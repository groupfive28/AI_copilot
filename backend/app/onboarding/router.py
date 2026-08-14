from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.onboarding.schemas import ApplicationReceivedResponse, ApplicationSubmission
from app.onboarding.service import receive_application
from app.onboarding.schemas import (
    ApplicationReceivedResponse,
    ApplicationSubmission,
    WizardApplicationResponse,
    WizardApplicationSubmission,
)
router = APIRouter(prefix="/api/v1/onboarding", tags=["Onboarding Intake"])


@router.get("/ping")
def ping() -> dict[str, str]:
    """Placeholder route confirming this layer is wired up. No business logic yet."""
    return {"layer": "onboarding", "status": "scaffolded"}


@router.post("/applications", response_model=ApplicationReceivedResponse)
def submit_application(
    submission: ApplicationSubmission, db: Session = Depends(get_db)
) -> ApplicationReceivedResponse:
    """
    Accepts a corporate account application (form fields + uploaded document
    references) from the onboarding frontend, persists it to
    penta_application.applications, and creates a placeholder
    extracted_fields row per document for the OCR pipeline to fill in later.

    Does not trigger OCR/verification/workflow processing yet - that starts
    once those pipelines exist.
    """
    return receive_application(db, submission)
@router.post(
    "/wizard-submit",
    response_model=WizardApplicationResponse,
)
def submit_wizard_application(
    submission: WizardApplicationSubmission,
    db: Session = Depends(get_db),
) -> WizardApplicationResponse:
    return receive_wizard_application(db, submission)