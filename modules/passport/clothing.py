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
FEMALE_CLOTHING = {
    "keep_original": {
        "name": "เก็บชุดเดิม",
        "prompt": "keep the person's original clothing exactly as it is, do not change clothing",
        "default": True,
    },
    "white_blouse": {
        "name": "เสื้อ.blouse สีขาว",
        "prompt": "white formal blouse, professional business attire, modest neckline",
    },
    "pink_blouse": {
        "name": "เสื้อ.blouse สีชมพู",
        "prompt": "light pink formal blouse, professional business attire, modest neckline",
    },
    "blue_blouse": {
        "name": "เสื้อ.blouse สีน้ำเงิน",
        "prompt": "light blue formal blouse, professional business attire, modest neckline",
    },
    "black_top": {
        "name": "เสื้อสีดำ",
        "prompt": "black formal top, professional business attire, modest neckline",
    },
    "white_turtleneck": {
        "name": "เสื้อคอกลมสีขาว",
        "prompt": "white turtleneck top, professional business attire, modest neckline",
    },
    "red_blouse": {
        "name": "เสื้อ.blouse สีแดง",
        "prompt": "red formal blouse, professional business attire, modest neckline",
    },
    "green_blouse": {
        "name": "เสื้อ.blouse สีเขียว",
        "prompt": "green formal blouse, professional business attire, modest neckline",
    },
    "purple_blouse": {
        "name": "เสื้อ.blouse สีม่วง",
        "prompt": "purple casual blouse, relaxed fit, modest neckline, everyday wear",
    },
    "casual_cotton_top": {
        "name": "เสื้อยืดคอกลม",
        "prompt": "casual cotton round-neck t-shirt, soft pastel color, relaxed fit, casual everyday wear",
    },
    "linen_blouse": {
        "name": "เสื้อเชิ้ต linen",
        "prompt": "casual linen blouse, relaxed fit, natural fabric texture, comfortable everyday wear",
    },
    "knit_sweater_top": {
        "name": "เสื้อกันหนาวถัก",
        "prompt": "casual knit sweater top, soft ribbed texture, comfortable relaxed fit, everyday casual wear",
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
