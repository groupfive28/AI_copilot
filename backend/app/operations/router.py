from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.operations.schemas import ApplicationDetail, ApplicationListResponse, VerificationResultsResponse
from app.operations.service import get_application_detail, list_applications, list_verification_failures

router = APIRouter(prefix="/api/v1/operations", tags=["Operations Review"])


@router.get("/ping")
def ping() -> dict[str, str]:
    """Placeholder route confirming this layer is wired up. No business logic yet."""
    return {"layer": "operations", "status": "scaffolded"}


@router.get("/applications", response_model=ApplicationListResponse)
def get_applications(
    status: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> ApplicationListResponse:
    return list_applications(db, status_filter=status, sort_by=sort_by, sort_dir=sort_dir)


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: str, db: Session = Depends(get_db)) -> ApplicationDetail:
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


@router.get("/verification-results", response_model=VerificationResultsResponse)
def get_verification_results(
    failed_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> VerificationResultsResponse:
    return list_verification_failures(db, failed_only=failed_only)
