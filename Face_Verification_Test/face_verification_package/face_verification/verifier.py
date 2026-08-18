from __future__ import annotations

import os
from pathlib import Path
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from sklearn.metrics.pairwise import cosine_similarity

from .config import MATCH_THRESHOLD


# ============================================================
# CONFIGURATION
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

# The gap between "borderline" and "strong" evidence. Kept fixed so a
# caller-supplied threshold (verify_documents(..., threshold=...)) still
# produces a sensible two-tier classification instead of collapsing to one
# cutoff - see verify_documents' docstring for why this exists.
_STRONG_MARGIN = 0.10

# Module-level defaults, used when verify_documents() is called with no
# explicit threshold. BORDERLINE_THRESHOLD comes from config.py - the
# single tunable knob - rather than being redefined here, which is what
# left it disconnected from config.py before (config.py's MATCH_THRESHOLD
# was never actually read anywhere).
BORDERLINE_THRESHOLD = MATCH_THRESHOLD
STRONG_MATCH_THRESHOLD = BORDERLINE_THRESHOLD + _STRONG_MARGIN


# ============================================================
# MODEL
# ============================================================

_APP: Optional[FaceAnalysis] = None


def get_model() -> FaceAnalysis:
    """
    Load InsightFace once and reuse it.

    The model is deliberately loaded lazily so importing
    verifier.py does not immediately initialize InsightFace.
    """

    global _APP

    if _APP is None:

        _APP = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )

        _APP.prepare(
            ctx_id=-1,
            det_size=(640, 640),
        )

    return _APP


# ============================================================
# FACE DETECTION
# ============================================================

def _face_area(face) -> float:
    """
    Return the bounding-box area of a detected face.
    """

    x1, y1, x2, y2 = face.bbox

    return float(
        max(0.0, x2 - x1)
        * max(0.0, y2 - y1)
    )


def _largest_face(faces):
    """
    Return the largest detected face.
    """

    return max(
        faces,
        key=_face_area,
    )


def detect_best_face(image):
    """
    Detect faces using four possible orientations.

    Selection priority:

    1. Orientation with the greatest number of detected faces.
    2. If tied, orientation with the highest detection score.
    3. From the selected orientation, choose the largest face.

    Returns:

        (
            selected_face,
            selected_image,
            selected_orientation,
            face_count
        )

    If no face is detected:

        (
            None,
            None,
            "NOT_DETECTED",
            0
        )
    """

    model = get_model()

    orientations = {
        "ORIGINAL": image,

        "ROTATE_90": cv2.rotate(
            image,
            cv2.ROTATE_90_CLOCKWISE,
        ),

        "ROTATE_180": cv2.rotate(
            image,
            cv2.ROTATE_180,
        ),

        "ROTATE_270": cv2.rotate(
            image,
            cv2.ROTATE_90_COUNTERCLOCKWISE,
        ),
    }

    best_faces = []
    best_orientation = None
    best_image = None
    best_detection_score = -1.0

    for orientation_name, test_image in orientations.items():

        faces = model.get(test_image)

        # Prefer more detected faces.
        if len(faces) > len(best_faces):

            best_faces = faces
            best_orientation = orientation_name
            best_image = test_image

            best_detection_score = (
                max(
                    float(face.det_score)
                    for face in faces
                )
                if faces
                else -1.0
            )

        # If the number of faces is tied,
        # prefer the orientation with the strongest detection.
        elif (
            len(faces) == len(best_faces)
            and len(faces) > 0
        ):

            current_detection_score = max(
                float(face.det_score)
                for face in faces
            )

            if (
                current_detection_score
                > best_detection_score
            ):

                best_faces = faces
                best_orientation = orientation_name
                best_image = test_image
                best_detection_score = (
                    current_detection_score
                )

    if not best_faces:

        return (
            None,
            None,
            "NOT_DETECTED",
            0,
        )

    selected_face = _largest_face(best_faces)

    return (
        selected_face,
        best_image,
        best_orientation,
        len(best_faces),
    )


# ============================================================
# DOCUMENT READING
# ============================================================

def _read_documents(folder: Path) -> List[Path]:
    """
    Read supported image files directly inside the supplied
    application folder.

    The verifier does not depend on document filenames.
    """

    if not folder.exists():

        raise FileNotFoundError(
            f"Document folder does not exist: {folder}"
        )

    if not folder.is_dir():

        raise NotADirectoryError(
            f"Expected a folder: {folder}"
        )

    documents = [
        path
        for path in folder.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            in SUPPORTED_EXTENSIONS
        )
    ]

    return sorted(
        documents,
        key=lambda path: path.name.lower(),
    )


# ============================================================
# SIMILARITY
# ============================================================

def _calculate_similarity(
    embedding1: np.ndarray,
    embedding2: np.ndarray,
) -> float:
    """
    Calculate cosine similarity between two face embeddings.
    """

    return float(
        cosine_similarity(
            [embedding1],
            [embedding2],
        )[0][0]
    )


def _classify_similarity(
    similarity: float,
    strong_threshold: float = STRONG_MATCH_THRESHOLD,
    borderline_threshold: float = BORDERLINE_THRESHOLD,
) -> str:
    """
    Classify a face similarity score against the given thresholds.

    >= strong_threshold
        STRONG_MATCH

    borderline_threshold - strong_threshold
        BORDERLINE

    < borderline_threshold
        STRONG_MISMATCH
    """

    if similarity >= strong_threshold:

        return "STRONG_MATCH"

    if similarity >= borderline_threshold:

        return "BORDERLINE"

    return "STRONG_MISMATCH"


# ============================================================
# PAIRWISE COMPARISON
# ============================================================

def _build_pairwise_comparisons(
    embeddings: Dict[str, np.ndarray],
    strong_threshold: float = STRONG_MATCH_THRESHOLD,
    borderline_threshold: float = BORDERLINE_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Compare every usable document with every other usable
    document.
    """

    files = sorted(embeddings.keys())

    results = []

    for file1, file2 in combinations(files, 2):

        similarity = _calculate_similarity(
            embeddings[file1],
            embeddings[file2],
        )

        classification = _classify_similarity(
            similarity,
            strong_threshold,
            borderline_threshold,
        )

        results.append(
            {
                "file1": file1,
                "file2": file2,
                "similarity": similarity,
                "classification": classification,
                "result": (
                    "SAME_PERSON"
                    if similarity
                    >= borderline_threshold
                    else "DIFFERENT_PERSON"
                ),
            }
        )

    return results


# ============================================================
# SIMILARITY MATRIX
# ============================================================

def _build_similarity_matrix(
    embeddings: Dict[str, np.ndarray],
) -> Dict[Tuple[str, str], float]:
    """
    Build a pairwise similarity matrix.
    """

    files = sorted(embeddings.keys())

    matrix = {}

    for file1, file2 in combinations(files, 2):

        matrix[(file1, file2)] = (
            _calculate_similarity(
                embeddings[file1],
                embeddings[file2],
            )
        )

    return matrix


def _get_similarity(
    matrix: Dict[Tuple[str, str], float],
    file1: str,
    file2: str,
) -> float:

    if file1 == file2:

        return 1.0

    key = (file1, file2)

    reverse_key = (file2, file1)

    if key in matrix:

        return matrix[key]

    return matrix[reverse_key]


# ============================================================
# DOCUMENT SUPPORT
# ============================================================

def _calculate_document_support(
    files: List[str],
    matrix: Dict[Tuple[str, str], float],
    strong_threshold: float = STRONG_MATCH_THRESHOLD,
    borderline_threshold: float = BORDERLINE_THRESHOLD,
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate how strongly each document is supported by the
    other documents, against the given thresholds.

    The important difference from the previous implementation
    is that a single weak pair does not automatically make
    every document suspicious.
    """

    support = {}

    for file1 in files:

        scores = []

        strong_matches = []
        borderline_matches = []
        mismatches = []

        for file2 in files:

            if file1 == file2:
                continue

            score = _get_similarity(
                matrix,
                file1,
                file2,
            )

            scores.append(score)

            if score >= strong_threshold:

                strong_matches.append(
                    {
                        "document": file2,
                        "similarity": score,
                    }
                )

            elif score >= borderline_threshold:

                borderline_matches.append(
                    {
                        "document": file2,
                        "similarity": score,
                    }
                )

            else:

                mismatches.append(
                    {
                        "document": file2,
                        "similarity": score,
                    }
                )

        support[file1] = {
            "mean_similarity": (
                float(np.mean(scores))
                if scores
                else None
            ),
            "minimum_similarity": (
                float(min(scores))
                if scores
                else None
            ),
            "maximum_similarity": (
                float(max(scores))
                if scores
                else None
            ),
            "strong_match_count": len(
                strong_matches
            ),
            "borderline_match_count": len(
                borderline_matches
            ),
            "mismatch_count": len(
                mismatches
            ),
            "strong_matches": strong_matches,
            "borderline_matches": borderline_matches,
            "mismatches": mismatches,
        }

    return support


# ============================================================
# DOMINANT IDENTITY GROUP
# ============================================================

def _find_dominant_identity_group(
    files: List[str],
    matrix: Dict[Tuple[str, str], float],
    strong_threshold: float = STRONG_MATCH_THRESHOLD,
    borderline_threshold: float = BORDERLINE_THRESHOLD,
) -> Tuple[List[str], List[str]]:
    """
    Identify the dominant identity group.

    A document joins a group when it has strong or borderline
    evidence connecting it to the group's documents.

    The algorithm is intentionally conservative:

    - It first looks for the strongest-supported document.
    - It then builds the identity group around that document.
    - Weak isolated comparisons do not automatically remove a
      document from the dominant identity group.

    Returns:

        dominant_documents,
        unsupported_documents
    """

    if len(files) < 2:

        return files, []

    support = _calculate_document_support(
        files,
        matrix,
        strong_threshold,
        borderline_threshold,
    )

    # --------------------------------------------------------
    # Select the strongest reference document.
    #
    # Priority:
    #   1. number of strong matches
    #   2. number of borderline matches
    #   3. mean similarity
    # --------------------------------------------------------

    reference = max(
        files,
        key=lambda file: (
            support[file]["strong_match_count"],
            support[file]["borderline_match_count"],
            support[file]["mean_similarity"]
            if support[file]["mean_similarity"]
            is not None
            else -1.0,
        ),
    )

    # --------------------------------------------------------
    # Build initial dominant group.
    #
    # Any document with at least borderline evidence against
    # the reference can enter the group.
    # --------------------------------------------------------

    dominant = {reference}

    for file in files:

        if file == reference:
            continue

        score = _get_similarity(
            matrix,
            reference,
            file,
        )

        if score >= borderline_threshold:

            dominant.add(file)

    # --------------------------------------------------------
    # Expand using strong evidence.
    #
    # This allows a document to belong to the same identity
    # group even if its direct comparison with the reference
    # is slightly below the strong threshold.
    #
    # This is important for cases such as:
    #
    # A ↔ B = 0.2826
    # A ↔ C = 0.5749
    # B ↔ C = 0.2075
    #
    # where the evidence indicates one identity group despite
    # variation caused by age, document quality, pose, etc.
    # --------------------------------------------------------

    changed = True

    while changed:

        changed = False

        for file in files:

            if file in dominant:
                continue

            strong_connections = 0
            borderline_connections = 0

            for group_file in dominant:

                score = _get_similarity(
                    matrix,
                    file,
                    group_file,
                )

                if score >= strong_threshold:

                    strong_connections += 1

                elif score >= borderline_threshold:

                    borderline_connections += 1

            # Strong evidence from at least one member is enough
            # to consider the document part of the dominant group.
            if strong_connections >= 1:

                dominant.add(file)
                changed = True

            # Otherwise require at least two borderline
            # connections. Not gated on a minimum file count: this
            # path can only trigger once the dominant group already
            # has >= 2 members for `file` to be borderline-connected
            # to (the initial pass above already admits anything
            # borderline-or-better against the reference alone), so
            # a 3-file application - reference + one initial member +
            # one file arriving here - is already a real, common case
            # for it, not just larger applications. An earlier
            # `len(files) >= 4` gate excluded exactly that case.
            elif borderline_connections >= 2:

                dominant.add(file)
                changed = True

    unsupported = [
        file
        for file in files
        if file not in dominant
    ]

    return (
        sorted(dominant),
        sorted(unsupported),
    )


# ============================================================
# APPLICATION DECISION
# ============================================================

def _make_application_decision(
    files: List[str],
    matrix: Dict[Tuple[str, str], float],
    strong_threshold: float = STRONG_MATCH_THRESHOLD,
    borderline_threshold: float = BORDERLINE_THRESHOLD,
) -> Tuple[
    str,
    Optional[bool],
    str,
    List[str],
]:
    """
    Determine the final application-level result.

    Decision philosophy:

    FACE_CONSISTENT
        The submitted documents provide sufficient evidence
        for one dominant identity group.

    REVIEW_REQUIRED
        There is a separate unsupported identity group or
        evidence is too weak/ambiguous to make a confident
        determination.

    INSUFFICIENT_EVIDENCE
        Fewer than two usable faces are available.

    IMPORTANT:

    A single weak pair does NOT automatically cause every
    document to become suspicious.

    This addresses the Gunter case where the same person's
    documents produced:

        0.1570
        0.7061
        0.2271

    The 0.1570 comparison is treated as weak evidence, but
    the complete evidence is considered before making the
    application decision.
    """

    if len(files) < 2:

        return (
            "INSUFFICIENT_EVIDENCE",
            None,
            "Fewer than two usable document faces were detected.",
            [],
        )

    dominant, unsupported = (
        _find_dominant_identity_group(
            files,
            matrix,
            strong_threshold,
            borderline_threshold,
        )
    )

    # --------------------------------------------------------
    # No meaningful dominant group.
    # --------------------------------------------------------

    if len(dominant) == 0:

        return (
            "REVIEW_REQUIRED",
            False,
            "No sufficiently supported identity group was detected.",
            sorted(files),
        )

    # --------------------------------------------------------
    # All documents belong to the dominant group.
    # --------------------------------------------------------

    if not unsupported:

        return (
            "FACE_CONSISTENT",
            True,
            (
                "The submitted documents provide sufficient "
                "facial evidence for one dominant identity group."
            ),
            [],
        )

    # --------------------------------------------------------
    # Some documents are outside the dominant identity group.
    # --------------------------------------------------------

    return (
        "REVIEW_REQUIRED",
        False,
        (
            "One or more documents contain facial evidence "
            "that is not sufficiently supported by the dominant "
            "identity group."
        ),
        unsupported,
    )


# ============================================================
# MAIN VERIFICATION FUNCTION
# ============================================================

def verify_documents(
    folder: str | os.PathLike,
    threshold: float = MATCH_THRESHOLD,
) -> Dict[str, Any]:
    """
    Verify whether document photographs contain faces that are
    sufficiently consistent with one identity.

    Parameters
    ----------
    folder:
        Folder containing uploaded document images.

    threshold:
        The borderline-match cutoff, used for every classification
        in this run (pairwise comparisons, document support, and
        the dominant-identity-group decision). The strong-match
        cutoff is derived as threshold + 0.10, preserving the
        module's two-tier design instead of collapsing to one
        cutoff. Defaults to MATCH_THRESHOLD from config.py.

    Returns
    -------
    dict
        JSON-friendly verification result.

    Important
    ---------
    This system evaluates facial consistency.

    It does NOT determine:

        - whether a document is genuine
        - whether a document is forged
        - whether an identity number is valid
        - whether a person is legally eligible
        - whether an account should be approved

    Final regulated decisions remain outside this verifier.
    """

    borderline_threshold = float(threshold)
    strong_threshold = borderline_threshold + _STRONG_MARGIN

    folder = Path(folder)

    document_paths = _read_documents(
        folder
    )

    detections: Dict[
        str,
        Dict[str, Any]
    ] = {}

    embeddings: Dict[
        str,
        np.ndarray
    ] = {}

    # ========================================================
    # FACE DETECTION + EMBEDDINGS
    # ========================================================

    for path in document_paths:

        image = cv2.imread(
            str(path)
        )

        if image is None:

            detections[path.name] = {
                "status": "IMAGE_READ_ERROR",
                "face_count": 0,
                "orientation": None,
            }

            continue

        (
            face,
            selected_image,
            orientation,
            face_count,
        ) = detect_best_face(
            image
        )

        if face is None:

            detections[path.name] = {
                "status": "NO_FACE",
                "face_count": 0,
                "orientation": orientation,
            }

            continue

        bbox = face.bbox.astype(
            int
        )

        x1, y1, x2, y2 = [
            int(value)
            for value in bbox
        ]

        area = int(
            max(0, x2 - x1)
            * max(0, y2 - y1)
        )

        detections[path.name] = {
            "status": "FACE_DETECTED",
            "face_count": int(
                face_count
            ),
            "orientation": orientation,
            "bbox": [
                x1,
                y1,
                x2,
                y2,
            ],
            "area": area,
            "detection_score": float(
                face.det_score
            ),
        }

        embeddings[path.name] = (
            np.asarray(
                face.embedding,
                dtype=np.float32,
            )
        )

    # ========================================================
    # USABLE DOCUMENTS
    # ========================================================

    usable_files = sorted(
        embeddings.keys()
    )

    if len(usable_files) < 2:

        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "same_person": None,
            "reason": (
                "Fewer than two usable document faces "
                "were detected."
            ),
            "threshold": float(
                threshold
            ),
            "strong_match_threshold": float(
                strong_threshold
            ),
            "borderline_threshold": float(
                borderline_threshold
            ),
            "documents_analysed": len(
                usable_files
            ),
            "documents": detections,
            "pairwise_comparisons": [],
            "document_consistency": {},
            "identity_group": [],
            "unsupported_documents": [],
            "suspicious_documents": [],
        }

    # ========================================================
    # SIMILARITY MATRIX
    # ========================================================

    similarity_matrix = (
        _build_similarity_matrix(
            embeddings
        )
    )

    # ========================================================
    # PAIRWISE RESULTS
    # ========================================================

    pairwise_comparisons = (
        _build_pairwise_comparisons(
            embeddings,
            strong_threshold,
            borderline_threshold,
        )
    )

    # ========================================================
    # DOCUMENT SUPPORT
    # ========================================================

    document_consistency = (
        _calculate_document_support(
            usable_files,
            similarity_matrix,
            strong_threshold,
            borderline_threshold,
        )
    )

    # ========================================================
    # FINAL DECISION
    # ========================================================

    (
        decision,
        same_person,
        reason,
        suspicious_documents,
    ) = _make_application_decision(
        usable_files,
        similarity_matrix,
        strong_threshold,
        borderline_threshold,
    )

    # ========================================================
    # DOCUMENT SUMMARIES
    # ========================================================

    document_summaries = []

    for document in usable_files:

        info = document_consistency[
            document
        ]

        document_summaries.append(
            {
                "document": document,
                "mean_similarity": info[
                    "mean_similarity"
                ],
                "minimum_similarity": info[
                    "minimum_similarity"
                ],
                "maximum_similarity": info[
                    "maximum_similarity"
                ],
                "strong_match_count": info[
                    "strong_match_count"
                ],
                "borderline_match_count": info[
                    "borderline_match_count"
                ],
                "mismatch_count": info[
                    "mismatch_count"
                ],
            }
        )

    # ========================================================
    # DETERMINE IDENTITY GROUP FOR OUTPUT
    # ========================================================

    identity_group, unsupported_documents = (
        _find_dominant_identity_group(
            usable_files,
            similarity_matrix,
            strong_threshold,
            borderline_threshold,
        )
    )

    # ========================================================
    # FINAL JSON-FRIENDLY RESULT
    # ========================================================

    return {
        "status": decision,

        "same_person": same_person,

        "reason": reason,

        "threshold": float(
            threshold
        ),

        "strong_match_threshold": float(
            strong_threshold
        ),

        "borderline_threshold": float(
            borderline_threshold
        ),

        "documents_analysed": len(
            usable_files
        ),

        "documents": detections,

        "pairwise_comparisons": (
            pairwise_comparisons
        ),

        "document_consistency": (
            document_consistency
        ),

        "document_summaries": (
            document_summaries
        ),

        "identity_group": (
            identity_group
        ),

        "unsupported_documents": (
            unsupported_documents
        ),

        "suspicious_documents": (
            suspicious_documents
        ),
    }


# ============================================================
# OPTIONAL DIRECT EXECUTION
# ============================================================
#
# This section is intentionally commented out.
#
# The GitHub application should import verify_documents()
# instead of automatically executing verification when this
# module is imported.
#
# Example:
#
# from verifier import verify_documents
#
# result = verify_documents(
#     "path/to/application_folder"
# )
#
# ============================================================