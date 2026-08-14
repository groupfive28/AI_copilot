from fastapi import APIRouter, UploadFile

from app.document_processing.schemas import DocumentUploadResponse
from app.document_processing.service import receive_upload

router = APIRouter(prefix="/api/v1/document-processing", tags=["Document Processing"])


@router.get("/ping")
def ping() -> dict[str, str]:
    """Placeholder route confirming this layer is wired up. No business logic yet."""
    return {"layer": "document_processing", "status": "scaffolded"}


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile) -> DocumentUploadResponse:
    """
    Accepts a document upload and returns its basic metadata.

    Scaffolding only: no OCR, extraction, or persistence yet. This proves the
    frontend upload flow reaches the backend and gets a real response back.
    """
    return await receive_upload(file)
