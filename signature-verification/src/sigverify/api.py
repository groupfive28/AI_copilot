from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from google.cloud import storage
from pydantic import BaseModel

from sigverify.config import settings
from sigverify.pipeline import verify_application_signatures

app = FastAPI(title="Penta Signature Verification")

_client = storage.Client(project=settings.gcp_project_id)


class DirectorResult(BaseModel):
    director_index: int
    document_id: str
    status: str  # match | mismatch | error
    discrepancy_details: dict


class VerifySignaturesResponse(BaseModel):
    application_id: str
    results: list[DirectorResult]


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.extract_api_key and x_api_key != settings.extract_api_key:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/applications/{application_id}/verify-signatures",
    response_model=VerifySignaturesResponse,
    dependencies=[Depends(require_api_key)],
)
def verify_signatures(application_id: str) -> VerifySignaturesResponse:
    """
    Compares each director's signature specimen against a signature found
    on THEIR OWN government-ID document. A director is silently skipped
    (not reported as a failure) if they have no matching government ID, or
    if their ID's document type has no known/detected signature field - see
    pipeline.py's docstrings.
    """
    results = verify_application_signatures(_client, application_id)
    return VerifySignaturesResponse(application_id=application_id, results=results)
