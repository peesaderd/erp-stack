"""
Clothing Presets for Passport Photo
====================================
Male & Female clothing options for FLUX i2i prompt generation.
"""

import random

# ── Pose directive (owner 2026-09-12) ──────────────────
# Owner: "ตัว model ไม่หันตรง หน้าตรงแต่ตัวเอียง" — the model's BODY (shoulders/
# torso) turns 3/4 while the head stays frontal. Cause: the clothing prompts
# describe the GARMENT only (product-shot phrasing) and carry no pose/facing
# clause, so FLUX renders the garment front-on and rotates the torso.
# This clause pins the WHOLE body frontal (head AND shoulders square to camera,
# symmetric) WITHOUT any face-retouching words — so it does not re-trigger the
# V3 over-beautify problem the owner rejected.
POSEFRONT = ("subject facing the camera directly with the entire body frontal, "
             "shoulders square and level to the camera, symmetric posture, "
             "head and torso pointing straight ahead, both shoulders equally visible, "
             "both shoulders at the same distance from the camera, not rotated, not turned, "
             "no three-quarter body angle, fully front-on pose")

# ── Male Clothing ──────────────────────────────────────
MALE_CLOTHING = {
    "keep_original": {
        "name": "เก็บชุดเดิม",
        "prompt": "keep the person's original clothing exactly as it is, do not change clothing",
        "default": True,
    },
    "white_shirt": {
        "name": "เสื้อเชิ้ตสีขาว",
        "prompt": f"white formal dress shirt, crisp white collar, professional business attire, {POSEFRONT}",
    },
    "blue_shirt": {
        "name": "เสื้อเชิ้ตสีน้ำเงิน",
        "prompt": f"light blue formal dress shirt, professional business attire, {POSEFRONT}",
    },
    "black_suit": {
        "name": "สูทสีดำ + เนกไท",
        "prompt": f"black formal suit jacket, white dress shirt, black necktie, professional business attire, {POSEFRONT}",
    },
    "gray_blazer": {
        "name": "เบลเซอร์สีเทา",
        "prompt": f"gray blazer jacket, white dress shirt, professional business attire, {POSEFRONT}",
    },
    "navy_suit": {
        "name": "สูทสีกรมท่า",
        "prompt": f"navy blue suit jacket, white dress shirt, professional business attire, {POSEFRONT}",
    },
}

# ── Female Clothing ────────────────────────────────────
# ชุดมืออาชีพสำหรับรูปติดบัตร (เปลี่ยนชุดออกให้หมด — 2026-09-12)
# ไม่มีชุดลำลอง (เสื้อยืด/สเวตเตอร์/linen) ในชุดนี้
FEMALE_CLOTHING = {
    "white_blouse": {
        "name": "เสื้อเบลาส์สีขาว",
        "prompt": f"white formal blouse, tailored fit, professional business attire, modest neckline, {POSEFRONT}",
        "default": True,
    },
    "white_lace_blouse": {
        "name": "เสื้อลูกไม้สีขาวคอสูง",
        "prompt": f"white floral lace blouse, long sleeves, high mock neckline with scalloped lace edge, slim tailored fit, elegant formal attire, modest, {POSEFRONT}",
        # Slim high-neck lace garment drifts to a 3/4 torso at low strength —
        # raise the Step-2 floor for this item so the frontal pose holds.
        "strength_floor": 0.70,
    },
    "pink_blazer": {
        "name": "เบลเซอร์สีชมพู + เสื้อขาว",
        "prompt": f"dusty pink rose tailored blazer jacket with notched lapel, three-quarter sleeves, worn over a plain white top, elegant formal attire, modest, {POSEFRONT}",
    },
    "black_blouse": {
        "name": "เสื้อเบลาส์สีดำ",
        "prompt": f"black formal blouse, tailored fit, professional business attire, modest neckline, {POSEFRONT}",
    },
    "cream_suit": {
        "name": "สูทครีม + เสื้อเชิ้ตขาว",
        "prompt": f"oversized cream ivory suit blazer with white collared shirt underneath, professional fashion attire, modest, elegant, {POSEFRONT}",
    },
    "navy_blazer": {
        "name": "เบลเซอร์กรมท่า + เสื้อเชิ้ตขาว",
        "prompt": f"navy blue blazer jacket with white dress shirt underneath, professional business attire, modest neckline, {POSEFRONT}",
    },
    "white_turtleneck": {
        "name": "เสื้อคอเต่าสีขาว",
        "prompt": f"white turtleneck top, professional business attire, modest neckline, {POSEFRONT}",
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
