"""HTTP entrypoint the onboarding portal calls to kick off OCR extraction
for an application's documents, already sitting in Firebase Storage at
onboarding-applications/{application_id}/{document_category}/{filename}.

    uvicorn penta.api:app --host 0.0.0.0 --port 8080

POST /applications/{application_id}/extract — call this once the frontend
has finished uploading (some or all of) an application's documents. No
per-document details needed in the request: document_category comes
straight from the Storage folder structure. Safe to call again later, e.g.
once more documents get uploaded, or to retry — every call (re)processes
everything currently submitted; a repeat extraction for a document that's
already been extracted before is recorded as such (see penta.ingest), not
silently skipped, since a call here is always something the frontend
explicitly asked for.

Submitted files are never moved, renamed, or deleted by this service —
once a customer submits an application, that data stays exactly where they
put it. See penta.ingest for what actually gets recorded (Supabase only).
penta.poller runs the same core on an automatic schedule as a fallback for
anything this endpoint missed, but — unlike this endpoint — does skip
documents already extracted at least once, since it isn't an explicit
trigger.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import Depends, FastAPI, Header, HTTPException
from google.cloud import storage
from pydantic import BaseModel

from penta.config import settings
from penta.db import mark_application_processing
from penta.ingest import list_submitted_documents, process_document

app = FastAPI(title="Penta OCR")

# One client shared across requests — Client() doesn't hit the network until
# an actual call is made, so this is safe to create at import time. project
# is passed explicitly because user ADC (as opposed to a service account key)
# doesn't carry a project id, and there's no ambient `gcloud config` inside
# a container to fall back on.
_client = storage.Client(project=settings.gcp_project_id)


class DocumentResult(BaseModel):
    document_category: str
    filename: str
    status: str  # "processed" | "failed"
    entities: dict[str, str] | None = None
    type_mismatch_suspected: bool = False
    attempt: int = 1
    error: str | None = None


class ExtractApplicationResponse(BaseModel):
    application_id: str
    results: list[DocumentResult]


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.extract_api_key and x_api_key != settings.extract_api_key:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/applications/{application_id}/extract",
    response_model=ExtractApplicationResponse,
    dependencies=[Depends(require_api_key)],
)
def extract_application(application_id: str) -> ExtractApplicationResponse:
    bucket = _client.bucket(settings.storage_bucket)
    submitted = list_submitted_documents(_client, bucket, application_id)

    if not submitted:
        return ExtractApplicationResponse(application_id=application_id, results=[])

    mark_application_processing(application_id)

    def handle(item: tuple[str, str, storage.Blob]) -> DocumentResult:
        document_category, filename, blob = item
        result = process_document(blob, application_id, document_category, filename)
        if not result.ok:
            return DocumentResult(
                document_category=document_category,
                filename=filename,
                status="failed",
                attempt=result.attempt,
                error=result.error,
            )
        return DocumentResult(
            document_category=document_category,
            filename=filename,
            status="processed",
            entities=result.entities,
            type_mismatch_suspected=result.type_mismatch_suspected,
            attempt=result.attempt,
        )

    # Each call is a handful of blocking network round-trips (GCS + Document
    # AI), so a small thread pool turns e.g. 8 sequential extractions into
    # roughly one extraction's worth of wall-clock time.
    with ThreadPoolExecutor(max_workers=min(8, len(submitted))) as pool:
        results = list(pool.map(handle, submitted))

    return ExtractApplicationResponse(application_id=application_id, results=results)
