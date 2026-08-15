"""
api.py
------
HTTP interface for the face verification microservice.

Run with:
    uvicorn api:app --host 0.0.0.0 --port 8001

Your main backend calls POST /verify/{director_id} once the director's
recent photo + ID document have been uploaded (i.e. after your NIN/BVN
cross-check step succeeds), and receives the MATCHED/MISMATCH/NEEDS_REVIEW
result synchronously. For high volume, wrap this call in a queue/worker
instead of calling it inline from the request thread.
"""

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import verification_service
import firebase_client

logger = logging.getLogger("face_verification.api")

app = FastAPI(
    title="Face Verification Service",
    description="Age-aware face matching between a director's recent photo and ID document photo.",
    version="1.0.0",
)


class DocumentCheckResult(BaseModel):
    document_type: str
    document_url: str | None
    skipped: bool
    skip_reason: str | None
    result: str | None
    similarity_score: float | None
    age_band_used: str | None


class VerificationResponse(BaseModel):
    director_id: str
    overall_result: str
    best_similarity_score: float | None
    documents_checked: list[DocumentCheckResult]
    reasons: list[str]
    timestamp: str


@app.on_event("startup")
def startup():
    firebase_client.init_firebase()
    # Warm up the face model on startup so the first real request isn't slow
    face_processing_module_warm_up()


def face_processing_module_warm_up():
    import face_processing
    try:
        face_processing.get_face_app()
        logger.info("Face model warmed up successfully")
    except Exception as e:
        logger.error("Model warm-up failed: %s", e)


@app.post("/verify/{director_id}", response_model=VerificationResponse)
def verify_director(director_id: str):
    """
    Runs face verification for a director: fetches the recent photo + every
    candidate document (by URL, from Firestore), matches, aggregates, and
    writes the result to Supabase. Returns the same result synchronously.
    """
    try:
        result = verification_service.verify_director_face(director_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (FileNotFoundError, ConnectionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error verifying director_id=%s", director_id)
        raise HTTPException(status_code=500, detail="Internal verification error")


@app.get("/health")
def health():
    return {"status": "ok"}
