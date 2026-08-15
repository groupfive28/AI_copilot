"""
firebase_client.py
-------------------
Reads a director's document URLs from Firestore, then downloads each
document directly by HTTP GET. No Firebase Storage SDK/bucket access is
needed here -- the database side stores each uploaded document as a
public/download URL on the director's Firestore record, so we just fetch
them like any other file on the web.

This is also what makes format-agnostic handling trivial: we save
whatever bytes come back and let OpenCV sniff the actual format from
content when reading it later -- doesn't matter if the URL points to a
.jpg, .jpeg, or .png.
"""

import os
import logging
import mimetypes
from typing import List

import requests
import firebase_admin
from firebase_admin import credentials, firestore

import config

logger = logging.getLogger("face_verification.firebase")

_app = None
_db = None


def init_firebase():
    """Idempotent Firebase (Firestore-only) initialisation. Call once at service startup."""
    global _app, _db
    if _app is not None:
        return

    cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
    _app = firebase_admin.initialize_app(cred)
    _db = firestore.client()
    logger.info("Firebase (Firestore) initialised")


def _ensure_init():
    if _app is None:
        init_firebase()


def _normalise_document_urls(raw_value) -> List["config.CandidateDocument"]:
    """
    Accepts either shape the database side might use:
      - list of plain URL strings: ["https://...", "https://..."]
      - list of {"type": "NIN", "url": "https://..."} objects
    and returns a normalised list of CandidateDocument.
    """
    candidates = []
    if not raw_value:
        return candidates

    for item in raw_value:
        if isinstance(item, str):
            candidates.append(config.CandidateDocument(url=item, document_type="UNKNOWN"))
        elif isinstance(item, dict) and "url" in item:
            candidates.append(config.CandidateDocument(
                url=item["url"],
                document_type=item.get("type", "UNKNOWN"),
            ))
        else:
            logger.warning("Skipping unrecognised documentURLs entry: %r", item)

    return candidates


def get_director_document_set(director_id: str) -> "config.DirectorDocumentSet":
    """
    Reads the director's Firestore record and builds the full set of
    documents (as URLs) to run face verification against.
    """
    _ensure_init()

    doc_ref = _db.collection(config.DIRECTORS_COLLECTION).document(director_id)
    snapshot = doc_ref.get()
    if not snapshot.exists:
        raise ValueError(f"No director record found for id={director_id}")

    data = snapshot.to_dict()

    recent_photo_url = data.get(config.FIELD_RECENT_PHOTO_URL)
    if not recent_photo_url:
        raise ValueError(
            f"Director {director_id} has no '{config.FIELD_RECENT_PHOTO_URL}' set in Firestore -- "
            f"cannot run face verification without an anchor photo."
        )

    claimed_dob = data.get(config.FIELD_DATE_OF_BIRTH)
    candidates = _normalise_document_urls(data.get(config.FIELD_DOCUMENT_URLS))

    logger.info("Discovered %d candidate document(s) for director_id=%s", len(candidates), director_id)

    return config.DirectorDocumentSet(
        director_id=director_id,
        recent_photo_url=recent_photo_url,
        candidate_documents=candidates,
        claimed_dob=claimed_dob,
    )


def _extension_from_response(url: str, content_type: str) -> str:
    """Best-effort extension for the local temp file. Purely cosmetic --
    OpenCV reads by content signature, not extension, so this never
    affects correctness, only makes temp files easier to eyeball."""
    ext = mimetypes.guess_extension((content_type or "").split(";")[0].strip())
    if ext in (".jpg", ".jpeg", ".png"):
        return ext
    # fall back to sniffing the URL path itself
    lower = url.lower().split("?")[0]
    for candidate_ext in (".jpg", ".jpeg", ".png"):
        if lower.endswith(candidate_ext):
            return candidate_ext
    return ".jpg"  # harmless default; content-based reading doesn't care


def download_from_url(url: str, local_filename_hint: str) -> str:
    """Downloads an image by URL to TMP_DIR, returns the local file path."""
    os.makedirs(config.TMP_DIR, exist_ok=True)

    last_error = None
    for attempt in range(1, config.HTTP_MAX_RETRIES + 2):
        try:
            resp = requests.get(url, timeout=config.HTTP_REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
            ext = _extension_from_response(url, resp.headers.get("Content-Type", ""))
            local_path = os.path.join(config.TMP_DIR, f"{local_filename_hint}{ext}")
            with open(local_path, "wb") as f:
                f.write(resp.content)
            logger.info("Downloaded %s -> %s (%d bytes)", url, local_path, len(resp.content))
            return local_path
        except requests.RequestException as e:
            last_error = e
            logger.warning("Attempt %d/%d failed downloading %s: %s",
                            attempt, config.HTTP_MAX_RETRIES + 1, url, e)

    raise ConnectionError(f"Failed to download {url} after {config.HTTP_MAX_RETRIES + 1} attempts: {last_error}")


def fetch_all_director_images(doc_set: "config.DirectorDocumentSet"):
    """
    Downloads the anchor photo + every candidate document for a director.
    Returns (recent_photo_local_path, [(candidate_document, local_path), ...]).
    """
    recent_local = download_from_url(doc_set.recent_photo_url, f"{doc_set.director_id}_recent")

    candidate_locals = []
    for i, cand in enumerate(doc_set.candidate_documents):
        local_path = download_from_url(cand.url, f"{doc_set.director_id}_doc{i}")
        candidate_locals.append((cand, local_path))

    return recent_local, candidate_locals


def write_verification_result_firestore(director_id: str, result: dict):
    """Optional: also mirror the result onto the director's Firestore doc for local audit."""
    _ensure_init()
    doc_ref = _db.collection(config.DIRECTORS_COLLECTION).document(director_id)
    doc_ref.set({config.FACE_MATCH_SUBFIELD: result}, merge=True)
    logger.info("Mirrored face verification result to Firestore for director_id=%s -> %s",
                director_id, result["overall_result"])
