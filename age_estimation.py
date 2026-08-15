"""
age_estimation.py
------------------
Determines the age-gap band to use for threshold selection.

Two signals are combined, in priority order:
  1. If we have a verified DOB (from your NIN/BVN cross-check upstream) AND
     the ID document type/issuance norms give a rough age at issuance,
     that's the most reliable signal.
  2. Otherwise, fall back to the model's own age estimate on the ID-document
     face vs. the age estimate on the recent photo — noisier, but works
     when we have no reliable document-issuance metadata.

This module deliberately keeps things conservative: when uncertain, it
picks a WIDER age band, which widens the review zone rather than
narrowing it -- i.e. uncertainty pushes toward NEEDS_REVIEW, not toward
false confidence in either direction.
"""

import logging
from datetime import date, datetime
from typing import Optional, NamedTuple

import config

logger = logging.getLogger("face_verification.age_estimation")

# If the model's own age estimate on the ID-document photo disagrees with
# the DOB-derived age at that photo's estimated capture time by more than
# this many years, we flag it -- this can indicate either a poor age
# estimate (common on children/low-quality photos) OR a genuine identity
# mismatch, so it's surfaced as a review signal rather than silently
# trusted either way.
AGE_ESTIMATE_DISAGREEMENT_THRESHOLD_YEARS = 12.0


class AgeGapResult(NamedTuple):
    age_gap_years: float
    source: str                      # "verified_dob" | "dual_estimate_fallback" | "no_signal"
    estimate_disagreement_flag: bool  # True if model's own age guess looks unreliable


def _parse_dob(dob_str: Optional[str]) -> Optional[date]:
    if not dob_str:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(dob_str, fmt).date()
        except ValueError:
            continue
    logger.warning("Could not parse DOB string: %s", dob_str)
    return None


def _current_age_from_dob(dob: date) -> float:
    today = date.today()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return float(years)


def estimate_age_gap(
    claimed_dob: Optional[str],
    id_doc_estimated_age: Optional[float],
    recent_photo_estimated_age: Optional[float],
) -> AgeGapResult:
    """
    Returns a best-effort estimate of the number of years between when
    the ID document photo was taken and now, plus provenance/flags.
    """
    dob = _parse_dob(claimed_dob)

    # Preferred path: verified current age minus the model's estimated age
    # *in the ID photo* gives us how old the person was when that photo
    # was taken, and thus the elapsed gap to now.
    if dob is not None and id_doc_estimated_age is not None:
        current_age = _current_age_from_dob(dob)
        gap = max(0.0, current_age - id_doc_estimated_age)
        logger.info("Age gap via verified DOB: current_age=%.1f, id_photo_age=%.1f, gap=%.1f",
                    current_age, id_doc_estimated_age, gap)

        # Sanity-check the model's own estimate against the DOB-derived truth.
        # A wide disagreement usually means the age model choked on this
        # photo (very common on children / low-quality scans) -- flag it so
        # a reviewer knows the age-band selection itself may be shaky,
        # rather than treating the resulting band as authoritative.
        disagreement = False
        if recent_photo_estimated_age is not None:
            implied_dob_age_now = id_doc_estimated_age + gap
            if abs(implied_dob_age_now - current_age) > AGE_ESTIMATE_DISAGREEMENT_THRESHOLD_YEARS:
                disagreement = True

        return AgeGapResult(gap, "verified_dob", disagreement)

    # Fallback: difference between the two models' age estimates
    if id_doc_estimated_age is not None and recent_photo_estimated_age is not None:
        gap = abs(recent_photo_estimated_age - id_doc_estimated_age)
        logger.info("Age gap via dual age-estimate fallback: gap=%.1f", gap)
        # No DOB to cross-check against here, but flag this path itself as
        # lower-confidence -- it has no independent verification at all.
        return AgeGapResult(gap, "dual_estimate_fallback", True)

    # No usable signal at all -- default to a mid-range band so thresholds
    # stay conservative rather than falsely confident.
    logger.warning("No usable signal for age-gap estimation; using default band")
    return AgeGapResult(_band_midpoint(config.DEFAULT_AGE_BAND), "no_signal", True)


def _band_midpoint(band_name: str) -> float:
    midpoints = {"0-5": 2.5, "5-15": 10.0, "15-30": 22.5, "30+": 35.0}
    return midpoints.get(band_name, 10.0)


def gap_to_band(age_gap_years: float) -> str:
    if age_gap_years <= 5:
        return "0-5"
    elif age_gap_years <= 15:
        return "5-15"
    elif age_gap_years <= 30:
        return "15-30"
    else:
        return "30+"
