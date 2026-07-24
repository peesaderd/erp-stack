#!/usr/bin/env python3
"""
Schema Engine — Batch update UGC presets, styles & combos
Usage: python3 schema_engine_ugc_update.py
"""
import json, urllib.request, sys

ENGINE = "http://localhost:8100"

def api(method, path, body=None):
    url = f"{ENGINE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ERROR {method} {path}: {e}")
        return None

def get_records(schema):
    r = api("GET", f"/api/v1/data/{schema}")
    return r.get("data", []) if r and r.get("success") else []

def upsert_record(schema, data, record_id=None):
    if record_id:
        return api("PUT", f"/api/v1/data/{schema}/{record_id}", data)
    # Try to find by style_key
    existing = get_records(schema)
    key_field = "style_key" if schema == "ugc_style" else "preset_key" if schema == "ugc_preset" else "combo_key"
    for rec in existing:
        if rec["data"].get(key_field) == data.get(key_field):
            return api("PUT", f"/api/v1/data/{schema}/{rec['id']}", data)
    return api("POST", f"/api/v1/data/{schema}", data)

def create_schema(slug, name, description, fields):
    body = {
        "name": name,
        "slug": slug,
        "description": description,
        "fields": fields,
    }
    # Try to get existing first
    r = api("GET", f"/api/v1/schema/{slug}")
    if r and r.get("success"):
        print(f"  Schema '{slug}' already exists, updating fields...")
        r2 = api("PUT", f"/api/v1/schema/{slug}", {"fields_update": fields})
        return r2.get("schema", r.get("schema")) if r2 else r.get("schema")
    r = api("POST", "/api/v1/schema", body)
    return r.get("schema") if r else None

# ══════════════════════════════════════════════════════════
# 1. UGC PRESET SCHEMA
# ══════════════════════════════════════════════════════════
print("=== Creating ugc_preset schema ===")
preset_fields = [
    {"name": "preset_key", "field_type": "text", "unique": True, "required": True, "description": "Preset identifier"},
    {"name": "name", "field_type": "text", "description": "Display name"},
    {"name": "description", "field_type": "text", "description": "Short description"},
    {"name": "mood", "field_type": "text", "description": "Mood/vibe for video generation"},
    {"name": "lighting", "field_type": "text", "description": "Lighting specification"},
    {"name": "shot_dynamics", "field_type": "text", "description": "Shot dynamics description"},
    {"name": "camera_motion", "field_type": "text", "description": "Camera motion style"},
    {"name": "bgm_style", "field_type": "text", "description": "BGM genre"},
    {"name": "sound_style", "field_type": "text", "description": "Sound design style"},
    {"name": "compatible_categories", "field_type": "text", "description": "JSON array of compatible categories"},
    {"name": "compatible_styles", "field_type": "text", "description": "JSON array of compatible style keys"},
    {"name": "compatible_personas", "field_type": "text", "description": "JSON array of compatible persona keys"},
    {"name": "is_active", "field_type": "boolean", "default": True},
]
create_schema("ugc_preset", "UGC Preset", "Recipe presets — mood, lighting, camera, BGM per product category", preset_fields)

# ══════════════════════════════════════════════════════════
# 2. UGC COMBO SCHEMA
# ══════════════════════════════════════════════════════════
print("\n=== Creating ugc_combo schema ===")
combo_fields = [
    {"name": "combo_key", "field_type": "text", "unique": True, "required": True, "description": "Combo identifier"},
    {"name": "category_key", "field_type": "text", "description": "Product category for this combo"},
    {"name": "preset_key", "field_type": "text", "description": "Recommended preset"},
    {"name": "style_keys", "field_type": "text", "description": "JSON array of recommended style keys"},
    {"name": "persona_keys", "field_type": "text", "description": "JSON array of recommended persona keys"},
    {"name": "is_active", "field_type": "boolean", "default": True},
]
create_schema("ugc_combo", "UGC Combo", "Recommended preset+style+persona combinations per product category", combo_fields)

# ══════════════════════════════════════════════════════════
# 3. UPDATE UGC STYLE SCHEMA — add new fields
# ══════════════════════════════════════════════════════════
print("\n=== Updating ugc_style schema — new fields ===")
style_new_fields = [
    {"name": "prompt_anchor", "field_type": "text", "description": "Template anchor text for video prompt building"},
    {"name": "script_structure", "field_type": "text", "description": "Expected script format for this style"},
    {"name": "shot_count", "field_type": "integer", "default": 1, "description": "Number of shots for multi-shot videos"},
    {"name": "has_person", "field_type": "boolean", "default": True, "description": "Does this style include a person in frame"},
    {"name": "compatible_categories", "field_type": "text", "description": "JSON array of compatible category names"},
]
api("PUT", "/api/v1/schema/ugc_style", {"fields_update": style_new_fields})

# ══════════════════════════════════════════════════════════
# 4. UPDATE EXISTING UGC STYLE RECORDS
# ══════════════════════════════════════════════════════════
print("\n=== Updating existing ugc_style records ===")

STYLE_UPDATES = {
    "product_demo": {
        "prompt_anchor": "Pure product shot on clean background, close-up details, no humans in frame",
        "script_structure": "Voiceover อธิบายสเปกและฟีเจอร์เด่นของสินค้าล้วนๆ",
        "shot_count": 3,
        "has_person": False,
        "compatible_categories": json.dumps(["electronics", "home", "tools", "home_appliance", "health_hygiene"]),
    },
    "holding": {
        "prompt_anchor": "Hand holding [product] in foreground, facing camera, slight hand movement to show angles",
        "script_structure": "แนะนำตัวแบบเป็นกันเอง อธิบายข้อดีของสินค้า",
        "shot_count": 1,
        "has_person": True,
        "compatible_categories": json.dumps(["beauty", "fashion", "food", "other"]),
    },
    "usage": {
        "prompt_anchor": "Medium close-up of hands actively operating [product], demonstrating its primary function",
        "script_structure": "โฟกัสขั้นตอนการใช้งาน 1-2-3 ชัดเจน รวดเร็ว",
        "shot_count": 1,
        "has_person": True,
        "compatible_categories": json.dumps(["beauty", "home", "tools", "health_hygiene"]),
    },
    "review": {
        "prompt_anchor": "Creator holding product, speaking to camera with genuine expression",
        "script_structure": "เล่าความรู้สึกหลังใช้จริง (Pros/Cons) แบบจริงใจ ไม่อวยเกินไป",
        "shot_count": 1,
        "has_person": True,
        "compatible_categories": json.dumps(["beauty", "food", "fashion", "home", "health"]),
    },
    "talking": {
        "prompt_anchor": "Creator looking directly into camera, speaking naturally in a home or studio setting",
        "script_structure": "เล่าเรื่องแบบปะฉะดะ สร้างความสนิทสนมกับผู้ชม",
        "shot_count": 1,
        "has_person": True,
        "compatible_categories": json.dumps(["beauty", "health", "fashion", "other"]),
    },
    "aesthetic_vlog": {
        "prompt_anchor": "Slow lifestyle montage, product integrated into daily routine, aesthetic shots",
        "script_structure": "สอดแทรกสินค้าในชีวิตประจำวันแบบ cinematic",
        "shot_count": 2,
        "has_person": True,
        "compatible_categories": json.dumps(["beauty", "fashion", "home", "other"]),
    },
    "product_only": {
        "prompt_anchor": "Product resting on clean aesthetic minimalist surface, NO people, NO hands",
        "script_structure": "Voiceover สั้น ชูจุดเด่นสินค้า",
        "shot_count": 1,
        "has_person": False,
        "compatible_categories": json.dumps(["electronics", "home", "tools", "other"]),
    },
    "tabletop_demo": {
        "prompt_anchor": "Product placed neatly on clean tabletop, model beside product gesturing to features",
        "script_structure": "อธิบายสินค้าแบบใกล้ชิด ชูฟีเจอร์เด่น",
        "shot_count": 1,
        "has_person": True,
        "compatible_categories": json.dumps(["home", "tools", "food", "electronics"]),
    },
    "pov_lifehack": {
        "prompt_anchor": "First-person perspective (POV), showing creator's point of view while using [product]",
        "script_structure": "สอดแทรกสินค้าในกิจวัตรประจำวันอย่างเป็นธรรมชาติ",
        "shot_count": 1,
        "has_person": False,
        "compatible_categories": json.dumps(["home", "tools", "food", "fashion", "other"]),
    },
    "split_comparison": {
        "prompt_anchor": "Side-by-side comparison testing [product] vs standard alternative",
        "script_structure": "ท้าพิสูจน์ด้วยการทดสอบจริง (ความทนทาน ความเร็ว ประสิทธิภาพ)",
        "shot_count": 2,
        "has_person": True,
        "compatible_categories": json.dumps(["electronics", "home", "tools", "beauty", "health"]),
    },
    "street_interview": {
        "prompt_anchor": "Excited reaction, showing product as if discovered randomly, genuine surprise",
        "script_structure": "รีวิวตื่นเต้น บอกความรู้สึกแรกเห็น",
        "shot_count": 1,
        "has_person": True,
        "compatible_categories": json.dumps(["food", "fashion", "beauty", "other"]),
    },
    "asmr_texture": {
        "prompt_anchor": "Extreme close-up, product being opened/applied, slow deliberate movements",
        "script_structure": "ไม่ต้องพูด โฟกัสที่สัมผัสและภาพ",
        "shot_count": 1,
        "has_person": False,
        "compatible_categories": json.dumps(["beauty", "food", "home", "other"]),
    },
    "greenscreen_react": {
        "prompt_anchor": "Reacting to product content on greenscreen, pointing at overlay, expressive reactions",
        "script_structure": "แสดงความเห็นแบบไวต่อปฏิกิริยา ใช้เนื้อหาประกอบ",
        "shot_count": 1,
        "has_person": True,
        "compatible_categories": json.dumps(["electronics", "food", "beauty", "other"]),
    },
    "warehouse_vlog": {
        "prompt_anchor": "Presenter inside warehouse/stockroom surrounded by shelves, holding product",
        "script_structure": "เน้นความน่าเชื่อถือ แหล่งสินค้าตรงจากคลัง",
        "shot_count": 1,
        "has_person": True,
        "compatible_categories": json.dumps(["electronics", "home", "tools", "other"]),
    },
}

existing = get_records("ugc_style")
updated = 0
for rec in existing:
    key = rec["data"].get("style_key", "")
    if key in STYLE_UPDATES:
        update_data = {**rec["data"], **STYLE_UPDATES[key]}
        r = api("PUT", f"/api/v1/data/ugc_style/{rec['id']}", update_data)
        if r and r.get("success"):
            updated += 1
            print(f"  ✓ {key}")
        else:
            print(f"  ✗ {key} — update failed")
print(f"  Updated {updated}/{len(existing)} records")

# ══════════════════════════════════════════════════════════
# 5. ADD NEW STYLES (problem_solution, comparison, unboxing, pov)
# ══════════════════════════════════════════════════════════
print("\n=== Adding new ugc_style records ===")
NEW_STYLES = {
    "problem_solution": {
        "style_key": "problem_solution",
        "name": "Problem-Solution",
        "model_action": "Frustrated expression/problem situation first, transitioning to smooth usage of [product]",
        "camera": "Two-shot: close-up on face for problem, medium for solution",
        "vibe": "dramatic, transformative, convincing",
        "keywords": "problem solution, before after, transformation, pain point",
        "video_motion": "Transition shot from frustrated to happy while using product",
        "prompt_anchor": "Frustrated expression/problem situation first, transitioning to smooth usage of [product]",
        "script_structure": "0-3s: ชี้ปัญหา, 3-10s: เปิดตัวสินค้า, 10-15s: ผลลัพธ์",
        "shot_count": 2,
        "has_person": True,
        "compatible_categories": json.dumps(["electronics", "home", "tools", "beauty", "health_hygiene"]),
        "video_resolution": "720P",
        "aspect_ratio": "9:16",
        "is_active": True,
        "is_default": False,
        "sort_order": 15,
    },
    "comparison": {
        "style_key": "comparison",
        "name": "Comparison / Test",
        "model_action": "Split-screen or side-by-side comparison testing [product] vs standard alternative",
        "camera": "Split screen, same framing for both sides",
        "vibe": "dramatic, transformative, convincing, scientific",
        "keywords": "comparison, side by side, test, proof, before after",
        "video_motion": "Side by side reveal, product on one side, alternative on the other",
        "prompt_anchor": "Side-by-side comparison testing [product] vs standard alternative",
        "script_structure": "ท้าพิสูจน์ด้วยการทดสอบจริง (ความทนทาน ความเร็ว ประสิทธิภาพ)",
        "shot_count": 2,
        "has_person": True,
        "compatible_categories": json.dumps(["electronics", "home", "tools", "beauty", "health"]),
        "video_resolution": "720P",
        "aspect_ratio": "9:16",
        "is_active": True,
        "is_default": False,
        "sort_order": 16,
    },
    "unboxing": {
        "style_key": "unboxing",
        "name": "Unboxing & First Impression",
        "model_action": "Top-down angle (overhead shot) opening product box, revealing contents and accessories",
        "camera": "Overhead shot, then medium shot for first impression",
        "vibe": "excited, curious, honest",
        "keywords": "unboxing, first impression, packaging, box opening, reveal",
        "video_motion": "Hands opening box, removing packaging, revealing product",
        "prompt_anchor": "Top-down angle (overhead shot) opening product box, revealing contents and accessories",
        "script_structure": "ความรู้สึกแรกเห็น แพ็กเกจจิ้ง ของแถม และสัมผัสแรก",
        "shot_count": 2,
        "has_person": True,
        "compatible_categories": json.dumps(["electronics", "home", "beauty", "fashion", "tools"]),
        "video_resolution": "720P",
        "aspect_ratio": "9:16",
        "is_active": True,
        "is_default": False,
        "sort_order": 17,
    },
    "pov": {
        "style_key": "pov",
        "name": "POV / Day in the Life",
        "model_action": "First-person perspective (POV), showing creator's point of view while seamlessly integrating [product]",
        "camera": "First-person POV, natural eye level",
        "vibe": "authentic, immersive, relatable",
        "keywords": "POV, first person, day in life, daily routine, immersive",
        "video_motion": "Walking motion, hands visible, natural head movement",
        "prompt_anchor": "First-person perspective (POV), showing creator's POV while integrating product",
        "script_structure": "สอดแทรกสินค้าในชีวิตประจำวันอย่างเป็นธรรมชาติ",
        "shot_count": 1,
        "has_person": False,
        "compatible_categories": json.dumps(["home", "fashion", "food", "other", "travel_edc"]),
        "video_resolution": "720P",
        "aspect_ratio": "9:16",
        "is_active": True,
        "is_default": False,
        "sort_order": 18,
    },
}

for key, data in NEW_STYLES.items():
    # Check if already exists
    exists = any(r["data"].get("style_key") == key for r in existing)
    if exists:
        print(f"  ~ {key} already exists, skipping")
        continue
    r = api("POST", "/api/v1/data/ugc_style", data)
    if r and r.get("success"):
        print(f"  ✓ {key} added")
    else:
        print(f"  ✗ {key} — failed")

# ══════════════════════════════════════════════════════════
# 6. ADD PRESET RECORDS (12 presets)
# ══════════════════════════════════════════════════════════
print("\n=== Adding ugc_preset records ===")
PRESETS = {
    "skincare_glow": {"preset_key": "skincare_glow", "name": "Skincare Glow", "description": "Soft luxury vibes, calm music, slow transitions", "mood": "soft, luxurious, calming", "lighting": "soft daylighting, clean shadows", "shot_dynamics": "cinematic, slow-motion", "camera_motion": "slow push in, gentle pan, soft rack focus", "bgm_style": "chill_loft", "sound_style": "ambient", "compatible_categories": json.dumps(["beauty", "health"]), "compatible_styles": json.dumps(["holding", "review", "usage", "talking"]), "compatible_personas": json.dumps(["calm_professional", "minimalist_zen", "energetic_young"]), "is_active": True},
    "gadget_unboxing": {"preset_key": "gadget_unboxing", "name": "Gadget Unboxing", "description": "Fast-paced, energetic, quick cuts", "mood": "energetic, exciting, tech-forward", "lighting": "high contrast, sharp focus, studio lighting", "shot_dynamics": "dynamic pan/zoom", "camera_motion": "fast whip pans, punch-in zooms, quick cuts", "bgm_style": "energetic_edm", "sound_style": "dynamic", "compatible_categories": json.dumps(["electronics"]), "compatible_styles": json.dumps(["product_demo", "unboxing", "talking"]), "compatible_personas": json.dumps(["tech_enthusiast", "energetic_young", "college_student"]), "is_active": True},
    "fashion_lookbook": {"preset_key": "fashion_lookbook", "name": "Fashion Lookbook", "description": "Elegant slow-mo, chic aesthetic", "mood": "elegant, chic, premium", "lighting": "neutral tone, soft diffused", "shot_dynamics": "portrait framing, soft tracking shots", "camera_motion": "soft tracking, slow dolly, subtle tilt", "bgm_style": "chill_loft", "sound_style": "elegant", "compatible_categories": json.dumps(["fashion"]), "compatible_styles": json.dumps(["holding", "review", "pov"]), "compatible_personas": json.dumps(["minimalist_zen", "calm_professional", "energetic_young"]), "is_active": True},
    "food_review": {"preset_key": "food_review", "name": "Food Review", "description": "Warm ASMR-style close-up shots", "mood": "warm, appetizing, satisfying", "lighting": "warm lighting", "shot_dynamics": "macro zoom, appetizing depth of field", "camera_motion": "slow macro pull, gentle hand-held sway", "bgm_style": "informative_jazz", "sound_style": "asmr", "compatible_categories": json.dumps(["food"]), "compatible_styles": json.dumps(["review", "pov", "usage"]), "compatible_personas": json.dumps(["mom_at_home", "college_student", "energetic_young"]), "is_active": True},
    "asmr_unboxing": {"preset_key": "asmr_unboxing", "name": "ASMR Unboxing", "description": "Quiet ambient, gentle sounds, relaxing", "mood": "calm, relaxing, mindful", "lighting": "soft indoor light", "shot_dynamics": "close-up macro, minimal camera movement", "camera_motion": "static, very slow push, gentle drift", "bgm_style": "chill_loft", "sound_style": "asmr", "compatible_categories": json.dumps(["home", "beauty", "other"]), "compatible_styles": json.dumps(["unboxing", "product_demo"]), "compatible_personas": json.dumps(["minimalist_zen", "calm_professional"]), "is_active": True},
    "makeup_tutorial": {"preset_key": "makeup_tutorial", "name": "Makeup Tutorial", "description": "Soft upbeat, beauty close-ups, trendy", "mood": "soft, upbeat, trendy", "lighting": "front ring-light aesthetic", "shot_dynamics": "sharp close-ups, smooth motion", "camera_motion": "steady hand-held, slow pans", "bgm_style": "upbeat_pop", "sound_style": "upbeat", "compatible_categories": json.dumps(["beauty", "fashion"]), "compatible_styles": json.dumps(["usage", "talking", "holding"]), "compatible_personas": json.dumps(["energetic_young", "calm_professional"]), "is_active": True},
    "fitness_supplement": {"preset_key": "fitness_supplement", "name": "Fitness/Supplement", "description": "High energy, motivating, fast tempo", "mood": "energetic, motivating, powerful", "lighting": "high contrast, punchy", "shot_dynamics": "punchy motion, dramatic angles", "camera_motion": "fast pan, action follow, whip zoom", "bgm_style": "energetic_edm", "sound_style": "dynamic", "compatible_categories": json.dumps(["health", "tools"]), "compatible_styles": json.dumps(["usage", "talking", "comparison"]), "compatible_personas": json.dumps(["tech_enthusiast", "energetic_young", "calm_professional"]), "is_active": True},
    "product_demo": {"preset_key": "product_demo", "name": "Product Demo", "description": "No person, product on table, feature showcase", "mood": "clean, informative, professional", "lighting": "clean studio light, evenly diffused", "shot_dynamics": "centered framing, slow rotation or linear pan", "camera_motion": "slow push in, static, slow pan", "bgm_style": "informative_jazz", "sound_style": "clean", "compatible_categories": json.dumps(["electronics", "home", "tools", "home_appliance", "health_hygiene"]), "compatible_styles": json.dumps(["product_demo", "usage"]), "compatible_personas": json.dumps(["calm_professional", "minimalist_zen", "mom_at_home"]), "is_active": True},
    "home_living": {"preset_key": "home_living", "name": "Home & Living", "description": "Clean, soothing, satisfying, aesthetic", "mood": "clean, soothing, cozy", "lighting": "cozy ambient light, natural wooden/white textures", "shot_dynamics": "steady tracking, aesthetic framing", "camera_motion": "steady tracking, slow slide", "bgm_style": "chill_loft", "sound_style": "ambient", "compatible_categories": json.dumps(["home", "home_appliance"]), "compatible_styles": json.dumps(["product_demo", "usage", "pov"]), "compatible_personas": json.dumps(["mom_at_home", "minimalist_zen", "calm_professional"]), "is_active": True},
    "travel_edc": {"preset_key": "travel_edc", "name": "Travel & EDC", "description": "Dynamic, outdoor, practical, compact", "mood": "dynamic, adventurous, practical", "lighting": "natural daylight, diffused outdoor", "shot_dynamics": "fast movement, hands-on action framing", "camera_motion": "action follow, hand-held dynamic", "bgm_style": "upbeat_pop", "sound_style": "dynamic", "compatible_categories": json.dumps(["fashion", "tools", "other", "travel_edc"]), "compatible_styles": json.dumps(["pov", "usage", "product_demo"]), "compatible_personas": json.dumps(["energetic_young", "tech_enthusiast", "college_student"]), "is_active": True},
    "mom_baby": {"preset_key": "mom_baby", "name": "Mom & Baby", "description": "Warm, gentle, safe, trustworthy", "mood": "warm, gentle, nurturing", "lighting": "pastel tones, soft warm light", "shot_dynamics": "gentle tilt/pan, soft framing", "camera_motion": "gentle tilt, slow pan, soft float", "bgm_style": "chill_loft", "sound_style": "gentle", "compatible_categories": json.dumps(["home", "health"]), "compatible_styles": json.dumps(["talking", "usage", "review"]), "compatible_personas": json.dumps(["mom_at_home", "calm_professional", "minimalist_zen"]), "is_active": True},
    "pet_care": {"preset_key": "pet_care", "name": "Pet Care", "description": "Cute, cheerful, playful, energetic", "mood": "cheerful, playful, bright", "lighting": "bright colorful, natural window", "shot_dynamics": "eye-level animal framing", "camera_motion": "quick tracking, bouncy follow", "bgm_style": "upbeat_pop", "sound_style": "playful", "compatible_categories": json.dumps(["home", "other"]), "compatible_styles": json.dumps(["usage", "pov", "review"]), "compatible_personas": json.dumps(["mom_at_home", "energetic_young", "college_student"]), "is_active": True},
}

for key, data in PRESETS.items():
    r = upsert_record("ugc_preset", data)
    if r and r.get("success"):
        print(f"  ✓ {key}")
    else:
        print(f"  ✗ {key} — failed")

# ══════════════════════════════════════════════════════════
# 7. ADD COMBO RECORDS (11 combos)
# ══════════════════════════════════════════════════════════
print("\n=== Adding ugc_combo records ===")
COMBOS = {
    "electronics_gadget": {"combo_key": "electronics_gadget", "category_key": "electronics", "preset_key": "gadget_unboxing", "style_keys": json.dumps(["product_demo", "unboxing", "problem_solution"]), "persona_keys": json.dumps(["tech_enthusiast"]), "is_active": True},
    "home_appliance": {"combo_key": "home_appliance", "category_key": "home_appliance", "preset_key": "product_demo", "style_keys": json.dumps(["product_demo", "usage", "pov"]), "persona_keys": json.dumps(["calm_professional", "mom_at_home"]), "is_active": True},
    "home_decor": {"combo_key": "home_decor", "category_key": "home", "preset_key": "home_living", "style_keys": json.dumps(["pov", "product_demo", "usage"]), "persona_keys": json.dumps(["minimalist_zen", "mom_at_home"]), "is_active": True},
    "food_beverage": {"combo_key": "food_beverage", "category_key": "food", "preset_key": "food_review", "style_keys": json.dumps(["review", "pov", "usage"]), "persona_keys": json.dumps(["mom_at_home", "college_student", "energetic_young"]), "is_active": True},
    "skincare_beauty": {"combo_key": "skincare_beauty", "category_key": "beauty", "preset_key": "skincare_glow", "style_keys": json.dumps(["review", "usage", "talking"]), "persona_keys": json.dumps(["energetic_young", "calm_professional"]), "is_active": True},
    "fashion_accessory": {"combo_key": "fashion_accessory", "category_key": "fashion", "preset_key": "fashion_lookbook", "style_keys": json.dumps(["holding", "pov", "review"]), "persona_keys": json.dumps(["minimalist_zen", "calm_professional", "energetic_young"]), "is_active": True},
    "health_hygiene": {"combo_key": "health_hygiene", "category_key": "health_hygiene", "preset_key": "product_demo", "style_keys": json.dumps(["product_demo", "usage", "review"]), "persona_keys": json.dumps(["calm_professional", "minimalist_zen", "mom_at_home"]), "is_active": True},
    "fitness_sport": {"combo_key": "fitness_sport", "category_key": "fitness", "preset_key": "fitness_supplement", "style_keys": json.dumps(["usage", "talking", "comparison"]), "persona_keys": json.dumps(["tech_enthusiast", "energetic_young"]), "is_active": True},
    "pet_supply": {"combo_key": "pet_supply", "category_key": "pet", "preset_key": "pet_care", "style_keys": json.dumps(["usage", "pov", "review"]), "persona_keys": json.dumps(["mom_at_home", "energetic_young"]), "is_active": True},
    "baby_kids": {"combo_key": "baby_kids", "category_key": "baby", "preset_key": "mom_baby", "style_keys": json.dumps(["talking", "usage", "review"]), "persona_keys": json.dumps(["mom_at_home", "calm_professional"]), "is_active": True},
    "travel_edc": {"combo_key": "travel_edc", "category_key": "travel_edc", "preset_key": "travel_edc", "style_keys": json.dumps(["pov", "usage", "product_demo"]), "persona_keys": json.dumps(["energetic_young", "tech_enthusiast"]), "is_active": True},
}

for key, data in COMBOS.items():
    r = upsert_record("ugc_combo", data)
    if r and r.get("success"):
        print(f"  ✓ {key}")
    else:
        print(f"  ✗ {key} — failed")

print("\n=== Done! ===")
