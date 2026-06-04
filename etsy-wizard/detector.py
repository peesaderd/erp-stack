"""
detector.py — Fast Object/Hand Detection for Compositing Pipeline

2-Step Lightning Pipeline (no LLM involved):
1. MediaPipe Hands → detect hand keypoints (wrist, thumb, index finger)
   → return pinch point for product placement
2. YOLOv11 fallback → detect any object in scene → return center bbox

All runs on CPU, < 100ms per frame.
"""

import os
import numpy as np
from PIL import Image
import logging

logger = logging.getLogger("detector")

# ─── Hand Detector (MediaPipe) ─────────────────────────────────────────

class HandDetector:
    """MediaPipe Hands — 21 landmarks per hand, ~20ms on CPU"""

    def __init__(self):
        self._hands = None
        self._mp_hands = None

    def _lazy_init(self):
        if self._hands is not None:
            return
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        model_path = os.path.join(
            os.path.dirname(__file__),
            "hand_landmarker.task",
        )
        # Auto-download model if not present
        if not os.path.exists(model_path):
            import urllib.request
            url = (
                "https://storage.googleapis.com/mediapipe-models/"
                "hand_landmarker/hand_landmarker/float16/"
                "latest/hand_landmarker.task"
            )
            logger.info(f"Downloading MediaPipe model: {url}")
            urllib.request.urlretrieve(url, model_path)
            logger.info("MediaPipe model ✓")

        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=2,
            min_hand_detection_confidence=0.5,
        )
        self._hands = vision.HandLandmarker.create_from_options(options)

    def detect(self, image: Image.Image):
        """Detect hands → list of 21 landmarks [(x, y), ...]

        Landmark indices:
        0  = wrist
        4  = thumb tip
        8  = index finger tip
        12 = middle finger tip
        16 = ring finger tip
        20 = pinky tip
        """
        self._lazy_init()
        import mediapipe as mp
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.array(image.convert("RGB")))
        result = self._hands.detect(mp_img)

        if not result.hand_landmarks:
            return []

        h, w = image.size[1], image.size[0]
        hands = []
        for landmarks in result.hand_landmarks:
            points = []
            for lm in landmarks:
                points.append((int(lm.x * w), int(lm.y * h)))
            hands.append(points)
        return hands

    def get_pinch_point(self, image: Image.Image):
        """Fast entry point: returns (x, y) of pinch between thumb+index, or None"""
        hands = self.detect(image)
        if not hands:
            return None, None
        hand = hands[0]
        thumb_tip = hand[4]
        index_tip = hand[8]
        pinch_x = (thumb_tip[0] + index_tip[0]) // 2
        pinch_y = (thumb_tip[1] + index_tip[1]) // 2
        return pinch_x, pinch_y


# ─── Product Detector (YOLOv11) ────────────────────────────────────────

class ProductDetector:
    """YOLOv11 — 80-class COCO detection, ~5-15ms on CPU (nano model)

    Downloads model on first use (~5MB for yolo11n.pt).
    """

    def __init__(self, model_size: str = "n"):
        self._model = None
        self._model_size = model_size
        # COCO classes commonly found in product scenes
        self._product_classes = {
            24: "backpack", 25: "umbrella", 26: "handbag", 27: "tie",
            28: "suitcase", 29: "frisbee", 30: "skis", 31: "snowboard",
            32: "sports ball", 33: "kite", 34: "baseball bat",
            35: "baseball glove", 36: "skateboard", 37: "surfboard",
            38: "tennis racket", 39: "bottle", 40: "wine glass",
            41: "cup", 42: "fork", 43: "knife", 44: "spoon",
            45: "bowl", 46: "banana", 47: "apple", 48: "sandwich",
            49: "orange", 50: "broccoli", 51: "carrot", 52: "hot dog",
            53: "pizza", 54: "donut", 55: "cake", 56: "chair",
            57: "couch", 58: "potted plant", 59: "bed",
            60: "dining table", 61: "toilet", 62: "tv",
            63: "laptop", 64: "mouse", 65: "remote", 66: "keyboard",
            67: "cell phone", 68: "microwave", 69: "oven",
            70: "toaster", 71: "sink", 72: "refrigerator",
            73: "book", 74: "clock", 75: "vase", 76: "scissors",
            77: "teddy bear", 78: "hair drier", 79: "toothbrush",
        }

    def _lazy_init(self):
        if self._model is not None:
            return
        from ultralytics import YOLO
        logger.info(f"Loading YOLO11{self._model_size}...")
        self._model = YOLO(f"yolo11{self._model_size}.pt")
        logger.info("YOLO loaded ✓")

    def detect(
        self,
        image: Image.Image,
        confidence: float = 0.25,
        prefer_center: bool = True,
    ):
        """Detect objects → list of detections sorted by relevance

        Args:
            image: PIL Image
            confidence: min confidence threshold (0-1)
            prefer_center: if True, boost score of center-located objects

        Returns:
            List of dicts with keys: class, class_id, confidence, bbox,
            cx, cy, width, height
        """
        self._lazy_init()
        results = self._model(
            np.array(image.convert("RGB")),
            verbose=False,
        )

        img_w, img_h = image.size
        center_x, center_y = img_w / 2, img_h / 2

        detections = []
        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                if conf < confidence:
                    continue
                x1, y1, x2, y2 = map(float, box.xyxy[0])
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                w = x2 - x1
                h = y2 - y1

                # Score: base confidence * center-distance weight
                score = conf
                if prefer_center:
                    dist_ratio = (
                        abs(cx - center_x) / img_w
                        + abs(cy - center_y) / img_h
                    )
                    score *= max(0.3, 1.0 - dist_ratio)

                detections.append({
                    "class": r.names.get(cls, "unknown"),
                    "class_id": cls,
                    "confidence": conf,
                    "score": score,
                    "bbox": [x1, y1, x2, y2],
                    "cx": cx,
                    "cy": cy,
                    "width": w,
                    "height": h,
                })

        detections.sort(key=lambda d: d["score"], reverse=True)
        return detections

    def find_product_bbox(self, image: Image.Image, confidence: float = 0.25):
        """Fast entry point: returns best bbox or None

        Filters to 'product-like' COCO classes (bottle, cup, cell phone, etc.)
        """
        all_detections = self.detect(image, confidence=confidence)

        # Prefer product-like classes
        product_dets = [
            d for d in all_detections
            if d["class_id"] in self._product_classes
        ]
        if product_dets:
            return product_dets[0]

        # Fallback: best-scoring detection
        if all_detections:
            return all_detections[0]

        return None


# ─── Unified Entry Point ───────────────────────────────────────────────

# Singleton instances
_hand_detector = None
_product_detector = None


def _ensure_detectors():
    global _hand_detector, _product_detector
    if _hand_detector is None:
        _hand_detector = HandDetector()
    if _product_detector is None:
        _product_detector = ProductDetector()


def find_placement(scene_image: Image.Image):
    """2-Step Lightning Pipeline

    Step 1: MediaPipe Hands (~20ms CPU)
        → Detect hand → pinch point → return placement coords
    Step 2: YOLOv11 fallback (~15ms CPU)
        → Detect any product-like object → return bbox

    Returns dict:
        source: "mediapipe_hands" | "yolo" | None
        x: placement x (center of object/pinch)
        y: placement y
        width: estimated object width (for sizing)
        height: estimated object height
        confidence: detection confidence
        raw_data: full detection data for advanced usage
    """
    _ensure_detectors()

    # Step 1: MediaPipe Hands
    hands = _hand_detector.detect(scene_image)
    if hands:
        hand = hands[0]
        thumb_tip = hand[4]
        index_tip = hand[8]
        wrist = hand[0]

        pinch_x = (thumb_tip[0] + index_tip[0]) // 2
        pinch_y = (thumb_tip[1] + index_tip[1]) // 2

        # Estimate product size based on hand size
        hand_height = wrist[1] - thumb_tip[1]
        est_width = int(hand_height * 0.5)
        est_height = int(hand_height * 0.7)

        logger.info(
            f"📷 MediaPipe: pinch=({pinch_x},{pinch_y}) "
            f"wrist=({wrist[0]},{wrist[1]}) "
            f"size={est_width}x{est_height}"
        )

        return {
            "source": "mediapipe_hands",
            "x": pinch_x - est_width // 2,
            "y": pinch_y - est_height // 2 + int(hand_height * 0.15),
            "width": est_width,
            "height": est_height,
            "confidence": 1.0,
            "raw_data": {
                "pinch_x": pinch_x,
                "pinch_y": pinch_y,
                "wrist": wrist,
                "landmarks": hand,
                "hand_count": len(hands),
            },
        }

    # Step 2: YOLOv11 fallback
    bbox_data = _product_detector.find_product_bbox(scene_image)
    if bbox_data:
        logger.info(
            f"📦 YOLO: '{bbox_data['class']}' "
            f"({bbox_data['confidence']:.2f}) "
            f"at [{int(bbox_data['cx'])},{int(bbox_data['cy'])}]"
        )

        return {
            "source": "yolo",
            "x": bbox_data["bbox"][0],
            "y": bbox_data["bbox"][1],
            "width": bbox_data["width"],
            "height": bbox_data["height"],
            "confidence": bbox_data["confidence"],
            "raw_data": bbox_data,
        }

    logger.warning("⚠️ No hand or product detected")
    return None
