import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Application(Base):
    """Maps to penta_application.applications, created via backend/scripts/sql/001_create_penta_application_schema.sql."""

    __tablename__ = "applications"
    __table_args__ = {"schema": "penta_application"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    cac_registration_number: Mapped[str] = mapped_column(Text)
    company_name: Mapped[str] = mapped_column(Text)
    date_of_registration: Mapped[date | None] = mapped_column(Date)
    business_type: Mapped[str] = mapped_column(Text)
    tin: Mapped[str] = mapped_column(Text)
    signatory_full_name: Mapped[str] = mapped_column(Text)
    signatory_email: Mapped[str] = mapped_column(Text)
    signatory_phone_number: Mapped[str] = mapped_column(Text)
    signatory_designation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
