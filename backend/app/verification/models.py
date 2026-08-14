import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VerificationResult(Base):
    """Maps to penta_application.verification_results - one row per verification check."""

    __tablename__ = "verification_results"
    __table_args__ = {"schema": "penta_application"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("penta_application.applications.id")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    check_type: Mapped[str] = mapped_column(Text)  # registry_lookup | face_verification
    registry_table: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)  # match | mismatch | not_found | error
    discrepancy_details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
