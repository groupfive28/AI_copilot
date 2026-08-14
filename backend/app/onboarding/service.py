import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.document_processing.models import ExtractedField
from app.onboarding.models import Application
from app.onboarding.schemas import ApplicationReceivedResponse, ApplicationSubmission
from sqlalchemy import text
from app.core.supabase import get_supabase_client
from app.onboarding.schemas import (
    ApplicationReceivedResponse,
    ApplicationSubmission,
    WizardApplicationResponse,
    WizardApplicationSubmission,
)


def receive_wizard_application(
    db: Session,
    submission: WizardApplicationSubmission,
) -> WizardApplicationResponse:

    now = datetime.now(UTC)

    # ------------------------------------------------------------
    # 1. Update the Penta NIN registry
    # ------------------------------------------------------------

    supabase = get_supabase_client()

    nin_registry = (
        supabase
        .schema("penta_document_registries")
        .table("nin_registry")
    )

    for nin in submission.director_nins:
        result = (
            nin_registry
            .update({"Company": submission.cac_number})
            .eq("nin", nin)
            .execute()
        )

        if not result.data:
            raise ValueError(
                f"Could not update NIN registry record for NIN {nin}."
            )

    # ------------------------------------------------------------
    # 2. Create the application
    # ------------------------------------------------------------

    application = Application(
        id=uuid.uuid4(),
        cac_registration_number=submission.cac_number,
        company_name=submission.company_name,
        tin=submission.tin,
        status="pending",
        created_at=now,
        updated_at=now,
    )

    db.add(application)
    db.commit()

    return WizardApplicationResponse(
        application_reference=str(application.id),
        status="pending",
        company_name=submission.company_name,
        cac_number=submission.cac_number,
    )
def receive_application(db: Session, submission: ApplicationSubmission) -> ApplicationReceivedResponse:
    """
    Persists the application and one placeholder extracted_fields row per
    submitted document (extracted_data={}, confidence_score=None - "not yet
    OCR'd"). The OCR pipeline updates each row in place once it runs; until
    then these rows are what makes a document's status show as "pending"
    rather than not existing at all.
    """
    now = datetime.now(UTC)

    application = Application(
        id=uuid.uuid4(),
        cac_registration_number=submission.corporate_details.cac_registration_number,
        company_name=submission.corporate_details.company_name,
        date_of_registration=submission.corporate_details.date_of_registration,
        business_type=submission.corporate_details.business_type,
        tin=submission.corporate_details.tin,
        signatory_full_name=submission.signatory.full_name,
        signatory_email=submission.signatory.email,
        signatory_phone_number=submission.signatory.phone_number,
        signatory_designation=submission.signatory.designation,
        status="received",
        created_at=now,
        updated_at=now,
    )
    db.add(application)
    db.flush()  # guarantees the applications row exists before the FK-referencing inserts below

    for document in submission.documents:
        db.add(
            ExtractedField(
                id=uuid.uuid4(),
                application_id=application.id,
                document_id=uuid.uuid4(),
                document_category=document.category.value,
                extracted_data={},
                confidence_score=None,
                created_at=now,
            )
        )

    db.commit()

    return ApplicationReceivedResponse(
        application_reference=str(application.id),
        received_at=now,
    )
