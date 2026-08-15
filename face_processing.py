"""
face_processing.py
-------------------
Face detection, landmark extraction, and pre-match quality gating.

Uses InsightFace's FaceAnalysis pipeline (SCRFD detector) which returns,
per detected face: bounding box, 5-point landmarks, pose angles, detection
score, and (from the buffalo_l pack) an embedding + age/gender estimate
in a single forward pass. We reuse that pass rather than running separate
models, since buffalo_l already bundles everything this system needs.
"""

import logging
from dataclasses import dataclass
from typing import Optional, List

import cv2
import numpy as np
from insightface.app import FaceAnalysis

import config

logger = logging.getLogger("face_verification.face_processing")

_face_app: Optional[FaceAnalysis] = None


@dataclass
class ProcessedFace:
    embedding: np.ndarray
    bbox: np.ndarray
    det_score: float
    estimated_age: float
    yaw_degrees: float
    quality_ok: bool
    quality_reason: Optional[str] = None


def get_face_app() -> FaceAnalysis:
    """Lazily loads the InsightFace model pack (downloads on first run)."""
    global _face_app
    if _face_app is None:
        logger.info("Loading InsightFace model pack: %s", config.INSIGHTFACE_MODEL_NAME)
        _face_app = FaceAnalysis(
            name=config.INSIGHTFACE_MODEL_NAME,
            providers=config.INSIGHTFACE_PROVIDERS,
        )
        _face_app.prepare(ctx_id=0, det_size=config.DETECTION_SIZE)
    return _face_app


def _laplacian_blur_score(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def _estimate_yaw(landmarks: np.ndarray) -> float:
    """
    Rough yaw estimate from 5-point landmarks (eyes, nose, mouth corners)
    using the horizontal asymmetry between eye-to-nose distances.
    Good enough as a coarse pose-quality gate, not a precise head-pose model.
    """
    left_eye, right_eye, nose = landmarks[0], landmarks[1], landmarks[2]
    left_dist = np.linalg.norm(nose - left_eye)
    right_dist = np.linalg.norm(nose - right_eye)
    # ratio close to 1 => frontal; skewed ratio => turned head
    ratio = (left_dist - right_dist) / (left_dist + right_dist + 1e-6)
    yaw_approx_degrees = ratio * 90  # heuristic scaling, not a calibrated angle
    return float(yaw_approx_degrees)


def process_image(image_path: str, label: str = "") -> ProcessedFace:
    """
    Runs detection + embedding + age estimate on the single largest/most
    confident face in the image, and evaluates it against quality gates.

    `label` is just for logging (e.g. "recent_photo" / "id_document").
    """
    app = get_face_app()
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not read image at {image_path}")

    faces = app.get(image)
    if not faces:
        return ProcessedFace(
            embedding=None, bbox=None, det_score=0.0, estimated_age=None,
            yaw_degrees=None, quality_ok=False, quality_reason="no_face_detected",
        )

    # Pick the highest-confidence face (documents/photos should contain exactly one)
    face = max(faces, key=lambda f: f.det_score)

    bbox = face.bbox.astype(int)
    face_w = bbox[2] - bbox[0]
    face_h = bbox[3] - bbox[1]

    yaw = _estimate_yaw(face.kps) if face.kps is not None else 0.0
    blur_score = _laplacian_blur_score(image)

    quality_ok = True
    reason = None

    if face.det_score < config.DETECTION_CONFIDENCE_MIN:
        quality_ok, reason = False, "low_detection_confidence"
    elif min(face_w, face_h) < config.MIN_FACE_PIXELS:
        quality_ok, reason = False, "face_too_small"
    elif blur_score < config.BLUR_VARIANCE_THRESHOLD:
        quality_ok, reason = False, "image_too_blurry"
    elif abs(yaw) > config.MAX_POSE_YAW_DEGREES:
        quality_ok, reason = False, "extreme_head_pose"

    logger.info(
        "[%s] det_score=%.3f face_size=%dx%d blur=%.1f yaw=%.1f quality_ok=%s (%s)",
        label, face.det_score, face_w, face_h, blur_score, yaw, quality_ok, reason,
    )

    return ProcessedFace(
        embedding=face.normed_embedding,   # 512-d, L2-normalised => cosine sim = dot product
        bbox=bbox,
        det_score=float(face.det_score),
        estimated_age=float(getattr(face, "age", None)) if getattr(face, "age", None) is not None else None,
        yaw_degrees=yaw,
        quality_ok=quality_ok,
        quality_reason=reason,
    )
