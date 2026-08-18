from __future__ import annotations

import cv2
import numpy as np

# Fixed proportional crop boxes (y1, y2, x1, x2 as fractions of image
# height/width), one per document type this system actually issues. Each
# was calibrated against the real "Penta Republic" fictional document
# templates this system's registries and onboarding flow are built
# against (Allard Clémence Vaudrey's passport, Neely Lugton's national ID,
# Melisent Poundsford's voter's card - see chat history), not a generic or
# unrelated document mockup - an earlier version of this module was
# calibrated against a different, unrelated document set and wrongly
# concluded only the passport carries a signature. All three document
# types confirmed here DO carry a real signature:
#   - passport: labeled "Holder's Signature / Signature du titulaire"
#   - national ID: labeled "CARDHOLDER SIGNATURE"
#   - voter's card: no label, but the signature is present at a
#     consistent position (bottom area, right of the personal-details
#     column)
_SIGNATURE_BOXES: dict[str, tuple[float, float, float, float]] = {
    "govt_id_international_passport": (0.705, 0.79, 0.48, 0.75),
    "govt_id_national_id_card": (0.755, 0.855, 0.62, 0.80),
    "govt_id_voters_card": (0.79, 0.90, 0.56, 0.88),
}


def crop_known_signature(bgr_image: np.ndarray, document_category: str) -> np.ndarray | None:
    """bgr_image: a full government-ID document page, as read by
    cv2.imread. Returns a grayscale crop of the signature region for any
    document_category with a calibrated box in _SIGNATURE_BOXES, or None
    for anything else (driver's license - no real sample has been seen for
    this system's version of that document type, so no box is calibrated;
    see crop_signature_best_effort for the fallback used there). Always
    "succeeds" in the sense of returning *a* crop at the fixed coordinates
    if the category is known - if a given document's layout differs from
    the sample this was calibrated against, the crop may miss the
    signature or include extra text, which preprocess.preprocess_signature
    and/or the resulting low similarity score will reflect rather than
    raising here."""
    box = _SIGNATURE_BOXES.get(document_category)
    if box is None:
        return None

    h, w = bgr_image.shape[:2]
    y1f, y2f, x1f, x2f = box
    y1, y2 = int(y1f * h), int(y2f * h)
    x1, x2 = int(x1f * w), int(x2f * w)
    crop = bgr_image[y1:y2, x1:x2]
    return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)


def crop_signature_best_effort(bgr_image: np.ndarray) -> np.ndarray | None:
    """For document types with no calibrated fixed signature position
    (currently: driver's license - no real sample of this system's version
    of that document has been seen). Falls back to a generic heuristic:
    find the largest elongated, moderately-sized dark ink contour in the
    image - roughly what a handwritten signature looks like as opposed to
    printed text (denser, more uniform stroke width, laid out in short
    line-height blocks) or a photo/logo (large filled regions). Returns
    None if nothing signature-shaped is found - callers should treat that
    as "no signature on this document" (not an error), same as the
    personal-ID registry checks already do when a field can't be parsed."""
    gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Merge nearby ink strokes into one blob per candidate signature so a
    # cursive signature's separate pen strokes count as one region instead
    # of many tiny ones.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 9))
    merged = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    h, w = gray.shape
    image_area = h * w
    best = None
    best_score = 0.0

    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = cw * ch
        area_fraction = area / image_area
        aspect_ratio = cw / ch if ch > 0 else 0

        # Signature-shaped: noticeably wider than tall, not tiny (a stray
        # mark) and not huge (a photo, a logo, a filled background block).
        if not (2.0 <= aspect_ratio <= 8.0):
            continue
        if not (0.005 <= area_fraction <= 0.15):
            continue

        # Prefer larger candidates among those that pass the shape filter.
        if area > best_score:
            best_score = area
            best = (x, y, cw, ch)

    if best is None:
        return None

    x, y, cw, ch = best
    pad_x, pad_y = int(cw * 0.1), int(ch * 0.2)
    x1, y1 = max(0, x - pad_x), max(0, y - pad_y)
    x2, y2 = min(w, x + cw + pad_x), min(h, y + ch + pad_y)
    return gray[y1:y2, x1:x2]
