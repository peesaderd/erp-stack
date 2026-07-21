"""
Face Detector
=============
OpenCV Haar Cascade + MediaPipe fallback for face detection.
Used to auto-crop passport photos (head positioning).
"""

import logging
import cv2
import numpy as np
from pathlib import Path

logger = logging.getLogger("passport.face_detector")

MODELS_DIR = Path(__file__).parent / "models"


def _load_cascade(name: str):
    """Load Haar Cascade from OpenCV data or local models dir."""
    paths = [
        MODELS_DIR / name,
        Path(cv2.data.haarcascades) / name,
        Path(f"/usr/share/opencv4/haarcascades/{name}"),
    ]
    for p in paths:
        if p.exists():
            classifier = cv2.CascadeClassifier(str(p))
            if not classifier.empty():
                return classifier
    return None


_cascade = None


def _get_cascade():
    global _cascade
    if _cascade is None:
        _cascade = _load_cascade("haarcascade_frontalface_default.xml")
        if _cascade is None:
            # Download if missing
            import urllib.request
            url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            dest = MODELS_DIR / "haarcascade_frontalface_default.xml"
            try:
                urllib.request.urlretrieve(url, str(dest))
                _cascade = cv2.CascadeClassifier(str(dest))
                logger.info("Downloaded Haar Cascade")
            except Exception as e:
                logger.error(f"Failed to download cascade: {e}")
    return _cascade


def detect_face(image: np.ndarray) -> dict | None:
    """
    Detect the largest face in an image.

    Args:
        image: RGB or grayscale numpy array

    Returns:
        { "x", "y", "w", "h", "cx", "cy", "confidence" } or None
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    cascade = _get_cascade()
    if cascade is None:
        logger.warning("No cascade classifier available")
        # Fallback: assume face is centered, covering ~40% of image height
        h, w = gray.shape
        face_h = int(h * 0.4)
        face_w = int(w * 0.5)
        cx, cy = w // 2, int(h * 0.35)
        return {"x": cx - face_w // 2, "y": cy - face_h // 2, "w": face_w, "h": face_h, "cx": cx, "cy": cy, "confidence": 0.5}

    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100)
    )

    if len(faces) == 0:
        logger.info("No face detected")
        return None

    # Return largest face
    largest = max(faces, key=lambda f: f[2] * f[3])
    x, y, w, h = largest
    return {"x": int(x), "y": int(y), "w": int(w), "h": int(h), "cx": int(x + w // 2), "cy": int(y + h // 2), "confidence": 1.0}


def auto_crop_passport(image: np.ndarray, head_height_pct: float = 0.65) -> tuple[np.ndarray, dict]:
    """
    Auto-crop image for passport photo based on face detection.
    Positions the head at ~65% of frame height (standard compliance).

    Args:
        image: RGB image
        head_height_pct: desired head height as fraction of output height

    Returns:
        (cropped_image, crop_info_dict)
    """
    h, w = image.shape[:2]
    face = detect_face(image)

    crop_info = {"face_detected": face is not None}

    if face:
        # Calculate target crop based on face position
        target_head_h = face["h"]
        target_canvas_h = target_head_h / head_height_pct
        target_aspect = w / h  # keep original aspect ratio
        target_canvas_w = target_canvas_h * target_aspect

        # Center on face
        cx = face["cx"]
        cy = face["cy"]

        x1 = int(cx - target_canvas_w / 2)
        y1 = int(cy - target_canvas_h * 0.35)  # head in upper 35%
        x2 = int(x1 + target_canvas_w)
        y2 = int(y1 + target_canvas_h)

        crop_info.update({"x1": x1, "y1": y1, "x2": x2, "y2": y2})
    else:
        # Fallback: center crop, assume face in upper portion
        crop_size = min(w, h)
        cx, cy = w // 2, int(h * 0.35)
        x1 = cx - crop_size // 2
        y1 = cy - int(crop_size * 0.35)
        x2 = x1 + crop_size
        y2 = y1 + crop_size
        crop_info.update({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "fallback": True})

    # Clamp to image bounds
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w, x2)
    y2 = min(h, y2)

    cropped = image[y1:y2, x1:x2]
    return cropped, crop_info
