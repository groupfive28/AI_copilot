import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.document_processing.models import ExtractedField
from app.onboarding.models import Application
from app.onboarding.schemas import ApplicationReceivedResponse, ApplicationSubmission


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
