import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = {"schema": "penta_application"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    cac_registration_number: Mapped[str] = mapped_column(Text)
    company_name: Mapped[str] = mapped_column(Text)

    date_of_registration: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    business_type: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tin: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    signatory_full_name: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    signatory_email: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    signatory_phone_number: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    signatory_designation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    company_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(Text)

    pipeline_stage: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApplicationDirector(Base):
    """One row per director submitted through the wizard, in submission
    order - see the schema migration's comment for why this exists (labeling
    which director a face/signature check or document belongs to by name,
    not just an opaque index)."""

    __tablename__ = "application_directors"
    __table_args__ = {"schema": "penta_application"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("penta_application.applications.id")
    )
    director_index: Mapped[int] = mapped_column(Integer)
    nin: Mapped[str] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    middle_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    
