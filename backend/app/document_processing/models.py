import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExtractedField(Base):
    """
    Maps to penta_application.extracted_fields - one row per uploaded document.

    A row is created with extracted_data={} and confidence_score=None at
    application-submission time (before OCR has run); the OCR pipeline
    updates it in place once it processes the document.
    """

    __tablename__ = "extracted_fields"
    __table_args__ = {"schema": "penta_application"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("penta_application.applications.id")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    document_category: Mapped[str] = mapped_column(Text)
    extracted_data: Mapped[dict] = mapped_column(JSONB)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
