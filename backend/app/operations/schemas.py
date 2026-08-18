import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel

ApplicationStatus = Literal["received", "processing", "escalated", "approved", "rejected"]
DocumentState = Literal["pending", "verified", "mismatch", "not_found", "error"]
PipelineStage = Literal["extracting", "verifying_faces", "verifying_signatures", "checking_registries", "done"]


class ApplicationListItem(BaseModel):
    id: uuid.UUID
    company_name: str
    cac_registration_number: str
    status: ApplicationStatus
    pipeline_stage: PipelineStage | None
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


class AuditLogEntryOut(BaseModel):
    id: uuid.UUID
    event_type: str
    event_details: dict[str, Any] | None
    created_at: datetime


class BiometricCheckDetail(BaseModel):
    """face_verification/signature_verification results - not part of
    `documents` above since they're not tied to one extracted_fields row
    the way a registry_lookup is (see get_application_detail). Every
    result is included here, not just failures, so a reviewer can see what
    matched as well as what didn't."""

    check_type: str  # "face_verification" | "signature_verification"
    director_index: int | None
    director_name: str | None  # None if the director's NIN never matched a registry row
    status: str
    discrepancy_details: dict[str, Any] | None
    created_at: datetime


class ApplicationDetail(BaseModel):
    id: uuid.UUID
    cac_registration_number: str
    company_name: str
    date_of_registration: date | None
    business_type: str | None  # NULL for applications from the wizard flow, which doesn't collect it
    tin: str
    signatory_full_name: str | None  # NULL for wizard-flow applications - see business_type
    signatory_email: str | None
    signatory_phone_number: str | None
    signatory_designation: str | None
    company_address: str | None  # NULL for the older non-wizard flow, which doesn't collect it
    status: ApplicationStatus
    pipeline_stage: PipelineStage | None
    created_at: datetime
    updated_at: datetime
    documents: list[ApplicationDocument]
    biometric_checks: list[BiometricCheckDetail]
    audit_log: list[AuditLogEntryOut]


# The three manual decisions an operator can make from the dashboard.
# "received"/"processing" are pipeline-internal states, not something an
# operator sets directly, so they're excluded here on purpose.
ApplicationDecision = Literal["approved", "rejected", "escalated"]


class ApplicationDecisionRequest(BaseModel):
    decision: ApplicationDecision
    note: str | None = None


class ApplicationDecisionResponse(BaseModel):
    id: uuid.UUID
    status: ApplicationStatus
    updated_at: datetime


class VerificationFailureDetail(BaseModel):
    document_category: str | None
    check_type: str
    registry_table: str | None
    status: str
    discrepancy_details: dict[str, Any] | None
    created_at: datetime
    # Which director this result belongs to - only meaningful for
    # face_verification/signature_verification (see list_verification_failures);
    # NULL for registry_lookup rows, which aren't tied to one director.
    director_index: int | None = None
    director_name: str | None = None


class ApplicationVerificationFailures(BaseModel):
    application_id: uuid.UUID
    company_name: str
    status: ApplicationStatus
    failures: list[VerificationFailureDetail]


class VerificationResultsResponse(BaseModel):
    items: list[ApplicationVerificationFailures]
