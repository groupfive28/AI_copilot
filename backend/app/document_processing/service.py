from fastapi import UploadFile

from app.document_processing.schemas import DocumentUploadResponse


async def receive_upload(file: UploadFile) -> DocumentUploadResponse:
    """
    Reads the incoming file to determine its size and hands back basic metadata.

    This is intentionally a no-op beyond that: no persistence, OCR, extraction,
    or verification logic. It exists to prove the upload path from the React
    frontend, through this router/service layer, and back, works end to end.
    """
    contents = await file.read()
    return DocumentUploadResponse(
        filename=file.filename or "unnamed",
        content_type=file.content_type,
        size_bytes=len(contents),
    )
