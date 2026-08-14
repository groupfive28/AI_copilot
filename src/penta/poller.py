"""Periodically scans Firebase Storage for any application with documents
that haven't been processed yet, and runs them through Document AI.

    python -m penta.poller

This is a fallback safety net for anything the portal's POST
/applications/{application_id}/extract call missed (a dropped request,
etc.) — see penta.api for the primary, event-triggered path. Uses the exact
same core (penta.ingest) so a document is recorded identically regardless
of which path picks it up, with one deliberate difference: unlike the API
endpoint, this skips any document that already has at least one
extracted_fields row. The API always (re)processes because a call there is
an explicit request; this runs on a timer, so reprocessing everything on
every cycle would burn Document AI calls for no reason. Submitted files are
never moved, renamed, or deleted either way.
"""

from __future__ import annotations

import time

from google.cloud import storage

from penta.config import settings
from penta.db import count_prior_extractions, mark_application_processing
from penta.ingest import SUBMISSIONS_ROOT, list_submitted_documents, process_document


def _application_ids(client: storage.Client, bucket: storage.Bucket) -> set[str]:
    """Every application_id with at least one object under
    onboarding-applications/ — Storage "folders" are just common prefixes,
    so this walks one level deep via delimiter-based listing instead of
    downloading every blob name in the bucket."""
    iterator = client.list_blobs(bucket, prefix=f"{SUBMISSIONS_ROOT}/", delimiter="/")
    list(iterator)  # the SDK only populates .prefixes once the page is consumed
    return {prefix[len(SUBMISSIONS_ROOT) + 1 : -1] for prefix in iterator.prefixes}


def poll_once(client: storage.Client) -> int:
    """Check every application once and process anything not yet extracted. Returns the count processed."""
    bucket = client.bucket(settings.storage_bucket)
    processed = 0
    for application_id in _application_ids(client, bucket):
        submitted = list_submitted_documents(client, bucket, application_id)
        pending = [
            item for item in submitted if count_prior_extractions(application_id, item[0]) == 0
        ]
        if not pending:
            continue

        mark_application_processing(application_id)
        for document_category, filename, blob in pending:
            result = process_document(blob, application_id, document_category, filename)
            label = f"{application_id}/{document_category}/{filename}"
            print(f"processed {label}" if result.ok else f"failed {label}: {result.error}")
            processed += 1
    return processed


def main() -> None:
    client = storage.Client(project=settings.gcp_project_id)
    print(f"watching gs://{settings.storage_bucket}/{SUBMISSIONS_ROOT}/ every {settings.poll_interval_seconds}s")
    while True:
        processed = poll_once(client)
        if processed:
            print(f"processed {processed} document(s)")
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
