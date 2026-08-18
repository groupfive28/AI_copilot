from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

# Reuses the existing, now-fixed face_verification package rather than
# duplicating it - see Face_Verification_Test/face_verification_package/.
# Mirrors the sys.path pattern run_verifier.py already uses at the repo
# root for the same reason (that package isn't pip-installable as-is).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_FACE_VERIFICATION_PACKAGE = _REPO_ROOT / "Face_Verification_Test" / "face_verification_package"
if str(_FACE_VERIFICATION_PACKAGE) not in sys.path:
    sys.path.insert(0, str(_FACE_VERIFICATION_PACKAGE))

from face_verification import verify_documents  # noqa: E402

from faceverify import db, storage
from faceverify.config import settings

# verify_documents()'s application-level status -> our verification_results.status.
# INSUFFICIENT_EVIDENCE means a face couldn't be detected in one or both
# images (not that the people differ), so it maps to "error" - a mismatch
# verdict would overstate what was actually established.
_STATUS_MAP = {
    "FACE_CONSISTENT": "match",
    "REVIEW_REQUIRED": "mismatch",
    "INSUFFICIENT_EVIDENCE": "error",
}


def verify_application_faces(client, application_id: str) -> list[dict[str, Any]]:
    """
    For each director, compares their passport photo against THEIR OWN
    government-ID document - each director uploads their own ID during
    their block in the wizard now (see storage.py), not one shared document
    for the whole application. Each comparison is independent: one
    director's photo not matching their ID doesn't affect another
    director's result.

    Returns the list of results written (also persisted to
    verification_results as a side effect). A director with a photo but no
    matching government ID is silently skipped (no result written) rather
    than reported as a failure - same principle as everywhere else in this
    system that a missing input is "nothing to check," not evidence of
    anything wrong, though in the normal wizard flow this shouldn't happen
    since the ID upload step is mandatory.
    """
    documents = storage.list_application_documents(client, settings.storage_bucket, application_id)

    results = []
    for director_index in sorted(documents.director_photos):
        photo_blob = documents.director_photos[director_index]
        government_id = documents.government_ids.get(director_index)
        if government_id is None:
            continue
        gov_id_blob, gov_id_category = government_id
        result = _verify_one_director(application_id, director_index, photo_blob, gov_id_blob, gov_id_category)
        results.append(result)
    return results


def _verify_one_director(
    application_id: str,
    director_index: int,
    photo_blob,
    gov_id_blob,
    gov_id_category: str,
) -> dict[str, Any]:
    photo_name = f"director_{director_index}_photo{Path(photo_blob.name).suffix}"
    gov_id_name = f"government_id{Path(gov_id_blob.name).suffix}"

    temp_dir = storage.download_to_temp_dir({photo_name: photo_blob, gov_id_name: gov_id_blob})
    try:
        raw_result = verify_documents(str(temp_dir))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    status = _STATUS_MAP.get(raw_result["status"], "error")
    document_id = db.new_document_id()

    discrepancy_details = {
        "director_index": director_index,
        "government_id_category": gov_id_category,
        "face_verification_status": raw_result["status"],
        "reason": raw_result["reason"],
        "pairwise_comparisons": raw_result["pairwise_comparisons"],
    }

    db.save_face_verification_result(
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
