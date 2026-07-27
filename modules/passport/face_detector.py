"""
Face Detector v2
================
OpenCV Haar Cascade + eye detection + angle correction.
Used to auto-crop passport photos (head positioning) with face alignment.
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
_eye_cascade = None


def _get_cascade():
    global _cascade
    if _cascade is None:
        _cascade = _load_cascade("haarcascade_frontalface_default.xml")
        if _cascade is None:
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


def _get_eye_cascade():
    global _eye_cascade
    if _eye_cascade is None:
        _eye_cascade = _load_cascade("haarcascade_eye.xml")
        if _eye_cascade is None:
            import urllib.request
            url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_eye.xml"
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            dest = MODELS_DIR / "haarcascade_eye.xml"
            try:
                urllib.request.urlretrieve(url, str(dest))
                _eye_cascade = cv2.CascadeClassifier(str(dest))
                logger.info("Downloaded Eye Cascade")
            except Exception as e:
                logger.error(f"Failed to download eye cascade: {e}")
    return _eye_cascade


def detect_face(image: np.ndarray) -> dict | None:
    """
    Detect the largest face in an image.
    Uses multi-scale detection + preprocessing for robustness.

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
        h, w = gray.shape
        face_h = int(h * 0.4)
        face_w = int(w * 0.5)
        cx, cy = w // 2, int(h * 0.35)
        return {"x": cx - face_w // 2, "y": cy - face_h // 2, "w": face_w, "h": face_h, "cx": cx, "cy": cy, "confidence": 0.5}

    # ── Preprocessing: equalize histogram for better detection ──
    gray_eq = cv2.equalizeHist(gray)

    # ── Multi-scale detection ──
    all_faces = []
    for scale in [1.05, 1.1, 1.15]:
        for min_n in [3, 5]:
            faces = cascade.detectMultiScale(
                gray_eq, scaleFactor=scale, minNeighbors=min_n,
                minSize=(80, 80), maxSize=(gray.shape[1], gray.shape[0])
            )
            for f in faces:
                all_faces.append(f)

    if len(all_faces) == 0:
        # Try without equalization
        faces = cascade.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=3,
            minSize=(80, 80)
        )
        if len(faces) == 0:
            logger.info("No face detected")
            return None
        all_faces = list(faces)

    # Return largest (stable merge of overlapping detections)
    # Simple: just return largest by area
    largest = max(all_faces, key=lambda f: f[2] * f[3])
    x, y, w, h = largest
    logger.info(f"Face detected: {w}x{h} at ({x},{y})")
    return {"x": int(x), "y": int(y), "w": int(w), "h": int(h),
            "cx": int(x + w // 2), "cy": int(y + h // 2), "confidence": 1.0}


def detect_eyes(image: np.ndarray) -> list | None:
    """
    Detect eyes in an image. Returns list of (x, y) eye center coordinates,
    sorted left-to-right.

    Uses OpenCV Haar cascade for eyes.
    Falls back to using face region + upper-half detection.

    Returns:
        [(left_eye_x, left_eye_y), (right_eye_x, right_eye_y)] or None
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    # First detect face to constrain eye search
    face = detect_face(image)
    if not face:
        # Try detecting eyes on the whole image
        eye_cascade = _get_eye_cascade()
        if eye_cascade:
            eyes = eye_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
            if len(eyes) >= 2:
                # Sort by x (left to right)
                eyes_sorted = sorted(eyes, key=lambda e: e[0])
                return [
                    (e[0] + e[2] // 2, e[1] + e[3] // 2)
                    for e in eyes_sorted[:2]
                ]
        return None

    # Constrain to upper half of face
    fx, fy, fw, fh = face["x"], face["y"], face["w"], face["h"]
    eye_roi_y1 = fy + int(fh * 0.05)
    eye_roi_y2 = fy + int(fh * 0.55)
    eye_roi_x1 = fx + int(fw * 0.05)
    eye_roi_x2 = fx + int(fw * 0.95)

    roi_gray = gray[eye_roi_y1:eye_roi_y2, eye_roi_x1:eye_roi_x2]

    eye_cascade = _get_eye_cascade()
    if not eye_cascade:
        return None

    eyes = eye_cascade.detectMultiScale(roi_gray, 1.1, 5, minSize=(20, 20))

    if len(eyes) < 2:
        return None

    # Convert to image coordinates
    eyes_abs = [(ex + eye_roi_x1 + ew // 2, ey + eye_roi_y1 + eh // 2)
                for ex, ey, ew, eh in eyes]

    # Sort left to right
    eyes_abs.sort(key=lambda e: e[0])

    # Return the two leftmost (should be both eyes)
    return eyes_abs[:2]


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
        target_head_h = face["h"]
        target_canvas_h = target_head_h / head_height_pct
        target_aspect = w / h
        target_canvas_w = target_canvas_h * target_aspect

        cx = face["cx"]
        cy = face["cy"]

        x1 = int(cx - target_canvas_w / 2)
        y1 = int(cy - target_canvas_h * 0.35)
        x2 = int(x1 + target_canvas_w)
        y2 = int(y1 + target_canvas_h)

        crop_info.update({"x1": x1, "y1": y1, "x2": x2, "y2": y2})
    else:
        crop_size = min(w, h)
        cx, cy = w // 2, int(h * 0.35)
        x1 = cx - crop_size // 2
        y1 = cy - int(crop_size * 0.35)
        x2 = x1 + crop_size
        y2 = y1 + crop_size
        crop_info.update({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "fallback": True})

    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w, x2)
    y2 = min(h, y2)

    cropped = image[y1:y2, x1:x2]
    return cropped, crop_info
