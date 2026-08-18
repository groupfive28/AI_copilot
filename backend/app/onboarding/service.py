import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.document_processing.models import ExtractedField
from app.onboarding.models import Application, ApplicationDirector
from app.onboarding.schemas import (
    ApplicationReceivedResponse,
    ApplicationSubmission,
    WizardApplicationResponse,
    WizardApplicationSubmission,
)


def receive_wizard_application(
    db: Session,
    submission: WizardApplicationSubmission,
) -> WizardApplicationResponse:
    """
    Originally wrote the NIN-registry update through the Supabase client
    (penta_document_registries isn't exposed via Supabase's API on purpose -
    the backend talks to Postgres directly - so that never worked, and would
    have needed separate credentials besides). Rewritten to use the same DB
    session as everything else, so this and the application insert below
    commit or roll back together atomically.

    A director's NIN not matching anything in the registry is expected, not
    an error - our seed data only covers ~100 fake NINs, so this will be
    every real applicant. Recorded and returned rather than aborting the
    whole submission.
    """
    now = datetime.now(UTC)
    unmatched_nins: list[str] = []
    application_id = submission.application_id or uuid.uuid4()

    for director_index, nin in enumerate(submission.director_nins):
        try:
            nin_value = int(nin)
        except ValueError:
            unmatched_nins.append(nin)
            continue

        # RETURNING the matched name in the same round trip this was
        # already making to stamp Company - application_directors exists
        # purely so later review screens can label a director's documents/
        # checks by name instead of an opaque index (see that table's
        # migration comment). first_name/etc. end up NULL below when the
        # NIN doesn't match anything, same as the existing
        # unmatched_nins handling.
        result = db.execute(
            text("""
                UPDATE penta_document_registries.nin_registry SET "Company" = :company WHERE nin_id = :nin
                RETURNING first_name, middle_name, last_name
            """),
            {"company": submission.cac_number, "nin": nin_value},
        )
        matched = result.mappings().first()
        if matched is None:
            unmatched_nins.append(nin)

        db.add(
            ApplicationDirector(
                id=uuid.uuid4(),
                application_id=application_id,
                director_index=director_index,
                nin=nin,
                first_name=matched["first_name"] if matched else None,
                middle_name=matched["middle_name"] if matched else None,
                last_name=matched["last_name"] if matched else None,
                created_at=now,
            )
        )

    application = Application(
        id=application_id,
        cac_registration_number=submission.cac_number,
        company_name=submission.company_name,
        tin=submission.tin,
        company_address=submission.company_address,
        status="received",
        created_at=now,
        updated_at=now,
    )

    db.add(application)
    db.commit()

    return WizardApplicationResponse(
        application_reference=str(application.id),
        status="received",
        company_name=submission.company_name,
        cac_number=submission.cac_number,
        unmatched_director_nins=unmatched_nins,
    )
def receive_application(db: Session, submission: ApplicationSubmission) -> ApplicationReceivedResponse:
    """
    Persists the application and one placeholder extracted_fields row per
    submitted document (extracted_data={}, confidence_score=None - "not yet
    OCR'd"). The OCR pipeline updates each row in place once it runs; until
    then these rows are what makes a document's status show as "pending"
    rather than not existing at all.
    """
    now = datetime.now(UTC)

    application = Application(
        id=submission.application_id or uuid.uuid4(),
        cac_registration_number=submission.corporate_details.cac_registration_number,
        company_name=submission.corporate_details.company_name,
        date_of_registration=submission.corporate_details.date_of_registration,
        business_type=submission.corporate_details.business_type,
        tin=submission.corporate_details.tin,
        signatory_full_name=submission.signatory.full_name,
        signatory_email=submission.signatory.email,
        signatory_phone_number=submission.signatory.phone_number,
        signatory_designation=submission.signatory.designation,
        status="received",
        created_at=now,
        updated_at=now,
    )
    db.add(application)
    db.flush()  # guarantees the applications row exists before the FK-referencing inserts below

    for document in submission.documents:
        db.add(
            ExtractedField(
                id=uuid.uuid4(),
                application_id=application.id,
                document_id=uuid.uuid4(),
                document_category=document.category.value,
                extracted_data={},
                confidence_score=None,
                created_at=now,
            )
        )

    db.commit()

    return ApplicationReceivedResponse(
        application_reference=str(application.id),
        received_at=now,
    )
