"""
UGC Presets, Styles & Combos — Central Configuration
Recipe Presets (12), Content Styles (9), Recommended Combos

This replaces the flat 11-style system with structured:
  Preset → Style → Shot Plan → Prompt
"""

# ─────────────────────────────────────────────────────────────────────
# 1. RECIPE PRESETS (หมวดหมู่สินค้า & Mood)
# ─────────────────────────────────────────────────────────────────────
UGC_PRESETS = {
    "skincare_glow": {
        "name": "Skincare Glow",
        "description": "Soft luxury vibes, calm music, slow transitions",
        "mood": "soft, luxurious, calming",
        "lighting": "soft daylighting, clean shadows",
        "shot_dynamics": "cinematic, slow-motion",
        "camera_motion": "slow push in, gentle pan, soft rack focus",
        "bgm_style": "chill_loft",
        "sound_style": "ambient",
        "compatible_categories": ["beauty", "health"],
        "compatible_styles": ["holding", "review", "usage", "talking_head"],
        "compatible_personas": ["calm_professional", "minimalist_zen", "energetic_young"],
    },
    "gadget_unboxing": {
        "name": "Gadget Unboxing",
        "description": "Fast-paced, energetic, quick cuts",
        "mood": "energetic, exciting, tech-forward",
        "lighting": "high contrast, sharp focus, studio lighting",
        "shot_dynamics": "dynamic pan/zoom",
        "camera_motion": "fast whip pans, punch-in zooms, quick cuts",
        "bgm_style": "energetic_edm",
        "sound_style": "dynamic",
        "compatible_categories": ["electronics"],
        "compatible_styles": ["unboxing", "product_demo", "talking_head"],
        "compatible_personas": ["tech_enthusiast", "energetic_young", "college_student"],
    },
    "fashion_lookbook": {
        "name": "Fashion Lookbook",
        "description": "Elegant slow-mo, chic aesthetic",
        "mood": "elegant, chic, premium",
        "lighting": "neutral tone, soft diffused",
        "shot_dynamics": "portrait framing, soft tracking shots",
        "camera_motion": "soft tracking, slow dolly, subtle tilt",
        "bgm_style": "chill_loft",
        "sound_style": "elegant",
        "compatible_categories": ["fashion"],
        "compatible_styles": ["holding", "review", "pov"],
        "compatible_personas": ["minimalist_zen", "calm_professional", "energetic_young"],
    },
    "food_review": {
        "name": "Food Review",
        "description": "Warm ASMR-style close-up shots",
        "mood": "warm, appetizing, satisfying",
        "lighting": "warm lighting",
        "shot_dynamics": "macro zoom, appetizing depth of field",
        "camera_motion": "slow macro pull, gentle hand-held sway",
        "bgm_style": "informative_jazz",
        "sound_style": "asmr",
        "compatible_categories": ["food"],
        "compatible_styles": ["review", "pov", "usage"],
        "compatible_personas": ["mom_at_home", "college_student", "energetic_young"],
    },
    "asmr_unboxing": {
        "name": "ASMR Unboxing",
        "description": "Quiet ambient, gentle sounds, relaxing",
        "mood": "calm, relaxing, mindful",
        "lighting": "soft indoor light",
        "shot_dynamics": "close-up macro, minimal camera movement",
        "camera_motion": "static, very slow push, gentle drift",
        "bgm_style": "chill_loft",
        "sound_style": "asmr",
        "compatible_categories": ["home", "beauty", "other"],
        "compatible_styles": ["unboxing", "product_demo"],
        "compatible_personas": ["minimalist_zen", "calm_professional"],
    },
    "makeup_tutorial": {
        "name": "Makeup Tutorial",
        "description": "Soft upbeat, beauty close-ups, trendy",
        "mood": "soft, upbeat, trendy",
        "lighting": "front ring-light aesthetic",
        "shot_dynamics": "sharp close-ups, smooth motion",
        "camera_motion": "steady hand-held, slow pans",
        "bgm_style": "upbeat_pop",
        "sound_style": "upbeat",
        "compatible_categories": ["beauty", "fashion"],
        "compatible_styles": ["usage", "talking_head", "holding"],
        "compatible_personas": ["energetic_young", "calm_professional"],
    },
    "fitness_supplement": {
        "name": "Fitness/Supplement",
        "description": "High energy, motivating, fast tempo",
        "mood": "energetic, motivating, powerful",
        "lighting": "high contrast, punchy",
        "shot_dynamics": "punchy motion, dramatic angles",
        "camera_motion": "fast pan, action follow, whip zoom",
        "bgm_style": "energetic_edm",
        "sound_style": "dynamic",
        "compatible_categories": ["health", "tools"],
        "compatible_styles": ["usage", "talking_head", "comparison"],
        "compatible_personas": ["tech_enthusiast", "energetic_young", "calm_professional"],
    },
    "product_demo": {
        "name": "Product Demo",
        "description": "No person, product on table, feature showcase",
        "mood": "clean, informative, professional",
        "lighting": "clean studio light, evenly diffused",
        "shot_dynamics": "centered framing, slow rotation or linear pan",
        "camera_motion": "slow push in, static, slow pan",
        "bgm_style": "informative_jazz",
        "sound_style": "clean",
        "compatible_categories": ["electronics", "home", "tools", "home_appliance", "health_hygiene"],
        "compatible_styles": ["product_demo", "product_usage"],
        "compatible_personas": ["calm_professional", "minimalist_zen", "mom_at_home"],
    },
    "home_living": {
        "name": "Home & Living",
        "description": "Clean, soothing, satisfying, aesthetic",
        "mood": "clean, soothing, cozy",
        "lighting": "cozy ambient light, natural wooden/white textures",
        "shot_dynamics": "steady tracking, aesthetic framing",
        "camera_motion": "steady tracking, slow slide",
        "bgm_style": "chill_loft",
        "sound_style": "ambient",
        "compatible_categories": ["home", "home_appliance"],
        "compatible_styles": ["product_demo", "usage", "pov"],
        "compatible_personas": ["mom_at_home", "minimalist_zen", "calm_professional"],
    },
    "travel_edc": {
        "name": "Travel & EDC",
        "description": "Dynamic, outdoor, practical, compact",
        "mood": "dynamic, adventurous, practical",
        "lighting": "natural daylight, diffused outdoor",
        "shot_dynamics": "fast movement, hands-on action framing",
        "camera_motion": "action follow, hand-held dynamic",
        "bgm_style": "upbeat_pop",
        "sound_style": "dynamic",
        "compatible_categories": ["fashion", "tools", "other"],
        "compatible_styles": ["pov", "usage", "product_demo"],
        "compatible_personas": ["energetic_young", "tech_enthusiast", "college_student"],
    },
    "mom_baby": {
        "name": "Mom & Baby",
        "description": "Warm, gentle, safe, trustworthy",
        "mood": "warm, gentle, nurturing",
        "lighting": "pastel tones, soft warm light",
        "shot_dynamics": "gentle tilt/pan, soft framing",
        "camera_motion": "gentle tilt, slow pan, soft float",
        "bgm_style": "chill_loft",
        "sound_style": "gentle",
        "compatible_categories": ["home", "health"],
        "compatible_styles": ["talking_head", "usage", "review"],
        "compatible_personas": ["mom_at_home", "calm_professional", "minimalist_zen"],
    },
    "pet_care": {
        "name": "Pet Care",
        "description": "Cute, cheerful, playful, energetic",
        "mood": "cheerful, playful, bright",
        "lighting": "bright colorful, natural window",
        "shot_dynamics": "eye-level animal framing",
        "camera_motion": "quick tracking, bouncy follow",
        "bgm_style": "upbeat_pop",
        "sound_style": "playful",
        "compatible_categories": ["home", "other"],
        "compatible_styles": ["usage", "pov", "review"],
        "compatible_personas": ["mom_at_home", "energetic_young", "college_student"],
    },
}

# ─────────────────────────────────────────────────────────────────────
# 2. UGC CONTENT STYLES (รูปแบบการเสนอ & มุมกล้อง)
# ─────────────────────────────────────────────────────────────────────
UGC_STYLES = {
    "holding": {
        "name": "Holding Product",
        "description": "ถือสินค้าในมือพูดกับกล้อง แนะนำสินค้า",
        "prompt_anchor": "Hand holding [product] in foreground, facing camera, slight hand movement to show angles",
        "script_structure": "แนะนำตัวแบบเป็นกันเอง อธิบายข้อดีของสินค้า",
        "has_person": True,
        "shot_count": 1,
        "shots": [
            {"time": "0-8s", "desc": "Person holding product, showing to camera", "camera": "medium shot, stable"},
        ],
    },
    "usage": {
        "name": "Product Usage",
        "description": "สาธิตการใช้งานสินค้าจริง",
        "prompt_anchor": "Medium close-up of hands actively operating [product], demonstrating its primary function",
        "script_structure": "โฟกัสขั้นตอนการใช้งาน 1-2-3 ชัดเจน รวดเร็ว",
        "has_person": True,
        "shot_count": 2,
        "shots": [
            {"time": "0-4s", "desc": "Hands reaching for product, picking it up", "camera": "close-up hands"},
            {"time": "4-8s", "desc": "Demonstrating product function", "camera": "medium close-up, following action"},
        ],
    },
    "review": {
        "name": "UGC Review",
        "description": "รีวิวสินค้าหลังใช้จริง",
        "prompt_anchor": "Creator holding product, speaking to camera with genuine expression",
        "script_structure": "เล่าความรู้สึกหลังใช้จริง (Pros/Cons) แบบจริงใจ ไม่อวยเกินไป",
        "has_person": True,
        "shot_count": 1,
        "shots": [
            {"time": "0-8s", "desc": "Person speaking to camera while holding product", "camera": "medium close-up, eye-level"},
        ],
    },
    "talking_head": {
        "name": "Talking Head",
        "description": "พูดหน้ากล้องตรงๆ สร้างความสนิทสนม",
        "prompt_anchor": "Creator looking directly into camera, speaking naturally in a home or studio setting",
        "script_structure": "เล่าเรื่องแบบปะฉะดะ สร้างความสนิทสนมกับผู้ชม",
        "has_person": True,
        "shot_count": 1,
        "shots": [
            {"time": "0-8s", "desc": "Person speaking directly to camera", "camera": "medium close-up, locked-off"},
        ],
    },
    "product_demo": {
        "name": "Product Demo",
        "description": "โชว์สินค้าไม่มีคน ถ่าย closestudio",
        "prompt_anchor": "Pure product shot on clean background, close-up details, no humans in frame",
        "script_structure": "Voiceover อธิบายสเปกและฟีเจอร์เด่นของสินค้าล้วนๆ",
        "has_person": False,
        "shot_count": 3,
        "shots": [
            {"time": "0-5s", "desc": "Establishing product shot on table", "camera": "slow push in, centered framing"},
            {"time": "5-10s", "desc": "Core function demonstration — hand trigger sensor, spray", "camera": "close-up, static"},
            {"time": "10-15s", "desc": "Lifestyle placement — product in use context", "camera": "wide, slow pan right"},
        ],
    },
    "problem_solution": {
        "name": "Problem-Solution",
        "description": "เปิดด้วยปัญหา → เฉลยทางแก้",
        "prompt_anchor": "Frustrated expression/problem situation first, transitioning to smooth usage of [product]",
        "script_structure": "0-3s: ชี้ปัญหา, 3-10s: เปิดตัวสินค้า, 10-15s: ผลลัพธ์",
        "has_person": True,
        "shot_count": 2,
        "shots": [
            {"time": "0-3s", "desc": "Frustrated/problem expression", "camera": "close-up on face"},
            {"time": "3-10s", "desc": "Transition to using product, happy result", "camera": "medium, dynamic pan"},
        ],
    },
    "comparison": {
        "name": "Comparison / Test",
        "description": "เปรียบเทียบ/ทดสอบประสิทธิภาพ",
        "prompt_anchor": "Split-screen or side-by-side comparison testing [product] vs standard alternative",
        "script_structure": "ท้าพิสูจน์ด้วยการทดสอบจริง (ความทนทาน ความเร็ว ประสิทธิภาพ)",
        "has_person": True,
        "shot_count": 2,
        "shots": [
            {"time": "0-5s", "desc": "Two products side by side, starting test", "camera": "wide, two-shot"},
            {"time": "5-10s", "desc": "Result of comparison, winner highlighted", "camera": "close-up on winning product"},
        ],
    },
    "unboxing": {
        "name": "Unboxing & First Impression",
        "description": "แกะกล่องลองเลย เปิดกล่องครั้งแรก",
        "prompt_anchor": "Top-down angle (overhead shot) opening product box, revealing contents and accessories",
        "script_structure": "ความรู้สึกแรกเห็น แพ็กเกจจิ้ง ของแถม และสัมผัสแรก",
        "has_person": True,
        "shot_count": 2,
        "shots": [
            {"time": "0-4s", "desc": "Top-down shot of unboxing, opening box", "camera": "overhead, stable"},
            {"time": "4-8s", "desc": "Holding product, showing accessories", "camera": "medium close-up, hand-held"},
        ],
    },
    "pov": {
        "name": "POV / Day in the Life",
        "description": "มุมมองบุคคลที่ 1 สอดแทรกสินค้าในชีวิตประจำวัน",
        "prompt_anchor": "First-person perspective (POV), showing creator's point of view while seamlessly integrating [product]",
        "script_structure": "สอดแทรกสินค้าเข้าไปในกิจวัตรประจำวันอย่างเป็นธรรมชาติ",
        "has_person": False,
        "shot_count": 2,
        "shots": [
            {"time": "0-4s", "desc": "POV walking into room, picking up product", "camera": "first-person, natural movement"},
            {"time": "4-8s", "desc": "POV using product in daily context", "camera": "first-person, hands visible"},
        ],
    },
}

# ─────────────────────────────────────────────────────────────────────
# 3. RECOMMENDED COMBINATIONS
# ─────────────────────────────────────────────────────────────────────
UGC_COMBOS = {
    "electronics_gadget": {
        "preset": "gadget_unboxing",
        "styles": ["product_demo", "unboxing", "problem_solution"],
        "personas": ["tech_enthusiast"],
    },
    "home_appliance": {
        "preset": "product_demo",
        "styles": ["product_demo", "usage", "pov"],
        "personas": ["calm_professional", "mom_at_home"],
    },
    "home_decor": {
        "preset": "home_living",
        "styles": ["pov", "product_demo", "usage"],
        "personas": ["minimalist_zen", "mom_at_home"],
    },
    "food_beverage": {
        "preset": "food_review",
        "styles": ["review", "pov", "usage"],
        "personas": ["mom_at_home", "college_student", "energetic_young"],
    },
    "skincare_beauty": {
        "preset": "skincare_glow",
        "styles": ["review", "usage", "talking_head"],
        "personas": ["energetic_young", "calm_professional"],
    },
    "fashion_accessory": {
        "preset": "fashion_lookbook",
        "styles": ["holding", "pov", "review"],
        "personas": ["minimalist_zen", "calm_professional", "energetic_young"],
    },
    "health_hygiene": {
        "preset": "product_demo",
        "styles": ["product_demo", "usage", "review"],
        "personas": ["calm_professional", "minimalist_zen", "mom_at_home"],
    },
    "fitness_sport": {
        "preset": "fitness_supplement",
        "styles": ["usage", "talking_head", "comparison"],
        "personas": ["tech_enthusiast", "energetic_young"],
    },
    "pet_supply": {
        "preset": "pet_care",
        "styles": ["usage", "pov", "review"],
        "personas": ["mom_at_home", "energetic_young"],
    },
    "baby_kids": {
        "preset": "mom_baby",
        "styles": ["talking_head", "usage", "review"],
        "personas": ["mom_at_home", "calm_professional"],
    },
    "travel_edc": {
        "preset": "travel_edc",
        "styles": ["pov", "usage", "product_demo"],
        "personas": ["energetic_young", "tech_enthusiast"],
    },
}


# ─────────────────────────────────────────────────────────────────────
# 4. Helpers
# ─────────────────────────────────────────────────────────────────────

def auto_select_preset(category: str) -> dict:
    """Auto-select best preset based on product category."""
    # Map flat categories to combo keys
    cat_to_combo = {
        "electronics": "electronics_gadget",
        "home_appliance": "home_appliance",
        "home": "home_decor",
        "food": "food_beverage",
        "beauty": "skincare_beauty",
        "fashion": "fashion_accessory",
        "health_hygiene": "health_hygiene",
        "health": "health_hygiene",
        "fitness": "fitness_sport",
        "tools": "electronics_gadget",
    }
    combo_key = cat_to_combo.get(category, "health_hygiene")
    combo = UGC_COMBOS.get(combo_key, UGC_COMBOS["health_hygiene"])
    preset = UGC_PRESETS.get(combo["preset"], UGC_PRESETS["product_demo"])
    return {
        "combo": combo,
        "preset": preset,
        "preset_id": combo["preset"],
        "suggested_styles": combo["styles"],
    }


def auto_select_style(styles_list: list, has_person: bool = True) -> str:
    """Auto-select best style from a list of candidates."""
    # Prefer styles that match has_person requirement
    for style_id in styles_list:
        s = UGC_STYLES.get(style_id)
        if s and s["has_person"] == has_person:
            return style_id
    # Fallback to first
    return styles_list[0] if styles_list else "product_demo"


def build_shot_prompts(style_id: str, product_appearance: str, preset: dict) -> list:
    """Build multi-shot video prompts from style + preset config."""
    style = UGC_STYLES.get(style_id)
    if not style:
        return []
    
    env_str = "a modern space"
    lighting = preset.get("lighting", "soft diffused lighting")
    
    prompts = []
    for shot in style["shots"]:
        prompt = f"{shot['desc']}. {product_appearance[:200]}"
        prompt += f" Camera: {shot['camera']}. {lighting}. 9:16 portrait, smooth motion"
        prompts.append(prompt)
    
    return prompts
