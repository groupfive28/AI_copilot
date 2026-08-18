from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.onboarding.schemas import (
    ApplicationReceivedResponse,
    ApplicationSubmission,
    WizardApplicationResponse,
    WizardApplicationSubmission,
)
from app.onboarding.service import receive_application, receive_wizard_application
from app.verification.service import run_post_submission_pipeline

router = APIRouter(prefix="/api/v1/onboarding", tags=["Onboarding Intake"])


@router.get("/ping")
def ping() -> dict[str, str]:
    """Placeholder route confirming this layer is wired up. No business logic yet."""
    return {"layer": "onboarding", "status": "scaffolded"}


@router.post("/applications", response_model=ApplicationReceivedResponse)
def submit_application(
    submission: ApplicationSubmission, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> ApplicationReceivedResponse:
    """
    Accepts a corporate account application (form fields + uploaded document
    references) from the onboarding frontend, persists it to
    penta_application.applications, and creates a placeholder
    extracted_fields row per document for the OCR pipeline to fill in later.

    OCR extraction, then verification, run as a background task after the
    response is sent - see app/verification/service.py:run_post_submission_pipeline.
    """
    result = receive_application(db, submission)
    background_tasks.add_task(run_post_submission_pipeline, result.application_reference)
    return result


@router.post("/wizard-submit", response_model=WizardApplicationResponse)
def submit_wizard_application(
    submission: WizardApplicationSubmission, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> WizardApplicationResponse:
    result = receive_wizard_application(db, submission)
    background_tasks.add_task(run_post_submission_pipeline, result.application_reference)
    return result
