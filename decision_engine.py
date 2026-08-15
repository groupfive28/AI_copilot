"""
decision_engine.py
-------------------
Turns a similarity score + age-gap band into the final three-tier
verdict, plus a structured record suitable for logging/audit.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import config

logger = logging.getLogger("face_verification.decision_engine")


def decide(
    similarity_score: Optional[float],
    age_gap_years: Optional[float],
    age_band: str,
    recent_photo_quality_ok: bool,
    id_document_quality_ok: bool,
    recent_photo_quality_reason: Optional[str],
    id_document_quality_reason: Optional[str],
    director_id: str,
) -> dict:
    """
    Returns a full result record:
    {
        "director_id": ...,
        "result": "MATCHED" | "MISMATCH" | "NEEDS_REVIEW",
        "similarity_score": float | None,
        "age_gap_estimate_years": float | None,
        "age_band_used": str,
        "threshold_match": float,
        "threshold_review": float,
        "reasons": [ ... ],
        "timestamp": ISO8601 string
    }
    """
    reasons = []

    # Gate 1: image quality. If either image failed quality checks,
    # we do not trust a similarity score enough to auto-decide.
    if not recent_photo_quality_ok or not id_document_quality_ok:
        if not recent_photo_quality_ok:
            reasons.append(f"recent_photo_quality_failed:{recent_photo_quality_reason}")
        if not id_document_quality_ok:
            reasons.append(f"id_document_quality_failed:{id_document_quality_reason}")
        return _build_result(
            director_id, config.RESULT_NEEDS_REVIEW, similarity_score,
            age_gap_years, age_band, None, None, reasons,
        )

    # Gate 2: no similarity score at all (e.g. one image had no face at all,
    # which quality checks upstream should have already caught, but guard anyway).
    if similarity_score is None:
        reasons.append("similarity_score_unavailable")
        return _build_result(
            director_id, config.RESULT_NEEDS_REVIEW, similarity_score,
            age_gap_years, age_band, None, None, reasons,
        )

    match_thresh, review_thresh = config.AGE_GAP_THRESHOLDS.get(
        age_band, config.AGE_GAP_THRESHOLDS[config.DEFAULT_AGE_BAND]
    )

    if similarity_score >= match_thresh:
        verdict = config.RESULT_MATCHED
        reasons.append(f"similarity {similarity_score:.3f} >= match threshold {match_thresh:.3f} for age band {age_band}")
    elif similarity_score >= review_thresh:
        verdict = config.RESULT_NEEDS_REVIEW
        reasons.append(f"similarity {similarity_score:.3f} between review threshold {review_thresh:.3f} and match threshold {match_thresh:.3f}")
    else:
        verdict = config.RESULT_MISMATCH
        reasons.append(f"similarity {similarity_score:.3f} < review threshold {review_thresh:.3f} for age band {age_band}")

    return _build_result(
        director_id, verdict, similarity_score, age_gap_years, age_band,
        match_thresh, review_thresh, reasons,
    )


def _build_result(director_id, verdict, similarity_score, age_gap_years,
                   age_band, match_thresh, review_thresh, reasons) -> dict:
    result = {
        "director_id": director_id,
        "result": verdict,
        "similarity_score": round(similarity_score, 4) if similarity_score is not None else None,
        "age_gap_estimate_years": round(age_gap_years, 1) if age_gap_years is not None else None,
        "age_band_used": age_band,
        "threshold_match": match_thresh,
        "threshold_review": review_thresh,
        "reasons": reasons,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("Decision for director_id=%s -> %s | %s", director_id, verdict, reasons)
    return result


def aggregate_multi_document_decision(director_id: str, per_document_results: list) -> dict:
    """
    Combines per-document decide() results (one per candidate document that
    actually had a detectable face) into a single overall verdict.

    `per_document_results` is a list of dicts, each shaped like:
        {
            "document_type": "NIN" | "VOTERS_CARD" | ... | "UNKNOWN",
            "document_url": "...",
            "skipped": bool,              # True if no face was found at all
            "skip_reason": str | None,
            "decision": <output of decide(), or None if skipped>
        }

    Aggregation policy (conservative by design -- this is a KYC gate, so
    the costly mistake is a false MATCH, not an extra human review):

      - If every candidate was skipped (no document had a detectable face
        at all) -> NEEDS_REVIEW. This is a genuinely ambiguous case: maybe
        the client only uploaded documents without photos (e.g. only CAC
        cert + utility bill), which your upload flow should ideally
        prevent, but the verification step shouldn't silently pass it.
      - If ANY document comes back MISMATCH -> overall NEEDS_REVIEW.
        A mismatch on even one document, while others match, is exactly
        the kind of inconsistency a human reviewer should see -- it could
        mean a swapped photo on one document, not necessarily that the
        whole application is fraudulent. We deliberately do NOT auto-reject
        here; auto-rejecting on a single low-quality mismatched scan would
        punish honest applicants for a bad photo, not fraud.
      - If NO document mismatches and AT LEAST ONE is MATCHED, and the
        rest are either MATCHED or NEEDS_REVIEW -> overall MATCHED, using
        the strongest similarity score as the headline number.
      - If NO document is MATCHED (only NEEDS_REVIEW / skipped) -> overall
        NEEDS_REVIEW.
    """
    reasons = []
    documents_checked = []
    decisions = []

    for entry in per_document_results:
        documents_checked.append({
            "document_type": entry.get("document_type", "UNKNOWN"),
            "document_url": entry.get("document_url"),
            "skipped": entry.get("skipped", False),
            "skip_reason": entry.get("skip_reason"),
            "result": entry["decision"]["result"] if entry.get("decision") else None,
            "similarity_score": entry["decision"]["similarity_score"] if entry.get("decision") else None,
            "age_band_used": entry["decision"]["age_band_used"] if entry.get("decision") else None,
        })
        if not entry.get("skipped") and entry.get("decision"):
            decisions.append(entry["decision"])

    if not decisions:
        reasons.append("no_candidate_document_had_a_detectable_face")
        return _build_multi_result(director_id, config.RESULT_NEEDS_REVIEW, None, documents_checked, reasons)

    verdicts = [d["result"] for d in decisions]
    similarity_scores = [d["similarity_score"] for d in decisions if d["similarity_score"] is not None]
    best_score = max(similarity_scores) if similarity_scores else None

    if config.RESULT_MISMATCH in verdicts:
        mismatched_types = [
            dc["document_type"] for dc, d in zip(documents_checked, decisions)
            if d["result"] == config.RESULT_MISMATCH
        ]
        reasons.append(f"mismatch_on_document(s): {mismatched_types} -- inconsistent with other document(s), needs human review")
        return _build_multi_result(director_id, config.RESULT_NEEDS_REVIEW, best_score, documents_checked, reasons)

    if config.RESULT_MATCHED in verdicts:
        matched_types = [
            dc["document_type"] for dc, d in zip(documents_checked, decisions)
            if d["result"] == config.RESULT_MATCHED
        ]
        reasons.append(f"matched_on_document(s): {matched_types}")
        return _build_multi_result(director_id, config.RESULT_MATCHED, best_score, documents_checked, reasons)

    reasons.append("all_checked_documents_fell_in_needs_review_band")
    return _build_multi_result(director_id, config.RESULT_NEEDS_REVIEW, best_score, documents_checked, reasons)


def _build_multi_result(director_id, overall_result, best_similarity_score, documents_checked, reasons) -> dict:
    result = {
        "director_id": director_id,
        "overall_result": overall_result,
        "best_similarity_score": round(best_similarity_score, 4) if best_similarity_score is not None else None,
        "documents_checked": documents_checked,
        "reasons": reasons,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("Aggregate decision for director_id=%s -> %s | %s", director_id, overall_result, reasons)
    return result
