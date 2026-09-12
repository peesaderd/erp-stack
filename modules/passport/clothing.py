"""
Clothing Presets for Passport Photo
====================================
Male & Female clothing options for FLUX i2i prompt generation.
"""

import random

# ── Male Clothing ──────────────────────────────────────
MALE_CLOTHING = {
    "keep_original": {
        "name": "เก็บชุดเดิม",
        "prompt": "keep the person's original clothing exactly as it is, do not change clothing",
        "default": True,
    },
    "white_shirt": {
        "name": "เสื้อเชิ้ตสีขาว",
        "prompt": "white formal dress shirt, crisp white collar, professional business attire",
    },
    "blue_shirt": {
        "name": "เสื้อเชิ้ตสีน้ำเงิน",
        "prompt": "light blue formal dress shirt, professional business attire",
    },
    "black_suit": {
        "name": "สูทสีดำ + เนกไท",
        "prompt": "black formal suit jacket, white dress shirt, black necktie, professional business attire",
    },
    "gray_blazer": {
        "name": "เบลเซอร์สีเทา",
        "prompt": "gray blazer jacket, white dress shirt, professional business attire",
    },
    "navy_suit": {
        "name": "สูทสีกรมท่า",
        "prompt": "navy blue suit jacket, white dress shirt, professional business attire",
    },
}

# ── Female Clothing ────────────────────────────────────
# ชุดมืออาชีพสำหรับรูปติดบัตร (เปลี่ยนชุดออกให้หมด — 2026-09-12)
# ไม่มีชุดลำลอง (เสื้อยืด/สเวตเตอร์/linen) ในชุดนี้
FEMALE_CLOTHING = {
    "white_blouse": {
        "name": "เสื้อเบลาส์สีขาว",
        "prompt": "white formal blouse, tailored fit, professional business attire, modest neckline",
        "default": True,
    },
    "white_lace_blouse": {
        "name": "เสื้อลูกไม้สีขาวคอสูง",
        "prompt": "white floral lace blouse, long sleeves, high mock neckline with scalloped lace edge, slim tailored fit, elegant formal attire, modest",
    },
    "pink_blazer": {
        "name": "เบลเซอร์สีชมพู + เสื้อขาว",
        "prompt": "dusty pink rose tailored blazer jacket with notched lapel, three-quarter sleeves, worn over a plain white top, elegant formal attire, modest",
    },
    "black_blouse": {
        "name": "เสื้อเบลาส์สีดำ",
        "prompt": "black formal blouse, tailored fit, professional business attire, modest neckline",
    },
    "cream_suit": {
        "name": "สูทครีม + เสื้อเชิ้ตขาว",
        "prompt": "oversized cream ivory suit blazer with white collared shirt underneath, professional fashion attire, modest, elegant",
    },
    "navy_blazer": {
        "name": "เบลเซอร์กรมท่า + เสื้อเชิ้ตขาว",
        "prompt": "navy blue blazer jacket with white dress shirt underneath, professional business attire, modest neckline",
    },
    "white_turtleneck": {
        "name": "เสื้อคอเต่าสีขาว",
        "prompt": "white turtleneck top, professional business attire, modest neckline",
    },
    "keep_original": {
        "name": "เก็บชุดเดิม",
        "prompt": "keep the person's original clothing exactly as it is, do not change clothing",
    },
}

# ── Background Colors ──────────────────────────────────
BACKGROUNDS = {
    "light_blue": {"name": "สีฟ้าอ่อน", "hex": "#C4DCFF", "prompt": "soft light blue background", "type": "solid"},
    "white": {"name": "สีขาว", "hex": "#FFFFFF", "prompt": "solid white background", "type": "solid"},
    "light_gray": {"name": "สีเทาอ่อน", "hex": "#F0F0F0", "prompt": "light gray background", "type": "solid"},
    "gradient_blue": {"name": "ฟ้าสวย (gradient)", "hex": "#C4DCFF", "hex2": "#7FB5FF", "prompt": "soft blue gradient background", "type": "gradient", "css": "linear-gradient(180deg,#C4DCFF,#7FB5FF)"},
    "gradient_pink": {"name": "ชมพูหวาน (gradient)", "hex": "#FFD6E8", "hex2": "#FF9EC4", "prompt": "soft pink gradient background", "type": "gradient", "css": "linear-gradient(180deg,#FFD6E8,#FF9EC4)"},
    "gradient_gold": {"name": "ทองอ่อน (gradient)", "hex": "#FFF3D6", "hex2": "#FFD98A", "prompt": "soft gold gradient background", "type": "gradient", "css": "linear-gradient(180deg,#FFF3D6,#FFD98A)"},
    "circle_sky": {"name": "วงกลมฟ้า (circle)", "hex": "#FFFFFF", "hex2": "#7FB5FF", "prompt": "radial soft sky blue circle gradient background", "type": "gradient", "css": "radial-gradient(circle,#FFFFFF,#7FB5FF)"},
    "circle_pink": {"name": "วงกลมชมพู (circle)", "hex": "#FFFFFF", "hex2": "#FF9EC4", "prompt": "radial soft pink circle gradient background", "type": "gradient", "css": "radial-gradient(circle,#FFFFFF,#FF9EC4)"},
    "circle_gold": {"name": "วงกลมทอง (circle)", "hex": "#FFFDF5", "hex2": "#FFD98A", "prompt": "radial soft gold circle gradient background", "type": "gradient", "css": "radial-gradient(circle,#FFFDF5,#FFD98A)"},
    "circle_mint": {"name": "วงกลมมิ้นท์ (circle)", "hex": "#FFFFFF", "hex2": "#7FE0C3", "prompt": "radial soft mint circle gradient background", "type": "gradient", "css": "radial-gradient(circle,#FFFFFF,#7FE0C3)"},
}

# ── Public API ─────────────────────────────────────────

def get_clothing(gender: str, choice: str = "auto") -> dict:
    """
    Get clothing prompt for gender + choice.
    
    Args:
        gender: "male" or "female"
        choice: clothing key, "auto" (default), or "random"
    
    Returns:
        dict with keys: name, prompt
    """
    pool = MALE_CLOTHING if gender == "male" else FEMALE_CLOTHING
    
    if choice == "random":
        key = random.choice(list(pool.keys()))
        return pool[key]
    
    if choice == "auto":
        # Get default
        for k, v in pool.items():
            if v.get("default"):
                return v
        # Fallback to first
        return list(pool.values())[0]
    
    if choice in pool:
        return pool[choice]
    
    # Fallback to default
    return get_clothing(gender, "auto")


def list_clothing(gender: str) -> list:
    """List all clothing options for a gender."""
    pool = MALE_CLOTHING if gender == "male" else FEMALE_CLOTHING
    return [{"key": k, **v} for k, v in pool.items()]


def get_background(choice: str = "light_blue") -> dict:
    """Get background config."""
    return BACKGROUNDS.get(choice, BACKGROUNDS["light_blue"])


def list_backgrounds() -> list:
    """List all background options."""
    return [{"key": k, **v} for k, v in BACKGROUNDS.items()]
