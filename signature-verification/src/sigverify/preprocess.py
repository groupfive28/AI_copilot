from __future__ import annotations

import cv2
import numpy as np

# Reimplements luizgh/sigver's sigver/preprocessing/normalize.py using
# OpenCV instead of scikit-image (opencv-python is already a dependency
# elsewhere in this stack - see ../face-verification/requirements.txt -
# scikit-image would be a new one for just this). Same algorithm: OTSU
# threshold to find the signature's ink pixels, crop tightly to them, center
# on a blank canvas, invert (ink becomes bright on a dark background - what
# the network was trained on), then resize+center-crop to the network's
# fixed input size.
_CANVAS_SIZE = (840, 1360)  # (H, W) - must be larger than any real crop
_RESIZE_SIZE = (170, 242)  # (H, W)
_INPUT_SIZE = (150, 220)  # (H, W) - SigNet's actual input size


def preprocess_signature(gray: np.ndarray) -> np.ndarray:
    """gray: any-size single-channel (grayscale) uint8 image containing
    (ideally) just a signature. Returns a (150, 220) uint8 array ready for
    model.embed(). Raises ValueError if no ink is found at all (a blank or
    near-blank crop) - callers should treat that as "couldn't extract a
    signature" (status="error"/"not_found"), not feed it through anyway."""
    gray = gray.astype(np.uint8)
    centered = _normalize_image(gray, _CANVAS_SIZE)
    inverted = 255 - centered
    resized = _resize_image(inverted, _RESIZE_SIZE)
    cropped = _crop_center(resized, _INPUT_SIZE)
    return cropped


def _normalize_image(img: np.ndarray, canvas_size: tuple[int, int]) -> np.ndarray:
    blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=2)
    threshold, _ = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    binarized = blurred > threshold
    rows, cols = np.where(binarized == 0)  # ink pixels (below threshold = dark = ink)
    if rows.size == 0 or cols.size == 0:
        raise ValueError("no ink pixels found - image appears blank")

    r_min, r_max = int(rows.min()), int(rows.max())
    c_min, c_max = int(cols.min()), int(cols.max())
    if r_max <= r_min or c_max <= c_min:
        raise ValueError("ink bounding box is degenerate - image appears blank")

    r_center = int(rows.mean() - r_min)
    c_center = int(cols.mean() - c_min)
    cropped = img[r_min:r_max, c_min:c_max]

    max_rows, max_cols = canvas_size
    img_rows, img_cols = cropped.shape

    r_start = max_rows // 2 - r_center
    c_start = max_cols // 2 - c_center

    if img_rows > max_rows:
        difference = img_rows - max_rows
        crop_start = difference // 2
        cropped = cropped[crop_start:crop_start + max_rows, :]
        img_rows = max_rows
        r_start = 0
    else:
        extra_r = (r_start + img_rows) - max_rows
        if extra_r > 0:
            r_start -= extra_r
        r_start = max(r_start, 0)

    if img_cols > max_cols:
        difference = img_cols - max_cols
        crop_start = difference // 2
        cropped = cropped[:, crop_start:crop_start + max_cols]
        img_cols = max_cols
        c_start = 0
    else:
        extra_c = (c_start + img_cols) - max_cols
        if extra_c > 0:
            c_start -= extra_c
        c_start = max(c_start, 0)

    normalized = np.full((max_rows, max_cols), 255, dtype=np.uint8)
    normalized[r_start:r_start + img_rows, c_start:c_start + img_cols] = cropped
    normalized[normalized > threshold] = 255
    return normalized


def _resize_image(img: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    height, width = size
    width_ratio = img.shape[1] / width
    height_ratio = img.shape[0] / height

    if width_ratio > height_ratio:
        resize_height = height
        resize_width = int(round(img.shape[1] / height_ratio))
    else:
        resize_width = width
        resize_height = int(round(img.shape[0] / width_ratio))

    resized = cv2.resize(img, (resize_width, resize_height), interpolation=cv2.INTER_AREA)

    if width_ratio > height_ratio:
        start = int(round((resize_width - width) / 2.0))
        return resized[:, start:start + width]
    else:
        start = int(round((resize_height - height) / 2.0))
        return resized[start:start + height, :]


def _crop_center(img: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    start_y = (img.shape[0] - size[0]) // 2
    start_x = (img.shape[1] - size[1]) // 2
    return img[start_y:start_y + size[0], start_x:start_x + size[1]]
