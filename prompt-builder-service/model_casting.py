# ─── Model Casting ───────────────────────────────────────────────
# สุ่มเลือกหน้าตา/การแต่งตัวของนางแบบให้หลากหลาย
# ═══════════════════════════════════════════════════════════════════════

import random
import logging
from typing import Dict

logger = logging.getLogger("model-casting")

MODEL_CASTS = [
    {
        "id": "clean_girl",
        "age": "22",
        "appearance": "สาวไทยผิวสวย หน้าใส ดูเป็นธรรมชาติ",
        "clothing": "เสื้อยืดสีขาวเรียบหรู",
        "style": "clean girl aesthetic, minimal makeup, dewy skin",
        "image_desc": "A beautiful young Thai woman, 22 years old, glowing dewy skin, minimal makeup, clean girl aesthetic, wearing a crisp white t-shirt, holding product at chest level with a bright natural smile, soft natural window lighting, warm inviting atmosphere",
    },
    {
        "id": "korean_trendy",
        "age": "23",
        "appearance": "สาวไทยสไตล์เกาหลี หน้าขาว ผิวใส",
        "clothing": "เสื้อกันหนาว oversized ตัวใหญ่ น่ารัก",
        "style": "Korean street fashion, trendy, youthful",
        "image_desc": "A young Thai woman, 23 years old, Korean-inspired style, glowing glass skin, oversized cozy sweater, holding product at chest level with a playful expression, trendy cafe background, soft warm lighting, trendy youthful atmosphere",
    },
    {
        "id": "chic_minimal",
        "age": "25",
        "appearance": "สาวไทยสไตล์ชิค เรียบหรู ดูแพง",
        "clothing": "ชุดสีโทนกลาง ดูมินิมอล แต่หรู",
        "style": "minimal chic, sophisticated, elegant",
        "image_desc": "An elegant Thai woman, 25 years old, sophisticated minimal style, wearing a neutral-toned fitted blouse, minimal gold jewelry, holding product at chest level with a confident calm expression, modern minimalist room with soft diffused lighting, premium elegant atmosphere",
    },
    {
        "id": "casual_cool",
        "age": "21",
        "appearance": "สาวไทยแนวแคชชวล เท่ สบายๆ",
        "clothing": "แจ็คเก็ตยีนส์ กางเกงขายาว ดูเท่",
        "style": "casual cool, relaxed, street style",
        "image_desc": "A Thai woman, 21 years old, relaxed street style, wearing a denim jacket, holding product casually at chest level, genuine friendly smile, authentic everyday setting, morning daylight, warm casual atmosphere",
    },
    {
        "id": "soft_romantic",
        "age": "22",
        "appearance": "สาวไทยสไตล์หวาน อ่อนโยน ผิวพรรณดี",
        "clothing": "เดรสลูกไม้สีพาสเทล ดูสุภาพออกแนวหวาน",
        "style": "romantic soft, feminine, dreamy",
        "image_desc": "A lovely young Thai woman, 22 years old, soft romantic style, wearing a pastel lace dress, holding product gently at chest level, sweet warm smile, fluffy natural texture, bedroom with warm golden sunset lighting, dreamy romantic atmosphere",
    },
    {
        "id": "fashion_forward",
        "age": "24",
        "appearance": "สาวไทยสายแฟชั่น ดูแพง ทันสมัย",
        "clothing": "เบลเซอร์สีครีม ดูดีมีสไตล์",
        "style": "modern chic, fashion forward, polished",
        "image_desc": "A stylish Thai woman, 24 years old, fashion-forward look, wearing a cream blazer, polished refined appearance, holding product at chest level with a natural sophisticated smile, modern loft with floor-to-ceiling windows, soft morning light, chic polished atmosphere",
    },
    {
        "id": "sporty_fresh",
        "age": "23",
        "appearance": "สาวไทยสายสุขภาพ ผิวมีน้ำมีนวล",
        "clothing": "ชุดกีฬาสีสันสดใส ดูมีพลัง",
        "style": "athleisure, fresh, energetic",
        "image_desc": "A fresh-faced Thai woman, 23 years old, healthy glowing skin, wearing a sporty pastel outfit, holding product at chest level with an energetic bright smile, bright airy room with plants, natural daylight, fresh vibrant atmosphere",
    },
    {
        "id": "campus_babe",
        "age": "20",
        "appearance": "สาวมหาลัย วัยรุ่น สดใส ผิวดี",
        "clothing": "เสื้อโปโลสีอ่อน กระโปรง ดูสุภาพสดใส",
        "style": "campus fresh, youthful, bright",
        "image_desc": "A young Thai college student, 20 years old, bright fresh complexion, wearing a light pastel polo and skirt, holding product at chest level with a cute bright expression, university campus or library background, natural daylight, youthful fresh atmosphere",
    },
]


def select_model_cast(category: str = "", product_name: str = "") -> Dict:
    """สุ่มเลือกนางแบบตามหมวดหมู่สินค้า
    
    Args:
        category: หมวดสินค้า (beauty, fashion, food, electronics ฯลฯ)
        product_name: ชื่อสินค้า (สำหรับ context)
    
    Returns:
        dict with model description fields
    """
    # Weight casts by category preference
    cat_prefs = {
        "beauty": ["clean_girl", "soft_romantic", "chic_minimal", "korean_trendy", "fashion_forward"],
        "fashion": ["fashion_forward", "chic_minimal", "casual_cool", "korean_trendy", "sporty_fresh"],
        "electronics": ["casual_cool", "campus_babe", "sporty_fresh", "korean_trendy"],
        "food": ["campus_babe", "casual_cool", "clean_girl", "soft_romantic"],
        "home": ["soft_romantic", "clean_girl", "chic_minimal", "mom_warm"],
        "health": ["sporty_fresh", "clean_girl", "chic_minimal", "fashion_forward"],
        "tools": ["casual_cool", "campus_babe", "sporty_fresh"],
    }
    
    pool_ids = cat_prefs.get(category, [c["id"] for c in MODEL_CASTS])
    # Filter to only existent casts
    pool = [c for c in MODEL_CASTS if c["id"] in pool_ids]
    if not pool:
        pool = MODEL_CASTS
    
    chosen = random.choice(pool)
    logger.info(f"Selected model cast '{chosen['id']}' for '{product_name}' (cat={category})")
    return {
        "model_age": chosen["age"],
        "model_appearance_th": chosen["appearance"],
        "model_clothing_th": chosen["clothing"],
        "model_style": chosen["style"],
        "image_description": chosen["image_desc"],
    }
