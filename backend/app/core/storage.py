"""
Direct Firebase/GCS Storage access for the backend - used only by the
admin-initiated document re-upload feature (operations/service.py). Every
other document upload in this project is client-direct from the browser
(see frontend/src/features/onboarding/wizard/wizardStorage.js); this is the
one deliberate exception, because routing the replacement file through the
backend lets it delete the stale document and upload the correction in one
atomic-enough step, rather than coordinating list/delete/upload calls from
the admin dashboard's own Firebase Storage SDK usage.
"""

import re

from google.cloud import storage

from app.core.config import settings

SUBMISSIONS_ROOT = "onboarding-applications"

_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client(project=settings.storage_project_id)
    return _client


def _sanitize_filename(filename: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]", "_", filename.strip())
    return name or "document"


def replace_document(application_id: str, document_category: str, filename: str, content: bytes, content_type: str | None) -> str:
    """Deletes every existing blob under this application/category, then
    uploads the new one. Deleting first matters: OCR processes every blob
    it finds under a category folder independently (see
    ocr/src/penta/ingest.py's list_submitted_documents), so leaving the
    stale wrong document in place alongside the correction would get both
    OCR'd and verified in the same pipeline run, producing a confusing mix
    of the old (wrong) and new (correct) results for what's supposed to be
    one document slot.

    Returns the new blob's full path."""
    bucket = _get_client().bucket(settings.storage_bucket)
    prefix = f"{SUBMISSIONS_ROOT}/{application_id}/{document_category}/"

    for blob in _get_client().list_blobs(bucket, prefix=prefix):
        blob.delete()

    blob_name = f"{prefix}{_sanitize_filename(filename)}"
    new_blob = bucket.blob(blob_name)
    new_blob.upload_from_string(content, content_type=content_type or "application/octet-stream")
    return blob_name
