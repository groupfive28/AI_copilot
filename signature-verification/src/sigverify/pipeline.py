from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2

from sigverify import crop, db, storage
from sigverify.config import settings
from sigverify.model import cosine_similarity, embed
from sigverify.preprocess import preprocess_signature

# Calibrated against real usage, not a labeled dataset (none exists for
# this specific setup - specimen photo vs. signature cropped from a
# photographed ID). Three thresholds have been tried, each a real,
# evidence-driven revision - see chat history:
#   - 0.5 (first attempt): produced a false "match" against one early
#     different-people passport-signature comparison (0.9256 similarity).
#   - 0.97: raised deliberately high to avoid the above, but repeated real
#     application runs then showed genuine signatures consistently scoring
#     0.60-0.73 - well short of 0.97 - while genuinely wrong signatures
#     tested scored 0.10-0.30. A real, usable gap existed, just not near
#     1.0 the way a more accurate model would produce.
#   - 0.6: set at the bottom of that gap. Still, further real application
#     runs kept landing genuine signatures below it often enough that the
#     team decided the practical cost (clean applications routinely
#     escalating on a legitimate signature) outweighed the benefit.
# 0.5 (current): a deliberate team decision to accept the specific risk
# identified in the very first bullet above - a raw 0.9256 different-people
# score has been observed once, in an early, less representative test. The
# team weighed that known risk against the SigNet model's now-established
# inability to reliably clear a higher bar for genuine signatures, and
# chose to prioritize not blocking legitimate applications. This is a
# considered tradeoff, not evidence that 0.5 is "safe" the way 0.6 was
# reasoned to be - revisit if a real mismatch is observed scoring at or
# above 0.5.
_MATCH_THRESHOLD = 0.5


def verify_application_signatures(client, application_id: str) -> list[dict[str, Any]]:
    """For each director with a signature specimen, compares it against
    THEIR OWN government-ID document - each director uploads their own ID
    during their block in the wizard now (see storage.py), not one shared
    document for the whole application.

    Returns the list of results written (also persisted to
    verification_results as a side effect). A director is silently skipped
    (no result, no verification_results row) either when they have no
    matching government ID at all (shouldn't happen in the normal wizard
    flow - the ID upload step is mandatory), or when their ID's document
    type is known to not reliably carry a signature and none was found -
    see _compare's docstring for why that's deliberately not the same
    thing as status="not_found"."""
    documents = storage.list_application_documents(client, settings.storage_bucket, application_id)

    results = []
    for director_index in sorted(documents.director_signatures):
        specimen_blob = documents.director_signatures[director_index]
        government_id = documents.government_ids.get(director_index)
        if government_id is None:
            continue
        gov_id_blob, gov_id_category = government_id
        result = _verify_one_director(application_id, director_index, specimen_blob, gov_id_blob, gov_id_category)
        if result is not None:
            results.append(result)
    return results


def _verify_one_director(
    application_id: str,
    director_index: int,
    specimen_blob,
    gov_id_blob,
    gov_id_category: str,
) -> dict[str, Any] | None:
    specimen_name = f"director_{director_index}_signature{Path(specimen_blob.name).suffix}"
    gov_id_name = f"government_id{Path(gov_id_blob.name).suffix}"

    temp_dir = storage.download_to_temp_dir({specimen_name: specimen_blob, gov_id_name: gov_id_blob})
    try:
        outcome = _compare(temp_dir / specimen_name, temp_dir / gov_id_name, gov_id_category)
    finally:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    if outcome is None:
        return None

    status, discrepancy_details = outcome
    discrepancy_details["director_index"] = director_index
    discrepancy_details["government_id_category"] = gov_id_category

    document_id = db.new_document_id()
    db.save_signature_verification_result(
        application_id=application_id,
        document_id=document_id,
        status=status,
        discrepancy_details=discrepancy_details,
    )

    return {
        "director_index": director_index,
        "document_id": document_id,
        "status": status,
        "discrepancy_details": discrepancy_details,
    }


def _compare(specimen_path: Path, gov_id_path: Path, gov_id_category: str | None) -> tuple[str, dict[str, Any]] | None:
    """Returns None (meaning: write no verification_results row at all,
    same as verify_application() skipping a document category with no
    registry mapping) specifically when the government-ID document type has
    no known signature field and the generic best-effort detector found
    nothing either - that's "nothing to check here," not evidence of
    anything wrong, and folding it into status="not_found" would escalate
    every non-passport application for a reason that has nothing to do with
    fraud risk (auto_decide_application treats every non-"match" status as
    escalation-worthy - see verification/service.py's _CLEAN_STATUSES).
    Every other outcome (couldn't read an image, blank/unparseable crop) IS
    genuinely ambiguous and returns status="error", which still escalates -
    that's the right call for those cases since something concrete went
    wrong, not just "this ID type doesn't have this field."""
    gov_id_image = cv2.imread(str(gov_id_path))
    if gov_id_image is None:
        return "error", {"reason": "could not read government ID image"}

    signature_on_document = crop.crop_known_signature(gov_id_image, gov_id_category or "")
    if signature_on_document is None:
        signature_on_document = crop.crop_signature_best_effort(gov_id_image)

    if signature_on_document is None:
        return None

    specimen_image = cv2.imread(str(specimen_path), cv2.IMREAD_GRAYSCALE)
    if specimen_image is None:
        return "error", {"reason": "could not read signature specimen image"}

    try:
        preprocessed_specimen = preprocess_signature(specimen_image)
    except ValueError as exc:
        return "error", {"reason": f"signature specimen: {exc}"}

    try:
        preprocessed_document = preprocess_signature(signature_on_document)
    except ValueError as exc:
        return "error", {"reason": f"signature on government ID: {exc}"}

    similarity = cosine_similarity(embed(preprocessed_specimen), embed(preprocessed_document))
    status = "match" if similarity >= _MATCH_THRESHOLD else "mismatch"

    return status, {
        "similarity": round(similarity, 4),
        "threshold": _MATCH_THRESHOLD,
        "model": "SigNet (luizgh/sigver, pretrained on GPDS) - uncalibrated for this comparison, see README",
    }
