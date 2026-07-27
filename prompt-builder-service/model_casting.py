# ─── Model Casting ───────────────────────────────────────────────
# สุ่มเลือกหน้าตา/การแต่งตัวของนางแบบให้หลากหลาย
# โหลดข้อมูลจาก model_casts.json — แก้ JSON ได้เลยไม่ต้องแตะ code
# ═══════════════════════════════════════════════════════════════════════

import os
import json
import random
import logging
from typing import Dict, List

logger = logging.getLogger("model-casting")

_CASTS_DIR = os.path.dirname(os.path.abspath(__file__))
_CASTS_FILE = os.path.join(_CASTS_DIR, "model_casts.json")

# Cache
_MODEL_CASTS: List[Dict] = []
# History file for draw-without-replacement
_HISTORY_FILE: str = os.environ.get("MODEL_CAST_HISTORY", os.path.join(_CASTS_DIR, "model_cast_history.json"))
_HISTORY_MAX: int = 3  # avoid last 3 models

_CAT_PREFS: Dict[str, List[str]] = {
    "beauty": [
        "clean_girl", "thai_trendy", "chic_minimal", "casual_cool",
        "soft_romantic", "fashion_forward", "sporty_fresh", "campus_babe",
        "mature_elegant", "grungy_city", "preppy_university", "luxe_aspirational",
    ],
    "fashion": [
        "fashion_forward", "chic_minimal", "casual_cool", "thai_trendy",
        "sporty_fresh", "mature_elegant", "luxe_aspirational", "grungy_city",
    ],
    "electronics": ["casual_cool", "campus_babe", "sporty_fresh", "thai_trendy", "grungy_city"],
    "food": ["campus_babe", "casual_cool", "clean_girl", "soft_romantic", "preppy_university"],
    "home": ["soft_romantic", "clean_girl", "chic_minimal", "mature_elegant"],
    "health": ["sporty_fresh", "clean_girl", "chic_minimal", "fashion_forward", "mature_elegant"],
    "tools": ["casual_cool", "campus_babe", "sporty_fresh"],
}


def _load_casts() -> List[Dict]:
    """โหลดข้อมูลนางแบบจาก JSON file (มี cache)"""
    global _MODEL_CASTS
    if _MODEL_CASTS:
        return _MODEL_CASTS
    try:
        if os.path.exists(_CASTS_FILE):
            with open(_CASTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _MODEL_CASTS = data.get("casts", [])
            logger.info(f"Loaded {len(_MODEL_CASTS)} model casts from {_CASTS_FILE}")
        else:
            logger.warning(f"{_CASTS_FILE} not found, using built-in defaults")
    except Exception as e:
        logger.error(f"Failed to load {_CASTS_FILE}: {e}")

    if not _MODEL_CASTS:
        # Fallback — 1 default
        _MODEL_CASTS = [{
            "id": "default",
            "age": "22",
            "appearance": "สาวไทยผิวสวย หน้าใส",
            "clothing": "เสื้อผ้าสไตล์ธรรมชาติ",
            "style": "natural, clean",
            "image_desc": "A beautiful young Thai woman, 22 years old, glowing dewy skin, natural look, holding product at chest level with a bright smile, soft lighting, warm atmosphere",
        }]
    return _MODEL_CASTS


def _load_history() -> list:
    """Load recently-used model IDs from history file to avoid repeats."""
    try:
        if os.path.exists(_HISTORY_FILE):
            with open(_HISTORY_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_history(history: list):
    """Save recently-used model IDs."""
    try:
        with open(_HISTORY_FILE, "w") as f:
            json.dump(history[-_HISTORY_MAX:], f)
    except Exception as e:
        logger.warning(f"Failed to save model cast history: {e}")


def select_model_cast(category: str = "", product_name: str = "") -> Dict:
    """สุ่มเลือกนางแบบตามหมวดหมู่สินค้า — draw without replacement
        ใช้ history file เพื่อไม่ให้ซ้ำ 3 ตัวล่าสุด

    Args:
        category: หมวดสินค้า (beauty, fashion, food, electronics ฯลฯ)
        product_name: ชื่อสินค้า (สำหรับ context)

    Returns:
        dict with model description fields
    """
    casts = _load_casts()
    pool_ids = _CAT_PREFS.get(category, [c["id"] for c in casts])
    pool = [c for c in casts if c["id"] in pool_ids]
    if not pool:
        pool = casts

    # Draw without replacement: exclude recently-used models
    history = _load_history()
    available = [c for c in pool if c["id"] not in history]
    if not available:
        # All used up — reset history
        available = pool
        history = []

    chosen = random.choice(available)

    # Update history
    history.append(chosen["id"])
    _save_history(history)

    logger.info(f"Selected model cast '{chosen['id']}' for '{product_name}' (cat={category}, history={history})")
    return {
        "model_age": chosen["age"],
        "model_appearance_th": chosen.get("appearance", ""),
        "model_clothing_th": chosen.get("clothing", ""),
        "model_style": chosen.get("style", ""),
        "image_description": chosen["image_desc"],
    }


def get_all_casts() -> List[Dict]:
    """ดึงรายการนางแบบทั้งหมด (ใช้ในหน้า config/UI)"""
    return _load_casts()
