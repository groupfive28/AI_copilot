"""
config.py
---------
Central configuration for the Face Verification microservice.
All tunable parameters live here so the system can be re-calibrated
without touching pipeline logic.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Optional


# ---------------------------------------------------------------------------
# Environment / deployment — Firebase (Firestore only; documents are fetched
# by direct download URL, not via the Storage SDK/bucket API, since the
# database side stores each document as a URL on the director's record.)
# ---------------------------------------------------------------------------
FIREBASE_CREDENTIALS_PATH = os.getenv(
    "FIREBASE_CREDENTIALS_PATH", "/secrets/firebase-service-account.json"
)

# Firestore collection layout (adjust to match your actual schema)
DIRECTORS_COLLECTION = os.getenv("DIRECTORS_COLLECTION", "directors")
FACE_MATCH_SUBFIELD = "faceVerification"   # field written back on the director doc (optional local audit copy)

# Firestore field names on the director document. Adjust these three to
# match whatever the database side actually calls them -- this is the one
# place you're most likely to need to edit for your real schema.
FIELD_RECENT_PHOTO_URL = "recentPhotoURL"
FIELD_DOCUMENT_URLS = "documentURLs"        # expected: list of {"type": "NIN", "url": "..."} OR list of plain url strings
FIELD_DATE_OF_BIRTH = "dateOfBirth"         # ISO date string, from your OCR/BVN-verified record

# HTTP fetch settings for downloading images from their URLs
HTTP_REQUEST_TIMEOUT_SECONDS = 20
HTTP_MAX_RETRIES = 2

# Local/temp working directory for downloaded images before processing
TMP_DIR = os.getenv("FACE_VERIFY_TMP_DIR", "/tmp/face_verification")

# ---------------------------------------------------------------------------
# Environment / deployment — Supabase (verification portal / results sink)
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")   # use the service_role key, not the anon key, for server-side writes
SUPABASE_RESULTS_TABLE = os.getenv("SUPABASE_RESULTS_TABLE", "face_verification_results")

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------
# InsightFace model pack. 'buffalo_l' bundles: detection (SCRFD/RetinaFace),
# recognition (ArcFace, 512-d embeddings), and a genderage estimator —
# exactly the three sub-models this pipeline needs, from one dependency.
INSIGHTFACE_MODEL_NAME = "buffalo_l"
INSIGHTFACE_PROVIDERS = ["CPUExecutionProvider"]   # swap to ["CUDAExecutionProvider", "CPUExecutionProvider"] if a GPU is available
DETECTION_SIZE = (640, 640)

# ---------------------------------------------------------------------------
# Image quality gates (applied before matching; failing these routes
# straight to NEEDS_REVIEW rather than forcing an unreliable comparison)
# ---------------------------------------------------------------------------
MIN_FACE_PIXELS = 60          # minimum face bounding-box edge length, px
BLUR_VARIANCE_THRESHOLD = 60  # Laplacian variance below this => "too blurry"
MAX_POSE_YAW_DEGREES = 30     # reject faces turned further than this
DETECTION_CONFIDENCE_MIN = 0.60

# ---------------------------------------------------------------------------
# Age-aware similarity thresholds
# ---------------------------------------------------------------------------
# Cosine similarity from ArcFace embeddings, banded by estimated age gap
# between the two photos. Wider age gaps get a wider "needs review" band
# because embedding drift from aging is expected, not necessarily fraud.
#
# Each band: (match_threshold, review_threshold)
#   similarity >= match_threshold          -> MATCHED
#   review_threshold <= similarity < match -> NEEDS_REVIEW
#   similarity < review_threshold          -> MISMATCH
AGE_GAP_THRESHOLDS: Dict[str, Tuple[float, float]] = {
    "0-5":    (0.62, 0.45),
    "5-15":   (0.55, 0.38),
    "15-30":  (0.48, 0.32),
    "30+":    (0.42, 0.28),
}

# Fallback band used when age cannot be estimated/derived at all
DEFAULT_AGE_BAND = "5-15"

# ---------------------------------------------------------------------------
# Decision engine output labels
# ---------------------------------------------------------------------------
RESULT_MATCHED = "MATCHED"
RESULT_MISMATCH = "MISMATCH"
RESULT_NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class CandidateDocument:
    """One uploaded document that MAY contain a face (not all will)."""
    url: str
    document_type: str = "UNKNOWN"   # e.g. NIN, VOTERS_CARD, PASSPORT, DRIVERS_LICENSE, CAC, UTILITY_BILL...


@dataclass
class DirectorDocumentSet:
    """
    Everything needed to run face verification for one director:
    one anchor 'recent photo' plus any number of candidate documents,
    only some of which will actually contain a usable face. All fetched
    by URL rather than a Storage SDK path.
    """
    director_id: str
    recent_photo_url: str
    candidate_documents: List[CandidateDocument] = field(default_factory=list)
    claimed_dob: Optional[str] = None   # ISO date, from OCR/BVN-verified record if available
