from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, EmailStr


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
    corporate_details: CorporateDetails
    signatory: SignatoryInformation
    documents: list[DocumentReference]


class ApplicationReceivedResponse(BaseModel):
    application_reference: str
    status: str = "received"
    received_at: datetime
