import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLogEntry(Base):
    """Maps to penta_application.audit_log - append-only by convention (no DB-level enforcement)."""

    __tablename__ = "audit_log"
    __table_args__ = {"schema": "penta_application"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("penta_application.applications.id")
    )
    event_type: Mapped[str] = mapped_column(Text)
    event_details: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
