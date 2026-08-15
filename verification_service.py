"""
verification_service.py
------------------------
The orchestrator. Entry point the rest of your system should call: give it
a director_id, it pulls ALL of that director's uploaded documents from
Firebase (any number, any of jpg/jpeg/png), runs face detection on each,
matches the ones that actually contain a face against the recent photo,
aggregates into one overall verdict, and writes the result to Supabase
(your verification portal) and optionally mirrors it to Firestore.
"""

import logging
import os

import firebase_client
import supabase_client
import face_processing
import embedding
import age_estimation
import decision_engine
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("face_verification.service")


def _process_one_candidate(recent_face, candidate, local_path, claimed_dob, director_id):
    """
    Runs detection + matching for a single candidate document against the
    already-processed recent photo. Returns a dict shaped for
    decision_engine.aggregate_multi_document_decision.
    """
    label = candidate.document_type or "UNKNOWN"
    cand_face = face_processing.process_image(local_path, label=label)

    if cand_face.embedding is None:
        # No face at all -- this document simply doesn't carry a photo
        # (utility bill, CAC certificate, board resolution, etc.). Skip it
        # gracefully rather than treating it as a failed match.
        return {
            "document_type": label,
            "document_url": candidate.url,
            "skipped": True,
            "skip_reason": cand_face.quality_reason or "no_face_detected",
            "decision": None,
        }

    similarity_score = None
    if recent_face.embedding is not None:
        similarity_score = embedding.cosine_similarity(recent_face.embedding, cand_face.embedding)

    age_gap_result = age_estimation.estimate_age_gap(
        claimed_dob=claimed_dob,
        id_doc_estimated_age=cand_face.estimated_age,
        recent_photo_estimated_age=recent_face.estimated_age,
    )
    age_band = age_estimation.gap_to_band(age_gap_result.age_gap_years)

    decision = decision_engine.decide(
        similarity_score=similarity_score,
        age_gap_years=age_gap_result.age_gap_years,
        age_band=age_band,
        recent_photo_quality_ok=recent_face.quality_ok,
        id_document_quality_ok=cand_face.quality_ok,
        recent_photo_quality_reason=recent_face.quality_reason,
        id_document_quality_reason=cand_face.quality_reason,
        director_id=director_id,
    )
    if age_gap_result.estimate_disagreement_flag:
        decision["reasons"].append(
            f"age_estimate_confidence_low (source={age_gap_result.source}) -- treat age band as approximate"
        )

    return {
        "document_type": label,
        "document_url": candidate.url,
        "skipped": False,
        "skip_reason": None,
        "decision": decision,
    }


def verify_director_face(director_id: str, write_to_supabase: bool = True, write_to_firestore: bool = False) -> dict:
    """
    Full pipeline for one director:
      1. Discover + download the recent photo + every candidate document
         (any number, any of jpg/jpeg/png) from Firebase Storage
      2. Detect/align/quality-check the recent photo once
      3. For each candidate document: detect a face if present, match
         against the recent photo, decide a per-document verdict
         (documents with no face are skipped, not penalised)
      4. Aggregate all per-document verdicts into one overall result
      5. Write the result to Supabase (verification portal) and optionally
         mirror to Firestore for local audit
    """
    logger.info("Starting face verification for director_id=%s", director_id)

    doc_set = firebase_client.get_director_document_set(director_id)
    recent_local_path, candidate_locals = firebase_client.fetch_all_director_images(doc_set)

    local_paths_to_clean = [recent_local_path] + [p for _, p in candidate_locals]

    try:
        recent_face = face_processing.process_image(recent_local_path, label="recent_photo")

        per_document_results = []
        for candidate, local_path in candidate_locals:
            entry = _process_one_candidate(
                recent_face, candidate, local_path, doc_set.claimed_dob, director_id
            )
            per_document_results.append(entry)

        result = decision_engine.aggregate_multi_document_decision(director_id, per_document_results)

    finally:
        for p in local_paths_to_clean:
            if p and os.path.exists(p):
                os.remove(p)

    if write_to_supabase:
        supabase_client.write_verification_result(result)

    if write_to_firestore:
        firebase_client.write_verification_result_firestore(director_id, result)

    return result


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) != 2:
        print("Usage: python verification_service.py <director_id>")
        sys.exit(1)

    outcome = verify_director_face(sys.argv[1])
    print(json.dumps(outcome, indent=2))
