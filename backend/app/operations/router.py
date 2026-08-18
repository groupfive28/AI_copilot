import re

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.firebase_auth import require_admin
from app.operations.schemas import (
    ApplicationDecisionRequest,
    ApplicationDecisionResponse,
    ApplicationDetail,
    ApplicationListResponse,
    VerificationResultsResponse,
)
from app.operations.service import (
    get_application_detail,
    list_applications,
    list_verification_failures,
    reupload_document,
    update_application_status,
)
from app.verification.service import run_post_submission_pipeline

router = APIRouter(prefix="/api/v1/operations", tags=["Operations Review"])

# Document categories only ever contain lowercase letters and underscores
# (see backend/app/onboarding/schemas.py's DocumentCategory and
# frontend/src/features/onboarding/constants.js's CORPORATE_DOCUMENT_TYPES)
# - this isn't validating business meaning, just that the value is safe to
# interpolate into a Storage path (app/core/storage.py's replace_document).
_CATEGORY_PATTERN = re.compile(r"^[a-z_]+$")


@router.get("/ping")
def ping() -> dict[str, str]:
    """Placeholder route confirming this layer is wired up. Left unguarded -
    no business data, harmless liveness check."""
    return {"layer": "operations", "status": "scaffolded"}


@router.get("/applications", response_model=ApplicationListResponse)
def get_applications(
    status: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> ApplicationListResponse:
    return list_applications(db, status_filter=status, sort_by=sort_by, sort_dir=sort_dir)


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
def get_application(
    application_id: str,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> ApplicationDetail:
    """
    Per-document state is derived from the latest registry_lookup
    verification_result for that document (pending if none exists yet).
    face_verification results aren't shown per document here since they
    compare across documents rather than checking one document's data
    against a registry - they'd need their own place in this view later.
    """
    detail = get_application_detail(db, application_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return detail


@router.post("/applications/{application_id}/decision", response_model=ApplicationDecisionResponse)
def post_application_decision(
    application_id: str,
    body: ApplicationDecisionRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ApplicationDecisionResponse:
    application = update_application_status(
        db, application_id, body.decision, body.note, admin_email=admin.get("email", "")
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return ApplicationDecisionResponse(id=application.id, status=application.status, updated_at=application.updated_at)


@router.post("/applications/{application_id}/documents/{document_category}/reupload")
async def post_document_reupload(
    application_id: str,
    document_category: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    note: str | None = Form(default=None),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> dict:
    """
    Admin-initiated correction for one document slot - e.g. a mismatched
    national ID the reviewer has confirmed is genuinely the wrong document,
    with a correct one obtained from the applicant out of band (email,
    phone, in person). Deliberately not a customer-facing self-service
    re-upload flow - that's a separate, bigger feature (notifications,
    customer auth, a resume-application entry point) not built yet.

    Swaps the Storage file, resets the application to "processing", and
    re-runs the full pipeline (OCR -> face-verification -> registry
    verification -> auto-decision) exactly like a fresh submission - OCR
    already tracks re-extraction attempts per document
    (ocr/src/penta/ingest.py's count_prior_extractions), so re-running the
    whole thing rather than trying to scope just the one document reuses
    that existing machinery instead of duplicating it.
    """
    if not _CATEGORY_PATTERN.match(document_category):
        raise HTTPException(status_code=400, detail="Invalid document category")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    application = reupload_document(
        db,
        application_id,
        document_category,
        file.filename or "document",
        content,
        file.content_type,
        note,
        admin_email=admin.get("email", ""),
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    background_tasks.add_task(run_post_submission_pipeline, application_id)

    return {"status": "accepted", "application_id": application_id}


@router.get("/verification-results", response_model=VerificationResultsResponse)
def get_verification_results(
    failed_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> VerificationResultsResponse:
    return list_verification_failures(db, failed_only=failed_only)
