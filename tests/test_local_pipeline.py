"""
test_local_pipeline.py
------------------------
Runs the face-matching pipeline against LOCAL image files, bypassing
Firebase and Supabase entirely. Use this for development/demo testing.

No flag names needed -- just list image paths. The FIRST image is treated
as the anchor (recent photo); every image after it is checked against
that anchor. Works with any number of documents (1, 2, 3, or more).

Usage (one document):
    python tests/test_local_pipeline.py recent.jpg id_document.jpg

Usage (three documents in one run):
    python tests/test_local_pipeline.py recent.jpg nin.jpg voters_card.png passport.jpeg

--dob is optional but strongly recommended -- without it, age-band
selection falls back to the model's own (less reliable) age guess.
    python tests/test_local_pipeline.py recent.jpg nin.jpg voters_card.png --dob 2002-10-24
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import face_processing
import embedding
import age_estimation
import decision_engine


def run(recent_photo_path: str, document_paths: list, dob: str = None):
    recent_face = face_processing.process_image(recent_photo_path, label="recent_photo")

    print("\n--- Anchor (recent photo) diagnostics ---")
    print(f"det_score={recent_face.det_score:.3f} yaw={recent_face.yaw_degrees} "
          f"estimated_age={recent_face.estimated_age} quality_ok={recent_face.quality_ok} "
          f"reason={recent_face.quality_reason}")
    print("------------------------------------------\n")

    per_document_results = []

    for path in document_paths:
        label = os.path.basename(path)
        cand_face = face_processing.process_image(path, label=label)

        print(f"--- {label} diagnostics ---")
        print(f"det_score={cand_face.det_score:.3f} yaw={cand_face.yaw_degrees} "
              f"estimated_age={cand_face.estimated_age} quality_ok={cand_face.quality_ok} "
              f"reason={cand_face.quality_reason}")

        if cand_face.embedding is None:
            print(f"-> SKIPPED (no face detected in this document)\n")
            per_document_results.append({
                "document_type": label,
                "document_url": path,
                "skipped": True,
                "skip_reason": cand_face.quality_reason or "no_face_detected",
                "decision": None,
            })
            continue

        similarity_score = None
        if recent_face.embedding is not None:
            similarity_score = embedding.cosine_similarity(recent_face.embedding, cand_face.embedding)

        age_gap_result = age_estimation.estimate_age_gap(
            claimed_dob=dob,
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
            director_id="TEST-LOCAL",
        )
        if age_gap_result.estimate_disagreement_flag:
            decision["reasons"].append(
                f"age_estimate_confidence_low (source={age_gap_result.source}) -- treat age band as approximate"
            )

        print(f"-> {decision['result']} (similarity={decision['similarity_score']}, "
              f"age_band={decision['age_band_used']})\n")

        per_document_results.append({
            "document_type": label,
            "document_url": path,
            "skipped": False,
            "skip_reason": None,
            "decision": decision,
        })

    overall = decision_engine.aggregate_multi_document_decision("TEST-LOCAL", per_document_results)

    print("=== OVERALL RESULT ===")
    print(json.dumps(overall, indent=2))
    return overall


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="First image = anchor (recent photo). Every image after it is checked against the anchor."
    )
    parser.add_argument("images", nargs="+",
                         help="recent_photo.jpg document1.jpg [document2.jpg ...]  -- at least 2 images total")
    parser.add_argument("--dob", default=None, help="ISO date YYYY-MM-DD, if known/verified")
    args = parser.parse_args()

    if len(args.images) < 2:
        parser.error("Provide at least 2 images: the recent photo, followed by one or more documents to check.")

    recent_photo = args.images[0]
    documents = args.images[1:]

    run(recent_photo, documents, args.dob)
