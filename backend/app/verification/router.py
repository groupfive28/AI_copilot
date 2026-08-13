from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/verification", tags=["Verification & Workflow"])


@router.get("/ping")
def ping() -> dict[str, str]:
    """Placeholder route confirming this layer is wired up. No business logic yet."""
    return {"layer": "verification", "status": "scaffolded"}
