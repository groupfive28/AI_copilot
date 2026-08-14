from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/external-sim", tags=["External Verification (Simulated)"])


@router.get("/ping")
def ping() -> dict[str, str]:
    """Placeholder route confirming this layer is wired up. No lookups yet."""
    return {"layer": "external_sim", "status": "scaffolded"}


# Planned, pending field specs:
#   POST /bvn/lookup               -> synthetic BVN registry
#   POST /pep-sanctions/screen     -> synthetic PEP/sanctions list
#   POST /corporate-registry/lookup -> synthetic corporate registry
