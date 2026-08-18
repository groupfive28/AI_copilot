import re
import uuid
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.document_processing.models import ExtractedField
from app.onboarding.models import Application
from app.operations.models import AuditLogEntry
from app.verification.models import VerificationResult

# Categories that resolve to a registry check in this pass. Everything else
# (nin/etc.) is skipped for now - see the module docstring below for why.
# board_resolution_form is deliberately absent - not yet AI-verified, per
# explicit instruction (uploaded and OCR'd like any other document, but
# never checked against a registry). cac_status_report used to be excluded
# for the same reason but now has its own dedicated check - see
# CAC_STATUS_REPORT_CATEGORIES/_verify_cac_status_report below - it's a
# native PDF (not a photographed document) with several fields the plain
# CAC certificate check can't reliably compare, so it gets richer,
# mismatch-capable verification than company_name/TIN alone.
CAC_TIN_CATEGORIES = {"certificate_of_incorporation", "cac_certificate", "tin"}
CAC_STATUS_REPORT_CATEGORIES = {"cac_status_report"}
PROOF_OF_ADDRESS_CATEGORIES = {"proof_of_address"}

# Personal-ID document categories -> the registry table(s) to check against.
# A tuple of more than one entry means the category is ambiguous about which
# document type it actually is (the non-wizard flow's
# "passport_or_drivers_license" combines both into one upload slot) - each
# listed table is tried in order, first match wins. Deliberately excludes
# "nin" - director NINs are already checked at wizard-submission time via a
# different code path (see receive_wizard_application), so re-checking them
# here would be redundant.
PERSONAL_ID_REGISTRY_MAP: dict[str, tuple[str, ...]] = {
    "bvn": ("bvn_registry",),
    "voters_card": ("voters_id_registry",),
    "passport_or_drivers_license": ("passport_registry", "drivers_license_registry"),
    "govt_id_international_passport": ("passport_registry",),
    "govt_id_drivers_license": ("drivers_license_registry",),
    "govt_id_voters_card": ("voters_id_registry",),
    "govt_id_national_id_card": ("national_id_registry",),
}

# registry_table -> the column holding that person's ID number, for the
# registries we have a real OCR sample of and a working extractor for (see
# _extract_dob_and_id_number). Also doubles as the set of registries
# _find_registry_row_by_name selects dob/id_number for at all - see that
# function's docstring for why drivers_license_registry/bvn_registry are
# deliberately absent.
_ID_COLUMN_BY_REGISTRY = {
    "national_id_registry": "nin_id",
    "voters_id_registry": "voters_id",
    "passport_registry": "passport_number",
}

# Patterns below were derived from real Document AI output against Penta's
# fictional test documents (a national ID, a voters card, and an
# international passport - see chat history for the raw OCR text), not
# guessed. Domestic documents (national ID, voters card) share one label
# convention; the passport uses a completely different bilingual one -
# notably "Given Names / Prénoms" combines first+middle into one field,
# unlike the domestic documents' separate "FIRST NAME"/"MIDDLE NAME" lines.
# No pattern exists yet for bvn_registry or drivers_license_registry - no
# real sample has been seen for either, and deliberately not guessed at
# (see _extract_dob_and_id_number).
_DOB_PATTERN_DOMESTIC = re.compile(r"DATE OF BIRTH\s*\n\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
_ID_NUMBER_PATTERN_NATIONAL_ID = re.compile(r"ID NO\.?\s+(\d+)", re.IGNORECASE)
_DOB_PATTERN_PASSPORT = re.compile(r"Date of Birth\s*/\s*Date de naissance\s*\n\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
_ID_NUMBER_PATTERN_PASSPORT = re.compile(r"Passport No\.?\s*/\s*N[°o]\s*de passeport\s*\n\s*(\S+)", re.IGNORECASE)

# Derived from a real PEDCO electricity bill sample (see chat history for the
# raw OCR text) - not guessed. "INVOICE NO" is a same-line label:value;
# "ADDRESS" is a label with the value on the next line.
_INVOICE_NUMBER_PATTERN_PEDCO = re.compile(r"INVOICE NO\.?:?\s*(\d+)", re.IGNORECASE)
_ADDRESS_PATTERN_PEDCO = re.compile(r"ADDRESS:\s*\n\s*(.+)", re.IGNORECASE)


def _extract_utility_bill_fields(text_value: str) -> tuple[str | None, str | None]:
    """Best-effort structured extraction from a PEDCO electricity bill's raw
    OCR text. address is a genuine corroborating signal - a company's
    service address is stable, so it's expected to agree with the registry.
    invoice_number is extracted for display only and deliberately never
    compared: a real bill's invoice number is per-billing-cycle (confirmed
    against a real sample - a live bill printed 561 against the same
    company's registry-stored 18, an expected difference, not a fraud
    signal), so the registry's single static value can never be expected to
    equal any given current bill."""
    invoice_match = _INVOICE_NUMBER_PATTERN_PEDCO.search(text_value)
    address_match = _ADDRESS_PATTERN_PEDCO.search(text_value)
    invoice_number = invoice_match.group(1) if invoice_match else None
    address = address_match.group(1).strip() if address_match else None
    return invoice_number, address


# Derived from a real CAC status report PDF's Document AI text (see chat
# history for the raw output) - not guessed. Unlike every other document
# type this module parses, the status report is a native PDF (not a
# photographed image), so its text has no OCR-misread risk - but Document
# AI's plain-text linearization of its multi-column boxed layout jumbles
# the "Company Name"/"Category"/"Status"/"Email Address" label group away
# from their values (labels all print together, then values all print
# together, in a different order), so those four fields are NOT reliably
# position-extractable and are deliberately not attempted here - see
# _verify_cac_status_report's ocr_corroborated fallback for company_name.
# RC Number, Phone Number, and Address Street, by contrast, each keep a
# direct "label :\nvalue" adjacency in the real output and extract cleanly.
# Patterns are restricted to the text before "B. Director" specifically
# because "Phone Number"/"Email Address" labels repeat per-director further
# down the same document - without that split, .search() would risk
# matching a director's phone/email instead of the company's.
_RC_NUMBER_PATTERN_STATUS_REPORT = re.compile(r"RC Number\s*:\s*\n?(\S+)", re.IGNORECASE)
_PHONE_PATTERN_STATUS_REPORT = re.compile(r"Phone Number\s*:\s*\n?(\+.*)", re.IGNORECASE)
_EMAIL_PATTERN_STATUS_REPORT = re.compile(r"([\w.+-]+@[\w.-]+)\s*\nRC Number", re.IGNORECASE)
# The "Date of Registration" field is rendered as 6 individual digit boxes
# (DD MM YY), which Document AI reads as one digit per line - real sample
# confirmed this pattern reliably isolates exactly that run of 6 single-digit
# lines (nothing else in the document produces 6 consecutive one-character
# lines).
_DATE_PATTERN_STATUS_REPORT = re.compile(r"(?:^|\n)(\d)\n(\d)\n(\d)\n(\d)\n(\d)\n(\d)\n")


def _extract_status_report_fields(text_value: str) -> dict[str, str | date | None]:
    """Best-effort structured extraction from a CAC status report PDF's raw
    text. Restricted to the slice before "B. Director" - see the patterns'
    comment above for why. Returns None for any field that couldn't be
    parsed rather than raising - same non-punishing convention as
    _extract_dob_and_id_number/_extract_utility_bill_fields."""
    section_a = text_value.split("B. Director")[0]

    rc_match = _RC_NUMBER_PATTERN_STATUS_REPORT.search(section_a)
    phone_match = _PHONE_PATTERN_STATUS_REPORT.search(section_a)
    email_match = _EMAIL_PATTERN_STATUS_REPORT.search(section_a)
    date_match = _DATE_PATTERN_STATUS_REPORT.search(section_a)

    registration_date = None
    if date_match:
        d1, d2, m1, m2, y1, y2 = date_match.groups()
        try:
            registration_date = date(2000 + int(y1 + y2), int(m1 + m2), int(d1 + d2))
        except ValueError:
            registration_date = None

    return {
        "rc_number": rc_match.group(1) if rc_match else None,
        "phone_number": phone_match.group(1).strip() if phone_match else None,
        "email_address": email_match.group(1) if email_match else None,
        "date_of_registration": registration_date,
    }


def _extract_dob_and_id_number(registry_table: str, text_value: str) -> tuple[date | None, str | None]:
    """Best-effort structured extraction from raw OCR text. This is
    corroborating evidence layered on top of the name match
    (_find_registry_row_by_name already decided match/not_found) - never
    the primary signal - so failing to parse a field returns None for it
    rather than raising or counting against the document. Only
    national_id_registry, voters_id_registry, and passport_registry have a
    real pattern; anything else returns (None, None) unconditionally."""
    if registry_table == "passport_registry":
        dob_match = _DOB_PATTERN_PASSPORT.search(text_value)
        id_match = _ID_NUMBER_PATTERN_PASSPORT.search(text_value)
    elif registry_table in ("national_id_registry", "voters_id_registry"):
        dob_match = _DOB_PATTERN_DOMESTIC.search(text_value)
        id_match = _ID_NUMBER_PATTERN_NATIONAL_ID.search(text_value) if registry_table == "national_id_registry" else None
    else:
        return None, None

    dob = None
    if dob_match:
        try:
            dob = datetime.strptime(dob_match.group(1), "%d/%m/%Y").date()
        except ValueError:
            dob = None

    id_number = id_match.group(1) if id_match else None
    return dob, id_number


"""
Compares each of an application's extracted documents against the registry
data we actually have. CAC/TIN-related categories are checked against
cac_tin_registry, proof_of_address is checked against
pedco_electricity_registry, and personal-ID categories (bvn/voters_card/
govt_id_*/passport_or_drivers_license) are checked against their matching
registry - all using the *application's own claimed* values as the lookup
key, not anything parsed out of the OCR output.

That's a real limitation, not an oversight: we don't know the Document AI
processor's entity-type schema (it's specific to the OCR teammate's GCP
project, custom-trained per document type, and the live processor
currently configured is a plain OCR processor with no structured entities
at all - see verified test results elsewhere), so there's no reliable way
yet to say "this extracted field is the RC number" versus any other string
in the document. Director NIN is deliberately excluded from
PERSONAL_ID_REGISTRY_MAP for a different reason: it's already checked at
wizard-submission time via a separate code path (see
receive_wizard_application), which matches each director's NIN
individually - re-checking it here, against only the signatory's name,
would be a downgrade, not an improvement.

The proof_of_address check now has two independent, mismatch-capable
address signals. company_name is still the lookup key against
pedco_electricity_registry (unchanged - "not_found" means no PEDCO bill on
file for this company at all). Once a registry row is found,
application.company_address (the applicant's own typed claim, collected in
the wizard's dedicated address step) is compared against that row's
address via _address_matches, and separately the address is also
structurally extracted straight off the bill's own OCR text
(_extract_utility_bill_fields, pattern derived from a real PEDCO bill
sample) and compared the same way. A confident disagreement on *either*
signal flips the result to "mismatch" - both are genuine, real-sample-
backed comparisons, not guesses.

invoice_number is also extracted from the bill by
_extract_utility_bill_fields, but deliberately never compared: testing
against a real bill confirmed a company's registry-stored invoice_number
(a single static snapshot) legitimately differs from any given real bill's
own invoice_number (a live Mynte bill printed 561 against the registry's
stored 18, for the same company/address) - utility invoice numbers change
every billing cycle, so treating that as a mismatch would flag genuine
bills as fraudulent. It's kept in discrepancy_details for the reviewer's
reference only, alongside the older substring-based ocr_corroborated
check.

The personal-ID checks (_verify_personal_id) are weaker still, and for a
related reason: Application has no claimed BVN/voter's-card/passport/
license/national-ID number anywhere to look up by (those numbers are never
collected from the applicant at all, only the documents themselves are
uploaded). So rather than an exact-key lookup, this does a fuzzy name
match against every name plausibly associated with the application (see
_claimed_identity_names): signatory_full_name where it's set (the older
non-wizard flow), plus every director whose NIN was already matched
against nin_registry at wizard-submission time - reusing that match rather
than requiring a new "who's the signatory" field the wizard would have to
collect. A registry row's first_name and last_name words must appear as
words in ONE of those claimed names (never several blended together -
see _find_registry_row_by_name); middle_name is excluded from the
requirement (people routinely omit it on a form field, or nin_registry may
have one a signatory didn't type, so requiring it would turn real matches
into false not_founds).

It still can't identify which specific director a shared personal-ID
document belongs to, only that it belongs to *someone* the application has
already proven a real identity for - like the shared government ID in
face-verification/, these categories are uploaded once per application,
not once per director. And it's still inert for a wizard application where
every submitted director NIN failed to match nin_registry and no
signatory was collected either - there's nothing to compare against.

For national_id_registry, voters_id_registry, and passport_registry
specifically, a "mismatch" *is* now possible: once a name match is found,
_extract_dob_and_id_number tries to pull a date of birth and ID number out
of the document's raw OCR text using patterns derived from real samples of
each layout, and compares them against the matched registry row. If either
value was extracted and disagrees with the registry, the result is
"mismatch," not "match" - this is the one place in this module where
OCR-extracted content (not just the application's own claim) can flip the
verdict, because for these three registries the document layout is known
well enough to trust it. bvn_registry and drivers_license_registry have no
extractor yet (no real sample has been seen for either), so they keep the
original match/not_found-only behavior - failing to parse a field is never
treated as a mismatch, only a missed opportunity to corroborate.

The OCR-extracted text is still used, as a secondary corroboration signal
recorded in discrepancy_details (does the claimed/matched value show up
anywhere in the extracted text) - but for CAC/TIN and proof_of_address the
match/mismatch verdict is decided by the registry comparison, not by OCR.
"""


def _ocr_haystack(extracted_data: dict) -> str:
    haystack_parts = [str(v) for v in extracted_data.values() if isinstance(v, str)]
    return " ".join(haystack_parts).lower()


def _corroborated_by_ocr(extracted_data: dict, *needles: str) -> bool:
    """True if ANY needle appears as a substring - for alternative
    identifiers where either one showing up is meaningful (e.g. RC number
    or company name)."""
    haystack = _ocr_haystack(extracted_data)
    return any(needle.lower() in haystack for needle in needles if needle)


def _all_corroborated_by_ocr(extracted_data: dict, *needles: str) -> bool:
    """True only if EVERY needle independently appears somewhere in the
    text - for needles that are components of one claim (first_name,
    last_name) rather than alternatives. Deliberately does not require them
    to appear together as one contiguous phrase: real ID cards print
    surname and given name as separate labeled fields, often surname first
    (confirmed against real OCR output - "SURNAME\\nLUGTON...FIRST
    NAME\\nNEELY"), so checking for "Neely ... Lugton" as one substring
    would almost never match even when the name is clearly present."""
    haystack = _ocr_haystack(extracted_data)
    real_needles = [n for n in needles if n]
    return bool(real_needles) and all(needle.lower() in haystack for needle in real_needles)


def _name_words(name: str | None) -> set[str]:
    if not name:
        return set()
    return {w for w in re.split(r"\s+", name.strip().lower()) if w}


def _registry_full_name(row: dict) -> str:
    return " ".join(part for part in (row.get("first_name"), row.get("middle_name"), row.get("last_name")) if part)


def _claimed_identity_names(db: Session, application: Application) -> list[str]:
    """Every name plausibly associated with this application, to check a
    personal-ID document against. Two sources:

    1. signatory_full_name - set by the older non-wizard /applications flow
       (ApplicationSubmission.signatory), never set by the wizard.
    2. Directors whose NIN was matched against nin_registry at wizard
       submission time (see receive_wizard_application) - that function
       stamps the matched row's "Company" column with
       application.cac_registration_number, which doubles as a reverse
       index here: querying nin_registry for that same cac_registration_number
       recovers the real name(s) of every director this application already
       proved ownership of, with no extra schema or wizard UI change needed.

    Kept as a list, not one combined name, so a personal-ID document only
    has to match ONE claimed identity, never a blend of several - see
    _find_registry_row_by_name."""
    names: list[str] = []
    if application.signatory_full_name:
        names.append(application.signatory_full_name)

    director_rows = db.execute(
        text("""
            SELECT first_name, middle_name, last_name
            FROM penta_document_registries.nin_registry
            WHERE "Company" = :cac_number
        """),
        {"cac_number": application.cac_registration_number},
    ).mappings().all()
    names.extend(name for row in director_rows if (name := _registry_full_name(dict(row))))

    return names


def _find_registry_row_by_name(
    db: Session, registry_table: str, claimed_names: list[str]
) -> tuple[dict, str] | None:
    """Registries are small (tens to ~100 rows) and there's no indexed key
    to look up a person by here, so this fetches the whole table once and
    matches in Python rather than trying to build a fuzzy SQL WHERE clause.
    registry_table always comes from the fixed PERSONAL_ID_REGISTRY_MAP
    above, never user input.

    Each claimed name is tried independently, in order, against every
    registry row - never combined into one pooled word set, so a match can
    never assemble itself from one person's first name and a different
    person's last name. Only requires first_name + last_name to appear in
    the claimed name - middle_name is deliberately excluded from the match
    requirement (though still surfaced in the result). People routinely
    omit a middle name on a "full name" form field, or nin_registry may
    have one a signatory didn't type, so requiring it would turn real
    matches into false not_founds. Returns the (row, matched claimed name)
    pair for the first hit.

    Also selects dob/id_number, but only for registry_table values present
    in _ID_COLUMN_BY_REGISTRY - the ones we have a real OCR sample for and
    can actually parse a comparable value out of (see
    _extract_dob_and_id_number). Deliberately not selected for every
    registry: drivers_license_registry's equivalent column is literally
    named "D.0.B" (a zero, not the letter O - a real quirk in the source
    spreadsheet, confirmed against the live schema) rather than "D.O.B", so
    a table-agnostic query would break on it. Easier to leave those
    registries alone until there's an actual extractor for that layout than
    to paper over the mismatch."""
    id_column = _ID_COLUMN_BY_REGISTRY.get(registry_table)
    extra_columns = f', "{id_column}" AS id_number, "D.O.B" AS dob' if id_column else ""

    rows = db.execute(
        text(f"""
            SELECT first_name, middle_name, last_name{extra_columns}
            FROM penta_document_registries.{registry_table}
        """)  # noqa: S608
    ).mappings().all()

    for claimed_name in claimed_names:
        claimed_words = _name_words(claimed_name)
        if not claimed_words:
            continue
        for row in rows:
            required_words = _name_words(row["first_name"]) | _name_words(row["last_name"])
            if required_words and required_words.issubset(claimed_words):
                return dict(row), claimed_name
    return None


def _verify_personal_id(
    db: Session,
    application: Application,
    field: ExtractedField,
    now: datetime,
    registry_tables: tuple[str, ...],
) -> VerificationResult:
    claimed_names = _claimed_identity_names(db, application)

    match: tuple[dict, str] | None = None
    matched_table = registry_tables[0]  # fallback for not_found, so registry_table is never NULL for a registry_lookup
    for table in registry_tables:
        match = _find_registry_row_by_name(db, table, claimed_names)
        if match is not None:
            matched_table = table
            break

    if match is None:
        status = "not_found"
        discrepancy_details = {
            "reason": (
                "no signatory name or NIN-matched director found for this application to check against"
                if not claimed_names
                else f"no {'/'.join(registry_tables)} row matches any claimed identity for this application"
            ),
            "claimed_names_checked": claimed_names,
        }
    else:
        matched_row, matched_claimed_name = match
        registry_full_name = _registry_full_name(matched_row)

        ocr_dob, ocr_id_number = _extract_dob_and_id_number(matched_table, field.extracted_data.get("_text") or "")
        registry_dob = matched_row["dob"].date() if matched_row.get("dob") else None
        registry_id_number = matched_row.get("id_number")

        disagreements = []
        if ocr_dob is not None and registry_dob is not None and ocr_dob != registry_dob:
            disagreements.append("date_of_birth")
        if (
            ocr_id_number is not None
            and registry_id_number is not None
            and str(ocr_id_number).strip().lower() != str(registry_id_number).strip().lower()
        ):
            disagreements.append("id_number")

        status = "mismatch" if disagreements else "match"
        discrepancy_details = {
            "matched_claimed_name": matched_claimed_name,
            "matched_registry_name": registry_full_name,
            "ocr_corroborated": _all_corroborated_by_ocr(
                field.extracted_data, matched_row.get("first_name"), matched_row.get("last_name")
            ),
            "dob_on_registry": str(registry_dob) if registry_dob else None,
            "dob_extracted_from_document": str(ocr_dob) if ocr_dob else None,
            "id_number_on_registry": registry_id_number,
            "id_number_extracted_from_document": ocr_id_number,
            "disagreements": disagreements,
        }

    return VerificationResult(
        id=uuid.uuid4(),
        application_id=application.id,
        document_id=field.document_id,
        check_type="registry_lookup",
        registry_table=matched_table,
        status=status,
        discrepancy_details=discrepancy_details,
        created_at=now,
    )


def _verify_cac_tin(db: Session, application: Application, field: ExtractedField, now: datetime) -> VerificationResult:
    registry_row = (
        db.execute(
            text("""
                SELECT "RC_number", company_name, "TIN"
                FROM penta_document_registries.cac_tin_registry
                WHERE "RC_number" = :rc_number
            """),
            {"rc_number": application.cac_registration_number},
        )
        .mappings()
        .first()
    )

    if registry_row is None:
        status = "not_found"
        discrepancy_details = {"reason": "no cac_tin_registry row for this RC number"}
    else:
        company_matches = (registry_row["company_name"] or "").strip().lower() == (
            application.company_name or ""
        ).strip().lower()
        tin_matches = str(registry_row["TIN"]) == str(application.tin)
        ocr_corroborated = _corroborated_by_ocr(
            field.extracted_data, application.cac_registration_number, application.company_name
        )

        if company_matches and tin_matches:
            status = "match"
            discrepancy_details = {"ocr_corroborated": ocr_corroborated}
        else:
            status = "mismatch"
            discrepancy_details = {
                "company_name_claimed": application.company_name,
                "company_name_on_registry": registry_row["company_name"],
                "tin_claimed": application.tin,
                "tin_on_registry": registry_row["TIN"],
                "ocr_corroborated": ocr_corroborated,
            }

    return VerificationResult(
        id=uuid.uuid4(),
        application_id=application.id,
        document_id=field.document_id,
        check_type="registry_lookup",
        registry_table="cac_tin_registry",
        status=status,
        discrepancy_details=discrepancy_details,
        created_at=now,
    )


def _verify_cac_status_report(
    db: Session, application: Application, field: ExtractedField, now: datetime
) -> VerificationResult:
    """Looked up the same way as _verify_cac_tin (by the application's
    claimed RC number), but compares more of the document's own printed
    values against the registry, not just company_name/TIN - the status
    report is a native PDF with several reliably-extractable fields (see
    _extract_status_report_fields) the plain CAC certificate check can't
    offer. company_name has no reliable extractor (see that function's
    docstring for why), so it's corroborated via substring search only,
    same treatment as everywhere else in this module a field can't be
    confidently position-extracted. TIN has no printed value on this
    document type at all, so it's not part of this check."""
    registry_row = (
        db.execute(
            text("""
                SELECT "RC_number", company_name, "TIN", date_of_registration, email_address, phone_number
                FROM penta_document_registries.cac_tin_registry
                WHERE "RC_number" = :rc_number
            """),
            {"rc_number": application.cac_registration_number},
        )
        .mappings()
        .first()
    )

    if registry_row is None:
        status = "not_found"
        discrepancy_details = {"reason": "no cac_tin_registry row for this RC number"}
    else:
        extracted = _extract_status_report_fields(field.extracted_data.get("_text") or "")
        ocr_corroborated = _corroborated_by_ocr(field.extracted_data, registry_row["company_name"])

        disagreements = []
        if extracted["rc_number"] is not None and extracted["rc_number"] != registry_row["RC_number"]:
            disagreements.append("rc_number")
        if extracted["phone_number"] is not None and extracted["phone_number"] != registry_row["phone_number"]:
            disagreements.append("phone_number")
        if extracted["email_address"] is not None and extracted["email_address"] != registry_row["email_address"]:
            disagreements.append("email_address")
        registry_registration_date = (
            registry_row["date_of_registration"].date() if registry_row["date_of_registration"] else None
        )
        if extracted["date_of_registration"] is not None and extracted["date_of_registration"] != registry_registration_date:
            disagreements.append("date_of_registration")

        status = "mismatch" if disagreements else "match"
        discrepancy_details = {
            "rc_number_on_registry": registry_row["RC_number"],
            "rc_number_on_document": extracted["rc_number"],
            "phone_number_on_registry": registry_row["phone_number"],
            "phone_number_on_document": extracted["phone_number"],
            "email_address_on_registry": registry_row["email_address"],
            "email_address_on_document": extracted["email_address"],
            "date_of_registration_on_registry": registry_registration_date.isoformat()
            if registry_registration_date
            else None,
            "date_of_registration_on_document": extracted["date_of_registration"].isoformat()
            if extracted["date_of_registration"]
            else None,
            "company_name_on_registry": registry_row["company_name"],
            "company_name_ocr_corroborated": ocr_corroborated,
            "disagreements": disagreements,
        }

    return VerificationResult(
        id=uuid.uuid4(),
        application_id=application.id,
        document_id=field.document_id,
        check_type="registry_lookup",
        registry_table="cac_tin_registry",
        status=status,
        discrepancy_details=discrepancy_details,
        created_at=now,
    )


def _address_matches(claimed_address: str | None, registry_address: str | None) -> bool | None:
    """None means "can't tell" (one side missing) - never treated as a
    disagreement, since we can't penalize an application for data we don't
    have. Otherwise fuzzy, deliberately not exact-equality: the registry
    stores a terse address (e.g. "1621 BUTLER DR") while an applicant
    typing their address into a free-text field will very reasonably
    include more (city, state, country) or format it differently
    (case, abbreviations) - requiring an exact match would turn genuinely
    correct addresses into false mismatches. The registry's address only
    needs to appear as a substring of what was typed."""
    if not claimed_address or not registry_address:
        return None
    normalized_claimed = re.sub(r"\s+", " ", claimed_address.strip().lower())
    normalized_registry = re.sub(r"\s+", " ", registry_address.strip().lower())
    return normalized_registry in normalized_claimed


def _verify_proof_of_address(
    db: Session, application: Application, field: ExtractedField, now: datetime
) -> VerificationResult:
    registry_row = (
        db.execute(
            text("""
                SELECT invoice_number, company_name, address
                FROM penta_document_registries.pedco_electricity_registry
                WHERE lower(company_name) = lower(:company_name)
            """),
            {"company_name": application.company_name},
        )
        .mappings()
        .first()
    )

    if registry_row is None:
        status = "not_found"
        discrepancy_details = {"reason": "no pedco_electricity_registry row for this company name"}
    else:
        # Two independent address signals, both trustworthy enough to flip
        # the verdict to mismatch: the applicant's own typed
        # company_address, and the address structurally extracted off the
        # bill itself (_extract_utility_bill_fields - a real sample-derived
        # pattern, not a guess). invoice_number is extracted too but never
        # compared - see _extract_utility_bill_fields's docstring for why
        # (it's expected to legitimately differ every billing cycle).
        address_match = _address_matches(application.company_address, registry_row["address"])
        document_invoice_number, document_address = _extract_utility_bill_fields(field.extracted_data.get("_text") or "")
        document_address_match = _address_matches(document_address, registry_row["address"])
        ocr_corroborated = _corroborated_by_ocr(
            field.extracted_data, str(registry_row["invoice_number"]), registry_row["address"]
        )

        disagreements = []
        if address_match is False:
            disagreements.append("company_address_claimed")
        if document_address_match is False:
            disagreements.append("address_on_document")

        status = "mismatch" if disagreements else "match"
        discrepancy_details = {
            "company_name_matched": registry_row["company_name"],
            "invoice_number_on_registry": registry_row["invoice_number"],
            "invoice_number_on_document": document_invoice_number,
            "address_on_registry": registry_row["address"],
            "company_address_claimed": application.company_address,
            "address_match": address_match,
            "address_on_document": document_address,
            "address_on_document_match": document_address_match,
            "disagreements": disagreements,
            "ocr_corroborated": ocr_corroborated,
        }

    return VerificationResult(
        id=uuid.uuid4(),
        application_id=application.id,
        document_id=field.document_id,
        check_type="registry_lookup",
        registry_table="pedco_electricity_registry",
        status=status,
        discrepancy_details=discrepancy_details,
        created_at=now,
    )


def verify_application(db: Session, application_id: str) -> list[tuple[VerificationResult, str]]:
    """Returns (result, document_category) pairs - document_category lives
    on extracted_fields, not verification_results, so it isn't on the ORM
    object itself."""
    application = db.get(Application, application_id)
    if application is None:
        return []

    extracted_fields = (
        db.query(ExtractedField)
        .filter(ExtractedField.application_id == application_id)
        .filter(ExtractedField.extracted_data != {})  # skip documents OCR hasn't processed yet
        .all()
    )

    now = datetime.now(UTC)
    created: list[tuple[VerificationResult, str]] = []

    for field in extracted_fields:
        if field.document_category in CAC_TIN_CATEGORIES:
            result = _verify_cac_tin(db, application, field, now)
        elif field.document_category in CAC_STATUS_REPORT_CATEGORIES:
            result = _verify_cac_status_report(db, application, field, now)
        elif field.document_category in PROOF_OF_ADDRESS_CATEGORIES:
            result = _verify_proof_of_address(db, application, field, now)
        elif field.document_category in PERSONAL_ID_REGISTRY_MAP:
            result = _verify_personal_id(db, application, field, now, PERSONAL_ID_REGISTRY_MAP[field.document_category])
        else:
            continue  # no registry mapping for this category yet

        db.add(result)
        created.append((result, field.document_category))

    db.commit()
    return created


# Every automated verification check ends in one of these statuses - see
# the CHECK constraint on verification_results.status.
_CLEAN_STATUSES = {"match"}


def auto_decide_application(db: Session, application_id: str) -> str | None:
    """Rolls up every verification_results row for this application -
    registry_lookup, face_verification, and signature_verification alike
    (the latter two write their own rows directly rather than through
    verify_application) - into one overall status, recorded in audit_log
    alongside what was actually seen.

    signature_verification briefly had a threshold (0.97) high enough that
    it escalated nearly every application regardless of whether the
    signature was actually wrong, so for a short period it was excluded
    from this rollup entirely. That's no longer true: repeated real
    application runs recalibrated the match threshold to 0.6 (see
    signature-verification/pipeline.py's _MATCH_THRESHOLD) based on a
    consistent real gap - genuine signatures scored 0.60-0.73, genuinely
    wrong ones scored 0.10-0.30 - so a mismatch here is trustworthy again
    and back to counting like every other check.

    This is a triage step, not a final decision: "approved" here only
    means every automated check came back clean, not that a human signed
    off. This system never auto-rejects - only escalates for a human to
    review via the dashboard's decision panel, which can set any status
    (including overriding an auto-approval) regardless of what this
    function decided. That asymmetry is deliberate for a bank KYC flow:
    false-negative escalations (a clean application waiting an extra
    minute for a human glance) are cheap; a false-positive auto-rejection
    with no human in the loop is not.

    Applications with zero verification_results (no registry-checkable
    documents were uploaded, or OCR/face-verification haven't run yet) are
    left untouched - there's nothing to base a decision on, so status
    stays wherever it was (normally "processing")."""
    application = db.get(Application, application_id)
    if application is None:
        return None

    rows = db.execute(
        text("SELECT status FROM penta_application.verification_results WHERE application_id = :id"),
        {"id": application_id},
    ).mappings().all()
    if not rows:
        return None

    statuses = {row["status"] for row in rows}
    decision = "approved" if statuses <= _CLEAN_STATUSES else "escalated"

    now = datetime.now(UTC)
    application.status = decision
    application.updated_at = now
    db.add(
        AuditLogEntry(
            id=uuid.uuid4(),
            application_id=application.id,
            event_type="auto_decision",
            event_details={
                "decision": decision,
                "check_count": len(rows),
                "statuses_seen": sorted(statuses),
            },
            created_at=now,
        )
    )
    db.commit()
    return decision


def run_post_submission_pipeline(application_id: str) -> None:
    """
    Runs as a FastAPI BackgroundTask after an application is created, so the
    submission endpoint responds immediately rather than blocking on OCR or
    face verification. Opens its own DB session since the request-scoped
    one (from get_db) is already closed by the time a background task runs.

    Calls the OCR service, then the face-verification service, then the
    signature-verification service, then our own registry verification,
    then rolls everything up into an automated triage decision (see
    auto_decide_application) - in that order, since registry verification
    reads extracted_fields (which OCR populates) and the rollup needs every
    verification_results row to already exist. Face/signature verification
    don't depend on either and could technically run anytime, but are kept
    alongside OCR as the "gather evidence" phase before registry
    verification's "decide" phase. Each external call is independent: if
    any of the three isn't configured or fails, this logs it and continues
    rather than aborting the whole pipeline - registry verification still
    runs against whatever extracted_fields already exist.
    """
    db = SessionLocal()
    try:
        _set_pipeline_stage(db, application_id, "extracting")
        _call_external_service(
            db=db,
            service_url=settings.ocr_service_url,
            path=f"/applications/{application_id}/extract",
            api_key=settings.ocr_extract_api_key,
            label="OCR extraction",
            application_id=application_id,
        )

        _set_pipeline_stage(db, application_id, "verifying_faces")
        _call_external_service(
            db=db,
            service_url=settings.face_verification_service_url,
            path=f"/applications/{application_id}/verify-faces",
            api_key=settings.face_verification_api_key,
            label="Face verification",
            application_id=application_id,
        )

        _set_pipeline_stage(db, application_id, "verifying_signatures")
        _call_external_service(
            db=db,
            service_url=settings.signature_verification_service_url,
            path=f"/applications/{application_id}/verify-signatures",
            api_key=settings.signature_verification_api_key,
            label="Signature verification",
            application_id=application_id,
        )

        _set_pipeline_stage(db, application_id, "checking_registries")
        verify_application(db, application_id)
        auto_decide_application(db, application_id)

        _set_pipeline_stage(db, application_id, "done")
    finally:
        db.close()


def _set_pipeline_stage(db: Session, application_id: str, stage: str) -> None:
    """Committed immediately (separately from whatever the caller does
    next) so a frontend polling GET /applications/{id} sees progress live,
    rather than everything jumping straight from nothing to "done" once the
    whole background task finally returns."""
    db.execute(
        text("UPDATE penta_application.applications SET pipeline_stage = :stage WHERE id = :id"),
        {"stage": stage, "id": application_id},
    )
    db.commit()


def _call_external_service(
    *, db: Session, service_url: str, path: str, api_key: str, label: str, application_id: str
) -> None:
    if not service_url:
        print(f"{label}: service URL not configured - skipping for application {application_id}")
        return
    try:
        headers = {"X-API-Key": api_key} if api_key else {}
        # 300s, not the httpx default: real OCR/face-verification calls process
        # every document in the application sequentially against a live
        # external API (Document AI / InsightFace), and can legitimately take
        # a couple of minutes even when nothing is wrong - especially with
        # multiple heavy local services competing for the same CPU. This is a
        # background task with no user waiting on the response, so a
        # generous timeout costs nothing; too short a timeout has a real
        # cost - a call that was still genuinely succeeding gets abandoned,
        # and registry verification below then runs before that result ever
        # lands, silently producing an incomplete application with no
        # obvious sign anything went wrong.
        response = httpx.post(f"{service_url}{path}", headers=headers, timeout=300)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - logged, pipeline continues regardless
        print(f"{label} call failed for application {application_id}: {exc}")
        # Previously this print() was the only trace of a failure - visible
        # in server logs only, invisible from the dashboard, so an admin
        # looking at a stuck "processing" application had no way to tell
        # whether OCR/face-verification ever ran at all. Surfacing it in
        # audit_log makes it show up in the application's own Activity tab.
        db.add(
            AuditLogEntry(
                id=uuid.uuid4(),
                application_id=application_id,
                event_type="pipeline_call_failed",
                event_details={"label": label, "path": path, "error": str(exc)},
                created_at=datetime.now(UTC),
            )
        )
        db.commit()
