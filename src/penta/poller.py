from __future__ import annotations

import time
from pathlib import Path

from google.cloud import storage

from penta.config import settings
from penta.ingest import SUBMISSIONS_PREFIX, SUPPORTED_SUFFIXES, process_document


def _parse_submission_path(blob_name: str) -> tuple[str, str, str] | None:
    """Split a blob name into (bank_id, user_id, filename), or None if it's
    not a pending submission — outside onboarding-applications/ (that
    includes processed/, failed/, and results/, which all live at bucket
    root), a "folder" placeholder, doesn't match the expected layout, or
    isn't a supported file type."""
    if not blob_name.startswith(SUBMISSIONS_PREFIX):
        return None
    remainder = blob_name[len(SUBMISSIONS_PREFIX) :]
    if remainder.endswith("/") or not remainder:
        return None
    parts = remainder.split("/", 2)
    if len(parts) != 3:
        return None
    bank_id, user_id, filename = parts
    if Path(filename).suffix.lower() not in SUPPORTED_SUFFIXES:
        return None
    return bank_id, user_id, filename


def poll_once(client: storage.Client) -> int:
    """Check the bucket once and process anything pending. Returns the count processed."""
    bucket = client.bucket(settings.storage_bucket)
    processed = 0
    for blob in client.list_blobs(settings.storage_bucket):
        parsed = _parse_submission_path(blob.name)
        if parsed is None:
            continue
        bank_id, user_id, filename = parsed
        result = process_document(bucket, blob, bank_id, user_id, filename)
        print(f"processed {blob.name}" if result.ok else f"failed {blob.name}: {result.error}")
        processed += 1
    return processed


def main() -> None:
    client = storage.Client(project=settings.gcp_project_id)
    print(f"watching gs://{settings.storage_bucket} every {settings.poll_interval_seconds}s")
    while True:
        processed = poll_once(client)
        if processed:
            print(f"processed {processed} document(s)")
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
