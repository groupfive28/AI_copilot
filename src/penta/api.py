from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from google.cloud import storage
from pydantic import BaseModel

from penta.config import settings
from penta.ingest import SUBMISSIONS_PREFIX, SUPPORTED_SUFFIXES, process_document

app = FastAPI(title="Penta OCR")

_client = storage.Client(project=settings.gcp_project_id)


class ExtractRequest(BaseModel):
    bank_id: str
    user_id: str
    filename: str


class ExtractResponse(BaseModel):
    status: str  # "processed" | "failed"
    text: str | None = None
    error: str | None = None


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.extract_api_key and x_api_key != settings.extract_api_key:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/documents/extract", response_model=ExtractResponse, dependencies=[Depends(require_api_key)])
def extract(req: ExtractRequest) -> ExtractResponse:
    if Path(req.filename).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {req.filename}")

    bucket = _client.bucket(settings.storage_bucket)
    blob = bucket.blob(f"{SUBMISSIONS_PREFIX}{req.bank_id}/{req.user_id}/{req.filename}")
    if not blob.exists():
        raise HTTPException(status_code=404, detail="document not found in storage")

    result = process_document(bucket, blob, req.bank_id, req.user_id, req.filename)
    if not result.ok:
        return ExtractResponse(status="failed", error=result.error)
    return ExtractResponse(status="processed", text=result.text)
