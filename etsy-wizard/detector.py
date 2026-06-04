"""
detector.py — Lightning-Fast Product Placement Detection

2-Step Pipeline (no LLM, no MediaPipe, just YOLO):
1. YOLO Detection → find product-like objects (bottle, cup, phone, etc.)
2. YOLO Pose → find person wrist keypoints → estimate hand position

All models < 12MB total, runs ~30-300ms on CPU depending on image.
"""

import numpy as np
from PIL import Image
import logging

logger = logging.getLogger("detector")

# ─── YOLO Detector ─────────────────────────────────────────────────────

class YOLODetector:
    """YOLO detection (80 COCO classes) — finds product-like objects"""

    def __init__(self):
        self._model = None

    def _lazy_init(self):
        if self._model is not None:
            return
        from ultralytics import YOLO
        logger.info("Loading YOLO detection model...")
        self._model = YOLO("yolo11n.pt")
        logger.info("YOLO detection ✓")

    def detect_products(self, image: Image.Image, confidence: float = 0.25):
        """Find product-like objects → list of detections

        COCO classes commonly found as products in UGC scenes:
        bottle(39), cup(41), cell phone(67), book(73), etc.
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

                detections.append({
                    "class": r.names.get(cls, "unknown"),
                    "class_id": cls,
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2],
                    "cx": cx,
                    "cy": cy,
                    "width": w,
                    "height": h,
                })

        return detections

    def find_product_bbox(self, image: Image.Image, confidence: float = 0.25):
        """Fast entry: return best product bbox or None"""
        dets = self.detect_products(image, confidence)

        # Product-like classes (COCO classes commonly used as products)
        product_ids = {39, 41, 67, 73, 75, 76, 77, 43, 44, 45, 46, 47, 48,
                       49, 50, 51, 52, 53, 54, 55, 24, 25, 26, 27, 28, 62, 63,
                       64, 65, 66, 68, 69, 70, 71, 72, 74, 78, 79}
        person_id = 0

        # Priority 1: Product-like objects
        product_dets = [d for d in dets if d["class_id"] in product_ids]
        if product_dets:
            return product_dets[0]  # highest confidence

        # Priority 2: Person (use as last resort — fallback to pose)
        persons = [d for d in dets if d["class_id"] == person_id]
        if persons:
            return persons[0]

        return None


# ─── YOLO Pose Detector ────────────────────────────────────────────────

class YOLOPoseDetector:
    """YOLO pose estimation — detects person keypoints (wrists = hand position)"""

    COCO_KEYPOINTS = [
        "nose", "Leye", "Reye", "Lear", "Rear",
        "Lshoulder", "Rshoulder", "Lelbow", "Relbow",
        "Lwrist", "Rwrist", "Lhip", "Rhip",
        "Lknee", "Rknee", "Lankle", "Rankle",
    ]

    def __init__(self):
        self._model = None

    def _lazy_init(self):
        if self._model is not None:
            return
        from ultralytics import YOLO
        logger.info("Loading YOLO pose model...")
        self._model = YOLO("yolo11n-pose.pt")
        logger.info("YOLO pose ✓")

    def detect_hands(self, image: Image.Image):
        """Detect person → extract wrist positions → estimate hand coords

        Returns list of hand dicts:
            { "side": "left"|"right", "x": int, "y": int,
              "wrist_x": int, "wrist_y": int, "confidence": float }
        """
        self._lazy_init()
        results = self._model(
            np.array(image.convert("RGB")),
            verbose=False,
        )

        hands = []
        for r in results:
            if r.keypoints is None:
                continue
            for kp in r.keypoints:
                kp_data = kp.xy[0].cpu().numpy()
                if len(kp_data) < 11:
                    continue

                for side, wrist_idx, elbow_idx in [
                    ("left", 9, 7),
                    ("right", 10, 8),
                ]:
                    wx, wy = kp_data[wrist_idx][0], kp_data[wrist_idx][1]
                    ex, ey = kp_data[elbow_idx][0], kp_data[elbow_idx][1]

                    # Skip if wrist not detected (0,0)
                    if wx < 1 and wy < 1:
                        continue

                    # Calculate hand position: extend beyond wrist away from elbow
                    dx = wx - ex
                    dy = wy - ey
                    dist = np.sqrt(dx * dx + dy * dy)
                    if dist > 0:
                        hand_x = int(wx + (dx / dist) * dist * 0.3)
                        hand_y = int(wy + (dy / dist) * dist * 0.3)
                    else:
                        hand_x, hand_y = int(wx), int(wy)

                    hands.append({
                        "side": side,
                        "x": hand_x,
                        "y": hand_y,
                        "wrist_x": int(wx),
                        "wrist_y": int(wy),
                        "elbow_x": int(ex),
                        "elbow_y": int(ey),
                    })
        return hands


# ─── Unified Entry Point ───────────────────────────────────────────────

_detector = None
_pose_detector = None


def _ensure_loaded():
    global _detector
    if _detector is None:
        _detector = YOLODetector()


def _ensure_pose_loaded():
    global _pose_detector
    if _pose_detector is None:
        _pose_detector = YOLOPoseDetector()


def find_placement(scene_image: Image.Image):
    """2-Step Placement Pipeline (YOLO only, no MediaPipe)

    Strategy:
    1. Try YOLO product detection (ANY non-person, ≥ 0.3 conf)
       → Flux often generates a bottle/object even with "empty hand" prompts
       → The Flux-generated bottle is the BEST placement guide
    2. YOLO pose → wrist keypoints → hand position
       → Used when no product detected but person visible
    3. Person bbox → upper body estimate
    4. Center-bottom fallback

    Returns dict:
        source: "yolo_product" | "yolo_hand" | "person_bbox" | None
        x, y: placement top-left corner
        width, height: estimated product area
        confidence: detection confidence
    """
    _ensure_loaded()

    img_w, img_h = scene_image.size

    # Step 1: YOLO product detection (anything that looks like an object)
    # Flux often adds a product despite prompts — use ITS position
    product = _detector.find_product_bbox(scene_image)
    found_product = product and product["class_id"] != 0 and product["confidence"] >= 0.3

    if found_product:
        logger.info(
            f"📦 YOLO detected: '{product['class']}' "
            f"({product['confidence']:.2f}) "
            f"at cx={product['cx']:.0f} cy={product['cy']:.0f} "
            f"size {product['width']:.0f}x{product['height']:.0f}"
        )
        # Use product bbox CENTER for position, but CLAMP size to reasonable
        # YOLO bbox often includes arm+hand+bottle → too large
        # Product should be ~30% of image height at typical aspect ratio
        est_h = min(product["height"], int(img_h * 0.35))
        est_w = est_h * 0.45  # typical slim product aspect ratio
        cx = product["cx"]
        cy = product["cy"]
        # Position so product CENTER aligns with bbox center, but shifted UP
        # (bottle is at top of the detected area, arm/hand is below)
        return {
            "source": "yolo_product",
            "x": cx - est_w * 0.5,
            "y": cy - est_h * 0.7,  # shift up: bottle sits above wrist
            "width": est_w,
            "height": est_h,
            "confidence": product["confidence"],
            "cx": cx,
            "cy": cy,
        }

    # Step 2: YOLO pose — hands when no product detected in scene
    _ensure_pose_loaded()
    hands = _pose_detector.detect_hands(scene_image)
    if hands:
        best_hand = max(hands, key=lambda h: h["y"])
        est_h = img_h * 0.25
        est_w = est_h * 0.45
        logger.info(
            f"✋ YOLO hand: {best_hand['side']} "
            f"at ({best_hand['x']},{best_hand['y']})"
        )
        return {
            "source": "yolo_hand",
            "x": best_hand["x"] - est_w * 0.4,
            "y": best_hand["y"] - est_h * 0.3,
            "width": est_w,
            "height": est_h,
            "confidence": 0.8,
            "cx": best_hand["x"],
            "cy": best_hand["y"],
            "hand_side": best_hand["side"],
        }

    # Step 3: Person bbox (no hands, no product detected)
    if product and product["class_id"] == 0:
        logger.info(f"🧑 Person but no hands, using upper body")
        return {
            "source": "person_bbox",
            "x": product["bbox"][0] + product["width"] * 0.2,
            "y": product["bbox"][1] + product["height"] * 0.2,
            "width": product["width"] * 0.6,
            "height": product["height"] * 0.3,
            "confidence": product["confidence"],
            "cx": product["cx"],
            "cy": product["cy"] + product["height"] * 0.15,
        }

    logger.warning("⚠️ Nothing detected in image")
    return None
