import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Text
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

    signatory_phone: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    signatory_designation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    
