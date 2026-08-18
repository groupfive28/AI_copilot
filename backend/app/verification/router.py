from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.verification.schemas import VerificationResultOut, VerifyApplicationResponse
from app.verification.service import verify_application

router = APIRouter(prefix="/api/v1/verification", tags=["Verification & Workflow"])


@router.get("/ping")
def ping() -> dict[str, str]:
    """Placeholder route confirming this layer is wired up. No business logic yet."""
    return {"layer": "verification", "status": "scaffolded"}


@router.post("/applications/{application_id}/verify", response_model=VerifyApplicationResponse)
def verify(application_id: str, db: Session = Depends(get_db)) -> VerifyApplicationResponse:
    """
    Compares each of the application's OCR'd documents against registry
    data. Only CAC/TIN-related document categories resolve to a check right
    now - see verification/service.py for why the others are deliberately
    skipped for the moment.
    """
    results = verify_application(db, application_id)
    return VerifyApplicationResponse(
        application_id=application_id,
        results=[
            VerificationResultOut(
                id=result.id,
                document_id=result.document_id,
                document_category=document_category,
                check_type=result.check_type,
                registry_table=result.registry_table,
                status=result.status,
                discrepancy_details=result.discrepancy_details,
                created_at=result.created_at,
            )
            for result, document_category in results
        ],
    )
