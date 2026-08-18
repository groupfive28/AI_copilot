import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class DocumentCategory(str, Enum):
    """Must match DOCUMENT_CATEGORIES ids in frontend/src/features/onboarding/constants.js."""

    CAC_CERTIFICATE = "cac_certificate"
    TIN = "tin"
    NIN = "nin"
    BVN = "bvn"
    VOTERS_CARD = "voters_card"
    PASSPORT_OR_DRIVERS_LICENSE = "passport_or_drivers_license"
    PROOF_OF_ADDRESS = "proof_of_address"


class CorporateDetails(BaseModel):
    cac_registration_number: str
    company_name: str
    date_of_registration: date | None = None
    business_type: str
    tin: str


class SignatoryInformation(BaseModel):
    full_name: str
    email: EmailStr
    phone_number: str
    designation: str


class DocumentReference(BaseModel):
    category: DocumentCategory
    document_subtype: str | None = None
    file_name: str
    content_type: str | None = None
    storage_path: str
    download_url: str


class ApplicationSubmission(BaseModel):
    # Client-generated, so uploaded documents can land in Storage under
    # this same id before the application exists server-side (the OCR
    # service looks up documents by application_id, not by any id minted
    # after the fact). Falls back to a server-generated id if omitted.
    application_id: uuid.UUID | None = None
    corporate_details: CorporateDetails
    signatory: SignatoryInformation
    documents: list[DocumentReference]


class ApplicationReceivedResponse(BaseModel):
    application_reference: str
    status: str = "received"
    received_at: datetime
class WizardApplicationSubmission(BaseModel):
    application_id: uuid.UUID | None = None  # see ApplicationSubmission.application_id
    company_name: str
    cac_number: str
    tin: str  # applications.tin is NOT NULL - required here so a missing value 422s instead of failing at the DB
    # min_length=2 - corporate account opening requires at least 2 directors,
    # per team decision. The wizard (OnboardingWizard.jsx's MIN_DIRECTORS)
    # already enforces this before submission; this is the server-side
    # backstop for that same rule, not a separate requirement.
    director_nins: list[str] = Field(min_length=2)
    company_address: str | None = None  # collected in the wizard's dedicated address step


class WizardApplicationResponse(BaseModel):
    application_reference: str
    status: str
    company_name: str
    cac_number: str
    unmatched_director_nins: list[str] = []  # NINs not found in the registry - not an error, just FYI
