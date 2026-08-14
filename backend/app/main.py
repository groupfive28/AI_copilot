from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.document_processing.router import router as document_processing_router
from app.external_sim.router import router as external_sim_router
from app.onboarding.router import router as onboarding_router
from app.operations.router import router as operations_router
from app.verification.router import router as verification_router

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboarding_router)
app.include_router(document_processing_router)
app.include_router(verification_router)
app.include_router(operations_router)
app.include_router(external_sim_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Reports API liveness and Postgres connectivity, for the frontend and Docker Compose to check."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unreachable"

    return {"status": "ok", "database": db_status}
