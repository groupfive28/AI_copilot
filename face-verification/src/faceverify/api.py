from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from google.cloud import storage
from pydantic import BaseModel

from faceverify.config import settings
from faceverify.pipeline import verify_application_faces

app = FastAPI(title="Penta Face Verification")

_client = storage.Client(project=settings.gcp_project_id)


class DirectorResult(BaseModel):
    director_index: int
    document_id: str
    status: str  # match | mismatch | error
    discrepancy_details: dict


class VerifyFacesResponse(BaseModel):
    application_id: str
    results: list[DirectorResult]


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.extract_api_key and x_api_key != settings.extract_api_key:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/applications/{application_id}/verify-faces",
    response_model=VerifyFacesResponse,
    dependencies=[Depends(require_api_key)],
)
def verify_faces(application_id: str) -> VerifyFacesResponse:
    """
    Compares each director's passport photo against their OWN government-ID
    document. A director with no matching ID is silently skipped rather
    than reported as a failure - see pipeline.py.
    """
    results = verify_application_faces(_client, application_id)
    return VerifyFacesResponse(application_id=application_id, results=results)
