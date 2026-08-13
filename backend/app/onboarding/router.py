from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/onboarding", tags=["Onboarding Intake"])


@router.get("/ping")
def ping() -> dict[str, str]:
    """Placeholder route confirming this layer is wired up. No business logic yet."""
    return {"layer": "onboarding", "status": "scaffolded"}
