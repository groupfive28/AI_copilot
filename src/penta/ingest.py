from __future__ import annotations

import mimetypes
from dataclasses import dataclass

from google.cloud import storage

from penta.docai import extract_text_bytes

SUBMISSIONS_PREFIX = "onboarding-applications/"

SUPPORTED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


@dataclass
class ProcessResult:
    ok: bool
    text: str | None = None
    error: str | None = None


def process_document(bucket: storage.Bucket, blob: storage.Blob, bank_id: str, user_id: str, filename: str) -> ProcessResult:
    """Extract text from blob, save the result, and file the source under
    processed/ or failed/. Never raises — failures come back as
    ProcessResult(ok=False, ...) so callers (HTTP handler, poll loop) each
    decide how to report them.
    """
    try:
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type is None:
            raise ValueError(f"could not determine mime type for {filename}")

        text = extract_text_bytes(blob.download_as_bytes(), mime_type)
        bucket.blob(f"results/{bank_id}/{user_id}/{filename}.txt").upload_from_string(text)
        bucket.copy_blob(blob, bucket, f"processed/{bank_id}/{user_id}/{filename}")
        blob.delete()
        return ProcessResult(ok=True, text=text)
    except Exception as exc:  # noqa: BLE001 - reported to the caller, not raised
        bucket.copy_blob(blob, bucket, f"failed/{bank_id}/{user_id}/{filename}")
        blob.delete()
        return ProcessResult(ok=False, error=str(exc))
