from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import Depends, FastAPI, Header, HTTPException
from google.cloud import storage
from pydantic import BaseModel

from penta.config import settings
from penta.db import mark_application_processing
from penta.ingest import list_submitted_documents, process_document

app = FastAPI(title="Penta OCR")

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
    
    with ThreadPoolExecutor(max_workers=min(8, len(submitted))) as pool:
        results = list(pool.map(handle, submitted))

    return ExtractApplicationResponse(application_id=application_id, results=results)
