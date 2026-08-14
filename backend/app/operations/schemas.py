import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel

ApplicationStatus = Literal["received", "processing", "escalated", "approved", "rejected"]
DocumentState = Literal["pending", "verified", "mismatch", "not_found", "error"]


class ApplicationListItem(BaseModel):
    id: uuid.UUID
    company_name: str
    cac_registration_number: str
    status: ApplicationStatus
    created_at: datetime


class ApplicationSummary(BaseModel):
    total: int
    pending_review: int  # status in (received, processing, escalated)
    verification_failures: int  # distinct applications with >=1 mismatch/not_found/error result


class ApplicationListResponse(BaseModel):
    summary: ApplicationSummary
    items: list[ApplicationListItem]


class ApplicationDocument(BaseModel):
    document_id: uuid.UUID
    document_category: str
    state: DocumentState
    confidence_score: Decimal | None
    registry_table: str | None
    discrepancy_details: dict[str, Any] | None


class ApplicationDetail(BaseModel):
    id: uuid.UUID
    cac_registration_number: str
    company_name: str
    date_of_registration: date | None
    business_type: str
    tin: str
    signatory_full_name: str
    signatory_email: str
    signatory_phone_number: str
    signatory_designation: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    documents: list[ApplicationDocument]


class VerificationFailureDetail(BaseModel):
    document_category: str | None
    check_type: str
    registry_table: str | None
    status: str
    discrepancy_details: dict[str, Any] | None
    created_at: datetime


class ApplicationVerificationFailures(BaseModel):
    application_id: uuid.UUID
    company_name: str
    status: ApplicationStatus
    failures: list[VerificationFailureDetail]


class VerificationResultsResponse(BaseModel):
    items: list[ApplicationVerificationFailures]
