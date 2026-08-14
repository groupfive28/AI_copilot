from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    """Echoes back basic file metadata. No OCR/extraction happens here yet."""

    filename: str
    content_type: str | None
    size_bytes: int
    status: str = "received"
