"""
TikTok UGC Studio - Affiliate Video Pipeline v6 (Structure-based)
================================================================
Pipeline: Analyze → Recipe → Script → Image Prompt → Image → Video Prompts → TTS → Video → Compose

Flow (9 Steps ตาม PIPELINE_STRUCTURE.md):
  Step 1: Product → Analyze (Mistral) → product_profile
  Step 2: Load Recipe → scenes structure
  Step 3: product_profile + recipe → Script (modules/video/script_gen.py)
  Step 4: product_profile + recipe → Image Prompt (prompt-builder-service)
  Step 5: image_prompt + product_image → Generate Image (Prodia Nano Banana)
  Step 6: product_profile + recipe + image → Video Prompts (prompt-builder-service)
  Step 7: script → TTS (Gemini)
  Step 8: image + video_prompts → Wan 2.7 → Video
  Step 9: Video + Voice + BGM → FFmpeg → Final

Cost Estimate:
  - 8s (Nano Banana + Gemini TTS + Wan 2.7): ~$0.038
  - 16s (2 scenes): ~$0.068

Changes from v5:
  - เพิ่ม Analyze step (Mistral)
  - เพิ่ม Recipe loading
  - เปลี่ยน Script generation จาก manual → Gemini
  - เปลี่ยน Image prompt จาก manual → Mistral
  - เพิ่ม Video prompts จาก recipe + image
  - ลบ endpoint calls ที่ถูกลบ
"""

import os
import sys
import json
import time
import uuid
import logging
import random
import re
import subprocess
import shutil
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests

def get_bgm_path(bgm_style: str) -> Path:
    """Helper to resolve BGM path. Randomly pick an available track from the BGM library."""
    # Collect all available BGM files from both locations (module-local sounds + tiktok-ugc-studio/bgm).
    # Exclude TTS voice samples (tts_*.mp3) which are not background music.
    candidates = []
    for d in (STORAGE_DIR / "sounds", _erp_stack / "tiktok-ugc-studio" / "bgm"):
        if d.is_dir():
            candidates.extend(
                p for p in sorted(d.glob("*.mp3"))
                if not p.name.startswith("tts_")
            )
    if candidates:
        return random.choice(candidates)
    # Last resort: return a path even if it doesn't exist (compose_video will skip BGM)
    return _erp_stack / "tiktok-ugc-studio" / "bgm" / "bg_chill.mp3"

# Add erp-stack to path for shared_config
_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from shared_config import PRODIA_TOKEN, GEMINI_API_KEY

# ─── Schema Engine UGC Style Client ─────────────────────────────────
_ugc_client_dir = os.path.join(str(_erp_stack), "prompt-builder-service")
if _ugc_client_dir not in sys.path:
    sys.path.insert(0, _ugc_client_dir)
from ugc_schema_client import get_default_style, get_style_config, validate_ugc_style, is_valid_style

# Import pipeline logger (same directory)
from pipeline_logger import start_job, update_step, update_cost, complete_job, fail_job, update_prompts

logger = logging.getLogger("tiktok-ugc.pipeline_affiliate")

# ─── Config ────────────────────────────────────────────────────────────────

STORAGE_DIR = Path(__file__).parent / "storage"
TMP_DIR = STORAGE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Service URLs
IMAGE_GEN_URL = "http://localhost:8110/api/v1/image/generate"
PROMPT_BUILDER_URL = "http://localhost:8117"

def _resolve_product_image(product_name: str) -> str:
    """Resolve product image URL from tus_products.db (SSOT) when caller omitted it."""
    if not product_name:
        return ""
    module_dir = Path(__file__).resolve().parent          # modules/video
    db_candidates = [
        module_dir.parent / "tiktok-ugc-studio" / "tus_products.db",   # erp-stack/tiktok-ugc-studio
        module_dir.parent.parent / "tiktok-ugc-studio" / "tus_products.db",
    ]
    for db_path in db_candidates:
        if not db_path.exists():
            continue
        try:
            con = sqlite3.connect(str(db_path))
            rows = con.execute(
                "SELECT images FROM tus_products WHERE product_id = ? OR title = ? OR title_th = ? LIMIT 1",
                (product_name, product_name, product_name),
            ).fetchall()
            con.close()
            if rows and rows[0][0]:
                images = json.loads(rows[0][0])
                if isinstance(images, list) and images:
                    fname = Path(str(images[0])).name
                    return f"http://localhost:8105/ugc/static/product_images/{fname}"
        except Exception:
            continue
    return ""




def download_file(url: str, output_path: Path) -> Path:
    """Download from URL to local path."""
    if os.path.exists(url):
        shutil.copy2(url, output_path)
        return output_path
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path


def concat_videos(video_paths: list, output_path: Path) -> Path:
    """Concat multiple videos with FFmpeg. Skip None entries."""
    valid_paths = [vp for vp in video_paths if vp is not None]

    if not valid_paths:
        raise RuntimeError("No valid videos to concat (all None)")

    if len(valid_paths) == 1:
        shutil.copy2(valid_paths[0], output_path)
        return output_path

    list_file = TMP_DIR / f"concat_{uuid.uuid4().hex}.txt"
    with open(list_file, "w") as f:
        for vp in valid_paths:
            f.write(f"file '{Path(vp).absolute()}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(list_file), "-c", "copy", str(output_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink(missing_ok=True)
    return output_path


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: Analyze Product (Mistral)
# ═══════════════════════════════════════════════════════════════════════════

def analyze_product(product_name: str, product_image: str = None, description: str = "", ugc_style: str = "holding", gender: str = "", target_age: str = "", features: str = "") -> dict:
    """
    Step 1: Analyze product via Mistral → product_profile

    Args:
        product_name: ชื่อสินค้า
        product_image: URL ของรูปสินค้า (optional)
        description: คําอธิบายสินค้า (optional)
        ugc_style: UGC style (holding/usage/review/etc.)

    Returns:
        dict: product_profile {
            category, target_gender, target_age, target_audience,
            customer_problem, main_benefit, hashtags, setting,
            _image_prompt, _video_prompt, _negative_prompt
        }
    """
    logger.info(f"Step 1/9: Analyze product (Mistral)")
    logger.info(f"  Product: {product_name}")
    logger.info(f"  Image: {product_image or 'None'}")
    logger.info(f"  UGC style: {ugc_style}")

    try:
        # Call Prompt Builder API
        url = f"{PROMPT_BUILDER_URL}/api/v1/build"
        payload = {
            "product_name": product_name,
            "description": description,
            "product_image": product_image or "",
            "ugc_style": ugc_style,
            "target_gender": gender,
            "target_age": target_age,
            "features": features,
        }

        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        profile = data.get("analysis", {})
        logger.info(f"  Analyzed: {profile.get('category')} / {profile.get('target_gender')}")

        # เก็บ image_prompt + video_prompt + negative_prompt ที่ได้จาก API
        profile["_image_prompt"] = data.get("image_prompt", "")
        profile["_video_prompt"] = data.get("video_prompt", "")
        profile["_negative_prompt"] = data.get("negative_prompt", "")

        return profile

    except Exception as e:
        logger.error(f"Analyze failed: {e}")
        # No fallback — fail fast so the pipeline never runs with a generic
        # prompt that does not match the product. Re-raise to stop the job.
        raise RuntimeError(f"Product analysis failed (no fallback): {e}")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2: Load Recipe
# ═══════════════════════════════════════════════════════════════════════════

def load_recipe(recipe_name: str = "tus") -> dict:
    """
    Step 2: Load recipe → scenes structure

    Query จาก Schema Engine (services/schema-engine) เท่านั้น
    ถ้า Schema Engine ไม่ตอบ หรือ recipe ไม่มี → throw error ทันที
    (ไม่มี filesystem fallback เพื่อให้รู้ทันเมื่อ Schema Engine พัง)

    Args:
        recipe_name: ชื่อ recipe (tus_novoice_15s, tus_15s, etc.)

    Returns:
        dict: recipe { name, total_duration, image_generation, video_generation, tts, ... }
    """
    logger.info(f"Step 2/9: Load recipe ({recipe_name})")

    schema_url = os.environ.get("SCHEMA_ENGINE_URL", "http://localhost:8100")
    resp = requests.get(
        f"{schema_url}/api/v1/data/video_recipe",
        params={"search": recipe_name, "limit": 1},
        timeout=3,
    )
    
    if resp.status_code != 200:
        raise RuntimeError(f"Schema Engine returned {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    records = data.get("data", [])
    if not records:
        raise RuntimeError(f"Recipe '{recipe_name}' not found in Schema Engine (video_recipe schema)")

    record = records[0]
    row = record.get("data", record)
    # Schema Engine stores with double nesting: data.data.config
    inner = row.get("data", row) if isinstance(row, dict) and "config" not in row else row
    config = inner.get("config", row.get("config", {}))

    # Use `inner` for recipe-level fields (unwrap double-nesting)
    recipe = {
        "name": inner.get("name", recipe_name),
        "description": inner.get("description", ""),
        "version": inner.get("version", "1.0"),
        "total_duration": inner.get("total_duration", 15),
        "language": inner.get("language", "th"),
        "default_style": inner.get("default_style", "holding"),
        "scenes": config.get("scenes", []),
        "video_model": config.get("video_model", "wan2.7"),
        "video_count": config.get("video_count", 1),
        "ugc_styles": config.get("ugc_styles", ["holding", "review", "usage", "talking"]),
        "voice_tone": config.get("voice_tone", "friendly, authentic, enthusiastic"),
        "target_audience": config.get("target_audience", "Thai TikTok users"),
        "image_generation": config.get("image_generation", {}),
        "video_generation": config.get("video_generation", {}),
        "tts": config.get("tts"),  # None = no voiceover
        "scene_actions_by_category": config.get("scene_actions_by_category", {}),
        "lighting_map": config.get("lighting_map", {}),
    }

    scenes = recipe.get("scenes", [])
    logger.info(f"  Recipe (Schema Engine): {recipe_name}, {len(scenes)} scenes, {recipe.get('total_duration')}s")
    return recipe


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3: Generate Script (Gemini)
# ═══════════════════════════════════════════════════════════════════════════

def generate_script(
    product_name: str,
    product_profile: dict,
    recipe: dict,
    ugc_style: str = "holding",
) -> str:
    """
    Step 3: Generate script via Gemini

    Args:
        product_name: ชื่อสินค้า
        product_profile: ผลจาก analyze_product()
        recipe: ผลจาก load_recipe()
        ugc_style: สไตล์ UGC (holding, review, product_demo, ...)

    Returns:
        str: full_script
    """
    logger.info(f"Step 3/9: Generate script (Gemini, style={ugc_style})")

    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from script_gen import generate_tiktok_review_script

        # product_demo style → use natural Thai narration template
        # other styles → use review template (Hook/Value/CTA)
        style = "product_demo" if ugc_style == "product_demo" else "review"

        result = generate_tiktok_review_script(
            product_name=product_name,
            customer_problem=product_profile.get("customer_problem", ""),
            main_benefit=product_profile.get("main_benefit", ""),
            target_audience=product_profile.get("target_audience", ""),
            tone="เป็นกันเอง พูดเร็ว",
            duration=f"{recipe.get('total_duration', 8)}s",
            features=product_profile.get("features", ""),
            product_appearance=product_profile.get("product_appearance", ""),
            style=style,
        )

        script = result.get("script", "")
        logger.info(f"  Script: {script} (uses_llm={result.get('uses_llm')})")
        return script

    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        # Fallback: natural Thai narration for product_demo
        if ugc_style == "product_demo":
            feat = product_profile.get("features", "")
            appear = product_profile.get("product_appearance", "")
            if feat:
                return f"{product_name} ตัวนี้ {feat} ใช้งานง่ายมาก"
            elif appear:
                return f"{product_name} ตัวนี้{appear[:100]} ใช้งานดี"
            return f"{product_name} ตัวนี้ใช้งานดีมาก"
        # Default: template review script
        base = f"{product_profile.get('customer_problem', 'ปัญหาที่เจอบ่อย')} ใช่ไหมคะ? วันนี้เรามี {product_name}"
        feat = product_profile.get("features", "")
        if feat:
            base += f" มี {feat}"
        base += f" {product_profile.get('main_benefit', 'คุณภาพดี')} ค่ะ กดตะกร้าเลย!"
        return base


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4: Build Image Prompt (Mistral)
# ═══════════════════════════════════════════════════════════════════════════

def build_image_prompt(
    product_name: str,
    product_profile: dict,
    recipe: dict,
) -> str:
    """
    Step 4: Build image prompt via Mistral

    Args:
        product_name: ชื่อสินค้า
        product_profile: ผลจาก analyze_product()
        recipe: ผลจาก load_recipe()

    Returns:
        str: image_prompt
    """
    logger.info(f"Step 4/9: Build image prompt (Mistral)")

    # ใช้ image_prompt ที่ได้จาก analyze_product() (Step 1)
    image_prompt = product_profile.get("_image_prompt", "")

    if image_prompt:
        logger.info(f"  Image prompt: {image_prompt}")
        return image_prompt

    # Fallback: basic prompt
    logger.warning("  No image prompt from analyze, using fallback")
    return f"{product_name}, product showcase, clean background, professional photography"


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5: Generate Image (Prodia Nano Banana)
# ═══════════════════════════════════════════════════════════════════════════

def generate_image(
    prompt: str,
    product_image: str = None,
    aspect_ratio: str = "9:16",
) -> tuple:
    """
    Step 5: Generate image via Prodia Nano Banana Img2Img

    Args:
        prompt: image_prompt จาก Step 4
        product_image: URL ของรูปสินค้า (reference)
        aspect_ratio: 9:16 (TikTok portrait)

    Returns:
        tuple: (image_url, cost_usd)
    """
    logger.info(f"Step 5/9: Generate image (Nano Banana, {aspect_ratio})")
    logger.info(f"  Prompt: {prompt}")
    logger.info(f"  Reference: {product_image or 'None'}")

    payload = {
        "prompt": prompt,
        "count": 1,
        "upscale": False,
        "aspectRatio": aspect_ratio,
    }

    if product_image:
        payload["inputImage"] = product_image
        payload["modelTier"] = "nano.banana"
        payload["provider"] = "prodia"
        payload["thaiModel"] = True

    last_exc = None
    for attempt in range(3):
        try:
            resp = requests.post(IMAGE_GEN_URL, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()

            if not (data.get("success") or data.get("ok")) or not data.get("images"):
                raise RuntimeError(f"Image-gen service failed: {data}")

            img_info = data["images"][0]
            url = img_info.get("full_url") or img_info.get("url")

            if not url:
                raise RuntimeError(f"No URL in response: {data}")

            # Extract cost from image service response (real pricing from prodia_pricing)
            cost_data = data.get("cost", {}) or img_info.get("cost", {})
            cost_usd = float(cost_data.get("dollars", 0.039) if isinstance(cost_data, dict) else 0.039)

            logger.info(f"  Image OK: {url[:60]}... | cost=${cost_usd:.4f}")
            return url, cost_usd

        except Exception as e:
            last_exc = e
            logger.warning(f"  Image gen attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                logger.info(f"  Retrying image gen...")
                import time
                time.sleep(2)

    logger.error(f"Image generation failed after 3 attempts: {last_exc}")
    raise RuntimeError(f"Image generation failed after 3 attempts: {last_exc}")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 6: Build Video Prompts (Mistral)
# ═══════════════════════════════════════════════════════════════════════════

def build_video_prompts(
    product_profile: dict,
    recipe: dict,
    image_path: str,
    ugc_style: str = "holding",
) -> list:
    """
    Step 6: Build video prompts from recipe + image context

    Args:
        product_profile: ผลจาก analyze_product()
        recipe: ผลจาก load_recipe()
        image_path: path ของ image ที่สร้างแล้ว (Step 5)
        ugc_style: UGC style — ใช้ product_type/category กำหนด action ที่เหมาะสม

    Returns:
        list: video_prompts (1 prompt per scene)
    """
    logger.info(f"Step 6/9: Build video prompts (ugc_style={ugc_style})")

    scenes = recipe.get("scenes", [])
    video_prompts = []

    # Setting: prefer env_context (specific environment from Gemini analysis),
    # fallback to setting (general location), then category-aware default.
    # This keeps the scene consistent with the product category (no mixed scenes).
    category = product_profile.get("category", "other")
    product_type = product_profile.get("product_type", "").lower()
    product_name = product_profile.get("product_name", "") or product_profile.get("_product_name", "")

    # Category-aware default settings — ensures scene matches product type
    category_setting_map = {
        "beauty": "a vanity table with soft mirror lighting",
        "fashion": "a bright closet or boutique with clothing racks",
        "electronics": "a clean modern desk or office workspace",
        "home": "a bright living room or kitchen counter",
        "food": "a warm kitchen counter or cafe table",
        "tools": "a functional workshop or garage bench",
        "health": "a clean bathroom or bedroom",
        "other": "a clean modern lifestyle setting",
    }
    # Setting is intentionally NOT injected into the I2V prompt: Wan 2.7 img2vid
    # uses the first frame as conditioning image, so re-describing the setting
    # would fight the reference frame and cause the background to warp.

    # Lighting map — Schema Engine (recipe config) เป็น SSOT;
    # hardcode ข้างล่างเป็น fallback เมื่อ recipe ไม่มีค่า
    lighting_map = {
        "beauty": "soft diffused natural window lighting",
        "tools": "bright functional lighting",
        "electronics": "clean bright studio lighting",
        "food": "warm golden hour lighting",
        "fashion": "bright studio lighting",
        "home": "bright natural daylight",
        "other": "soft natural lighting",
    }
    db_lighting = (recipe.get("lighting_map") or {}).get(category)
    lighting = db_lighting or lighting_map.get(category, "soft natural lighting")
    
    # Model age is intentionally NOT injected into the I2V prompt: the model's
    # appearance comes from the reference image (Step 5), not from re-describing
    # age here (which would fight the first frame).

    # ── Scene descriptions — Schema Engine (recipe config) เป็น SSOT ──
    # ถ้า recipe มี scene_actions_by_category[category] ให้ใช้ของ DB
    # (มี {product} placeholder แทนชื่อสินค้า); fallback = hardcode เดิม
    db_actions = (recipe.get("scene_actions_by_category") or {}).get(category, {})
    if db_actions:
        scene_descriptions = {
            k: (v.replace("{product}", product_name or "product") if isinstance(v, str) else v)
            for k, v in db_actions.items()
        }
    else:
        scene_descriptions = _scene_descriptions_for_category(category, product_type, product_name)

    # ── Model look (จาก profile, ไม่ hardcode) ──
    model_gender = product_profile.get("target_gender", "") or ""
    gender_en = {"female": "woman", "male": "man", "": "Thai person"}.get(model_gender, "Thai person")
    
    # ── Build per-scene prompts ──
    for i, scene in enumerate(scenes):
        scene_name = scene.get("name", f"Scene{i+1}")
        scene_dur = scene.get("duration", 2)
        
        # Get scene-specific description or default
        scene_action = scene_descriptions.get(scene_name, "product visible in frame, natural setting")
        
        # Build the full positive prompt (Minimalist I2V formula).
        # Wan 2.7 img2vid receives the first frame as conditioning image, so we
        # do NOT re-describe the model's face/skin or the setting (that would
        # fight the reference frame and cause the video to not continue).
        # Only describe WHO does WHAT and the LIGHTING tone.
        enhanced = (
            f"The {gender_en}. "
            f"{scene_action} "
            f"{lighting}. "
            f"9:16 portrait, smooth natural motion."
        )
        
        # Action rules come from the UGC style data (Schema Engine SSOT),
        # not from hardcoded per-category restrictions.
        # Gemini/STYLE_MAP decide hold/use/open per the selected UGC style.
        
        video_prompts.append(enhanced)

    logger.info(f"  Generated {len(video_prompts)} video prompts for category={category}")
    return video_prompts


def _scene_descriptions_for_category(category: str, product_type: str, product_name: str) -> dict:
    """Generate scene descriptions based on product category/type.
    
    Returns dict {scene_name: action_description} ใช้ใน build_video_prompts()
    """
    pn = product_name or "product"
    
    # ── Electronics ──
    if category == "electronics":
        return {
            "Hook": f"Model walking toward {pn} installed on wall/counter, product clearly visible in the setting",
            "Problem": f"Close-up of {pn} in off/inactive state, showing need for activation",
            "Discovery": f"Hand reaching for {pn}, finger pressing button or switch, product activating with subtle indicator glow",
            "Features": f"{pn} in active use, feature demonstration, product functionality visible and working",
            "Transformation": f"Wide shot showing {pn} improving the space or solving the problem, room/area visibly better",
            "CTA": f"Model with satisfied expression, {pn} in focus in the background, final product showcase",
        }
    
    # ── Home / Tools ──
    elif category in ("home", "tools"):
        return {
            "Hook": f"Model entering frame holding {pn}, product clearly visible and recognizable",
            "Problem": f"Close-up showing problem or need before using {pn}, relatable struggle",
            "Discovery": f"Model beginning to use {pn}, natural action, product solving the immediate issue",
            "Features": f"Product detail close-up, key features of {pn} visible, texture and build quality shown",
            "Transformation": f"Result visible after using {pn}, improved situation, problem solved",
            "CTA": f"Model satisfied, {pn} in focus, final encouraging shot",
        }
    
    # ── Food ──
    elif category == "food":
        return {
            "Hook": f"{pn} packaging visible, appetizing presentation on table or counter",
            "Problem": f"Opening or preparing {pn}, anticipation visible",
            "Discovery": f"{pn} being revealed, poured, or displayed, texture and color visible",
            "Features": f"Close-up of {pn} texture, ingredients or details visible, mouth-watering shot",
            "Transformation": f"Final prepared state of {pn}, ready to enjoy, appetizing result",
            "CTA": f"Final shot of {pn}, encouraging viewer to try it",
        }
    
    # ── Fashion ──
    elif category == "fashion":
        return {
            "Hook": f"Model holding {pn}, fashion-forward entrance, product clearly visible",
            "Problem": f"Showing look without {pn}, neutral expression",
            "Discovery": f"{pn} being shown or styled, model examining product",
            "Features": f"Texture and detail close-up of {pn}, fabric or finish visible",
            "Transformation": f"Complete look with {pn} styled, confident pose, full outfit visible",
            "CTA": f"Final confident look, {pn} featured prominently",
        }
    
    # ── Beauty — keep original holding restriction ──
    elif category == "beauty":
        return {
            "Hook": f"Model holding {pn} in both hands, product packaging facing camera, smiling naturally, just showing",
            "Problem": f"Model still holding {pn}, gentle expression, product clearly visible",
            "Discovery": f"Model examining {pn}, slight head movement, product still in hands",
            "Features": f"Close-up of {pn}, product texture and packaging detail visible",
            "Transformation": f"Model presenting {pn} proudly, product in focus",
            "CTA": f"Final product showcase, {pn} in frame, model smiling warmly",
        }
    
    # ── Default: generic ──
    else:
        return {
            "Hook": f"Model holding {pn}, product clearly visible, natural opening",
            "Problem": f"{pn} shown in context, viewer attention drawn to product",
            "Discovery": f"Model interacting with {pn}, natural movement",
            "Features": f"Close-up details of {pn}, texture and build visible",
            "Transformation": f"Result or benefit of {pn} shown, improvement visible",
            "CTA": f"Final showcase, {pn} in focus, encouraging shot",
        }


# ═══════════════════════════════════════════════════════════════════════════
# STEP 7: TTS (Gemini)
# ═══════════════════════════════════════════════════════════════════════════

def generate_voice(
    text: str,
    voice: str = "Aoede",
    run_id: str = "",
    target_gender: str = "",
) -> str:
    """Step 7: Generate Thai voice via Gemini TTS (Gemini-only, no fallback).

    Voice is chosen by target_gender when known:
      - male   -> Charon (Gemini deep male narrator)
      - female -> Aoede (Gemini warm female)
      - empty  -> verbatim 'voice' or Gemini female default (Aoede)
    """
    logger.info(f"Step 7/9: TTS (Gemini, gender={target_gender or 'auto'})")
    logger.info(f"  Text: {text[:50]}...")

    output_path = str(TMP_DIR / f"voice_{run_id}.wav")

    # Gemini-only TTS. Gender from product profile wins; no Edge TTS in this module.
    from gemini_tts import gemini_text_to_speech, get_voice_for_gender
    if target_gender in ("male", "female"):
        gemini_voice = get_voice_for_gender(target_gender)
    else:
        gemini_voice = voice or "Aoede"

    try:
        tts_path = gemini_text_to_speech(text, output_path=output_path, voice=gemini_voice)
        if tts_path and Path(tts_path).exists():
            logger.info(f"  Gemini TTS OK: {tts_path}")
            return tts_path
    except Exception as e:
        logger.error(f"Gemini TTS failed: {e}")

    return ""
# ═══════════════════════════════════════════════════════════════════════════
# STEP 8: Generate Video (Prodia Wan 2.7 Sync API)
# ═══════════════════════════════════════════════════════════════════════════

# ── Shared Prodia v2 Async Client ──
from prodia_client import ProdiaV2Client, ProdiaV2Error, ProdiaValidationError


def _convert_to_wav(audio_path: str) -> str:
    """Convert TTS audio to 16kHz mono PCM WAV for accurate Prodia Lip-sync."""
    if not audio_path or not os.path.exists(audio_path):
        return audio_path
    wav_path = str(Path(audio_path).parent / f"{Path(audio_path).stem}_16k.wav")
    try:
        import subprocess
        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            wav_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 500:
            logger.info(f"Converted audio to 16kHz WAV for Lip-sync: {wav_path}")
            return wav_path
    except Exception as e:
        logger.warning(f"Audio WAV conversion notice ({e}), using original file: {audio_path}")
    return audio_path


def generate_video(
    image_path: str,
    prompt: str,
    duration: int = 8,
    resolution: str = "720P",
    audio_path: Optional[str] = None,
    negative_prompt: Optional[str] = None,
) -> tuple:
    """
    Step 8: Generate video via Wan 2.7 Async API (shared ProdiaV2Client)
    """
    logger.info(f"Step 8/9: Generate video (Wan 2.7, {resolution})")
    logger.info(f"  Prompt: {prompt}")

    # Read image bytes
    if image_path.startswith("http://") or image_path.startswith("https://"):
        resp = requests.get(image_path, timeout=30)
        resp.raise_for_status()
        image_data = resp.content
    else:
        with open(image_path, "rb") as f:
            image_data = f.read()

    # Convert audio to clean 16kHz WAV for Prodia Lip Sync
    audio_bytes = None
    if audio_path:
        valid_wav_path = _convert_to_wav(audio_path)
        logger.info(f"  Audio: {Path(valid_wav_path).stat().st_size} bytes (sending 16kHz WAV to Prodia for lip-sync)")
        with open(valid_wav_path, "rb") as f:
            audio_bytes = f.read()

    # ── Generate via shared client ──
    client = ProdiaV2Client(token=PRODIA_TOKEN())

    try:
        neg_p = (
            negative_prompt
            or "no text, no watermark, blurry, distorted, extra limbs, bad face, deformed, "
            "gibberish text, fake Thai script, distorted Thai characters, illegible text, "
            "unnatural facial features, oversaturated colors"
        )
        result = client.generate_video(
            prompt=prompt,
            input_image=image_data,
            duration=duration,
            resolution=resolution,
            audio_bytes=audio_bytes,
            job_type="inference.wan2-7.img2vid.v1",
            negative_prompt=neg_p,
        )

        output_url = result.get("output_url", "")
        price = result.get("price", {})
        cost_video = float(price.get("dollars", 0))

        if not output_url:
            raise RuntimeError(f"No output URL in result: {result.get('result_raw', {})}")

        # Download the video (Prodia output needs auth)
        auth_headers = {"Authorization": f"Bearer {PRODIA_TOKEN()}"} if "prodia.com" in (output_url or "") else {}
        video_resp = requests.get(output_url, headers=auth_headers, timeout=60)
        video_resp.raise_for_status()

        result_path = TMP_DIR / f"img2vid_{uuid.uuid4().hex[:8]}.mp4"
        with open(result_path, "wb") as f:
            f.write(video_resp.content)

        file_size = result_path.stat().st_size
        logger.info(f"  Video OK ({file_size} bytes, {resolution}): {result_path}")
        logger.info(f"  Cost: ${cost_video:.4f}")
        # Verify that the generated video contains an audio stream for lip‑sync
        if not has_audio_track(str(result_path)):
            logger.error("Wan 2.7 returned video without audio track – lip sync failed")
            raise RuntimeError("Lip sync failure: generated video lacks audio track")

        return str(result_path), cost_video
    except Exception as e:
        logger.error(f"  Prodia Wan 2.7 Video generation failed: {e}")
        raise RuntimeError(f"Prodia Wan 2.7 Video generation failed: {e}")

def _generate_fallback_video_from_image(image_path: str, duration: int = 15) -> str:
    """Generate a high-quality 1080x1920 video with smooth zoompan from a still image via FFmpeg."""
    fallback_path = TMP_DIR / f"img2vid_fallback_{uuid.uuid4().hex[:8]}.mp4"
    logger.info(f"Generating FFmpeg video fallback from image: {image_path}")
    
    local_img = image_path
    if str(image_path).startswith("http://") or str(image_path).startswith("https://"):
        local_img = TMP_DIR / f"temp_img_{uuid.uuid4().hex[:8]}.png"
        r = requests.get(image_path, timeout=30)
        with open(local_img, "wb") as f:
            f.write(r.content)
            
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(local_img),
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0015,1.2)':d={duration*25}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920",
        "-r", "25",
        str(fallback_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    logger.info(f"FFmpeg Video Fallback Created OK -> {fallback_path}")
    return str(fallback_path)

def has_audio_track(video_path: str) -> bool:
    """Check if video contains an audio stream using ffprobe.
    Returns False on any error.
    """
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return bool(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Failed to probe audio track for {video_path}: {e}")
        return False

def _probe_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe. Returns 0 on error."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Failed to probe duration for {video_path}: {e}")
    return 0.0


def compose_video(
    video_paths: list,
    voice_path: Optional[str] = None,
    run_id: str = "",
    bgm_style: str = "chill_loft",
    target_duration: int = 0,
    voice_speed: float = 1.3,
) -> str:
    """
    Step 9: Compose final video (merge voice + BGM + concat scenes)

    Args:
        video_paths: list ของ video paths จาก Step 8
        voice_path: path ของ voice จาก Step 7 (None = ไม่มี voiceover)
        run_id: สำหรับสร้าง filename
        bgm_style: สไตล์เพลงพื้นหลัง
        voice_speed: ความเร็วเสียง 1.0=ปกติ 1.3=เร่งสปีด (default ASMR/Sale voice)

    Returns:
        str: path ของ final video
    """
    logger.info(f"Step 9/9: Compose (FFmpeg)")

    # Step 9a: Concat scenes (filter None, fallback gracefully)
    valid_paths = [vp for vp in video_paths if vp is not None]
    logger.info(f"  9a: {len(valid_paths)}/{len(video_paths)} valid scenes")

    if not valid_paths:
        raise RuntimeError("No valid videos to compose (all None)")

    concat_path = TMP_DIR / f"concat_{run_id}.mp4"
    if len(valid_paths) > 1:
        concat_videos(valid_paths, concat_path)
    else:
        shutil.copy2(valid_paths[0], concat_path)

    # Step 9b: Force-merge Gemini TTS voiceover audio into the video
    final_path = concat_path
    if voice_path and Path(voice_path).exists():
        logger.info(f"  9b: Merging TTS voiceover audio {voice_path} into final video")
        voiced_path = STORAGE_DIR / f"affiliate_{run_id}_voiced.mp4"
        cmd_voice = [
            "ffmpeg", "-y",
            "-i", str(concat_path),
            "-i", str(voice_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            str(voiced_path)
        ]
        try:
            subprocess.run(cmd_voice, check=True, capture_output=True, timeout=60)
            if voiced_path.exists() and voiced_path.stat().st_size > 1000:
                final_path = voiced_path
                logger.info(f"  9b: Voiceover merged successfully -> {final_path}")
        except Exception as ve:
            logger.error(f"  9b: Merging voiceover failed ({ve}), using concat video")
    else:
        final_path = concat_path


    # Step 9c: Add BGM
    if bgm_style:
        logger.info(f"  9c: Add BGM ({bgm_style})")
        bgm_path = get_bgm_path(bgm_style)

        if bgm_path.exists():
            bgm_output = STORAGE_DIR / f"affiliate_{run_id}_bgm.mp4"
            # Probe actual video duration so BGM is trimmed to match exactly
            actual_dur = _probe_duration(str(final_path))
            if actual_dur <= 0:
                actual_dur = float(target_duration) if target_duration > 0 else 15.0
            logger.info(f"    Video duration: {actual_dur:.2f}s, BGM: {bgm_path.name}")

            # Mix BGM under voiceover: BGM at low volume (0.15), voice stays full.
            # Use amix with normalize=0 so voice volume is NOT reduced by BGM.
            try:
                cmd_mix = [
                    "ffmpeg", "-y",
                    "-i", str(final_path),
                    "-stream_loop", "-1",
                    "-i", str(bgm_path),
                    "-filter_complex",
                    "[1:a]volume=0.15[bg];[0:a][bg]amix=inputs=2:duration=longest:normalize=0[out]",
                    "-map", "0:v",
                    "-map", "[out]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-t", f"{actual_dur:.2f}",
                    str(bgm_output),
                ]
                subprocess.run(cmd_mix, check=True, capture_output=True, timeout=60)
                logger.info(f"    BGM mixed (trimmed to {actual_dur:.2f}s)")
                final_path = bgm_output
            except Exception as e:
                logger.warning(f"    BGM mix failed ({e}), trying BGM-only")
                # Fallback: just copy video + BGM as sole audio
                try:
                    cmd_bgm = [
                        "ffmpeg", "-y",
                        "-i", str(concat_path),  # use original video with audio
                        "-i", str(bgm_path),
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-t", f"{actual_dur:.2f}",
                        str(bgm_output),
                    ]
                    subprocess.run(cmd_bgm, check=True, capture_output=True, timeout=60)
                    logger.info(f"    BGM-only added (trimmed to {actual_dur:.2f}s)")
                    final_path = bgm_output
                except Exception as e2:
                    logger.warning(f"    BGM-only also failed: {e2}")

    logger.info(f"  Final: {final_path}")
    return str(final_path)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN: Run Full Pipeline v6
# ═══════════════════════════════════════════════════════════════════════════

def run_pipeline(
    product_name: str,
    product_image: Optional[str] = None,
    recipe_name: str = "tus",
    voice: str = "Aoede",
    bgm_style: str = "chill_loft",
    description: Optional[str] = None,
    ugc_style: str = "holding",
    external_job_id: Optional[str] = None,
    duration: int = 15,
    image_prompt: Optional[str] = None,
    video_prompt: Optional[str] = None,
    video_prompts: Optional[list] = None,
    negative_prompt: Optional[str] = None,
    script: Optional[str] = None,
    gender: Optional[str] = None,
    age: Optional[str] = None,
    **kwargs,
) -> dict:
    """
    Run full Affiliate Pipeline v6 (9 Steps ตาม PIPELINE_STRUCTURE.md)

    Args:
        product_name: ชื่อสินค้า
        product_image: URL ของรูปสินค้า (required!)
        recipe_name: ชื่อ recipe (tus, etsy)
        voice: ชื่อเสียง TTS
        bgm_style: สไตล์เพลงพื้นหลัง
        description: คําอธิบายสินค้า (optional)
        external_job_id: job_id จาก caller (ถ้ามี) — ใช้แทนการ gen เอง เพื่อให้ pipeline_logs.db
                         ตรงกับ pipeline.db ใน tiktok-ugc-studio
        image_prompt: รูป prompt ที่เตรียมมาแล้ว (ถ้ามีจะไม่ gen ใหม่)
        video_prompt: วิดีโอ prompt ที่เตรียมมาแล้ว (ใช้ fallback ถ้า video_prompts ไม่มี)
        video_prompts: รายการวิดีโอ prompts ต่อ scene (ถ้ามีจะไม่ gen ใหม่)
        negative_prompt: negative prompt ที่เตรียมมาแล้ว
        script: script ที่เตรียมมาแล้ว (ถ้ามีจะไม่ gen ใหม่)

    Returns:
        dict: {
            run_id, final_path, duration, cost_estimate, cost_breakdown,
            product_profile, recipe, script, image_path, video_paths
        }
    """
    run_id = uuid.uuid4().hex[:8]
    job_id = external_job_id or f"vid_{run_id}"

    logger.info(f"{'='*60}")
    logger.info(f"Pipeline v6 - Run {run_id}")
    logger.info(f"{'='*60}")
    logger.info(f"Product: {product_name}")
    logger.info(f"Image: {product_image}")

    if not product_image:
        product_image = _resolve_product_image(product_name)
        if product_image:
            logger.info(f"  Image resolved from tus_products.db: {product_image}")

    logger.info(f"Recipe: {recipe_name}")
    logger.info(f"{'='*60}")

    # Initialize pipeline logger
    try:
        start_job(job_id, {
            'product_title': product_name,
            'product_image': product_image,
            'product_description': description,
            'recipe_name': recipe_name,
            'voice': voice,
            'ugc_style': ugc_style,
        })
    except Exception as e:
        logger.warning(f"Pipeline logger start failed: {e}")

    # ── Validate ugc_style from Schema Engine ──
    _orig_ugc = ugc_style
    ugc_style = validate_ugc_style(ugc_style)
    if ugc_style != _orig_ugc:
        logger.warning(f"  ugc_style '{_orig_ugc}' not valid, using '{ugc_style}'")

    features = kwargs.get("features", "")
    pipeline_start = time.time()
    cost_image = 0.0
    cost_voice = 0.0
    cost_video = 0.0

    try:
        # ── STEP 1: Analyze ──
        step_start = time.time()
        product_profile = analyze_product(product_name, product_image, description, ugc_style=ugc_style, gender=gender or "", target_age=age or "", features=features)
        analyze_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'analyze', {'duration_ms': analyze_duration})
        except Exception:
            pass

        # ── STEP 2: Load Recipe ──
        step_start = time.time()
        recipe = load_recipe(recipe_name)
        recipe_duration = int((time.time() - step_start) * 1000)
        num_scenes = len(recipe.get("scenes", []))
        total_duration = duration if duration > 0 else recipe.get("total_duration", 8)

        try:
            update_step(job_id, 'recipe', {'duration_ms': recipe_duration, 'scenes': num_scenes})
        except Exception:
            pass

        # ── STEP 3: Generate Script (skip if pre-computed) ──
        if not script:
            step_start = time.time()
            script = generate_script(product_name, product_profile, recipe, ugc_style=ugc_style)
            script_duration = int((time.time() - step_start) * 1000)
        else:
            script_duration = 0
            logger.info(f"Step 3/9: Skipped (using pre-computed script)")

        try:
            update_step(job_id, 'script', {'duration_ms': script_duration, 'script': script[:100]})
        except Exception:
            pass

        # ── STEP 4: Build Image Prompt (skip if pre-computed) ──
        if not image_prompt:
            step_start = time.time()
            image_prompt = build_image_prompt(product_name, product_profile, recipe)
            img_prompt_duration = int((time.time() - step_start) * 1000)
        else:
            img_prompt_duration = 0
            logger.info(f"Step 4/9: Skipped (using pre-computed image_prompt)")

        try:
            update_step(job_id, 'image_prompt', {'duration_ms': img_prompt_duration})
        except Exception:
            pass

        # ── STEP 5: Generate Image ──
        step_start = time.time()
        img_url, cost_image = generate_image(image_prompt, product_image)
        img_path = TMP_DIR / f"image_{run_id}.png"
        download_file(img_url, img_path)
        image_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'image_gen', {'duration_ms': image_duration, 'output_path': str(img_path)})
            update_cost(job_id, 'image', cost_image)
        except Exception:
            pass

        # ── STEP 6: Build Video Prompts (skip if pre-computed) ──
        if not video_prompts and video_prompt:
            video_prompts = [video_prompt]
            vid_prompt_duration = 0
            logger.info(f"Step 6/9: Skipped (using pre-computed video_prompt)")
        elif not video_prompts:
            # Prefer Gemini video_prompt from analyze_product() (Step 1) — it is a
            # full descriptive narrative, not a keyword list. Fall back to the
            # recipe-template builder only when Gemini did not produce one.
            gemini_vp = product_profile.get("_video_prompt", "")
            if gemini_vp:
                video_prompts = [gemini_vp]
                vid_prompt_duration = 0
                logger.info(f"Step 6/9: Using Gemini video_prompt from analyze_product()")
            else:
                step_start = time.time()
                video_prompts = build_video_prompts(product_profile, recipe, str(img_path), ugc_style=ugc_style)
                vid_prompt_duration = int((time.time() - step_start) * 1000)
        else:
            vid_prompt_duration = 0
            logger.info(f"Step 6/9: Skipped (using pre-computed video_prompts)")

        try:
            update_step(job_id, 'video_prompts', {'duration_ms': vid_prompt_duration, 'count': len(video_prompts)})
        except Exception:
            pass

        # Save all prompts + script to logger
        try:
            update_prompts(job_id, {
                'image_prompt': image_prompt,
                'video_prompts': video_prompts,
                'script': script,
                'negative_prompt': negative_prompt if negative_prompt else '',
                'hashtags': product_profile.get('hashtags', []),
            })
        except Exception as e:
            logger.warning(f"Logger update_prompts failed: {e}")

        # ── STEP 7: TTS (ข้ามถ้าไม่มี voice หรือ recipe ไม่ได้ตั้งค่า tts) ──
        if script:
            step_start = time.time()
            voice_path = generate_voice(script, voice=voice, run_id=run_id, target_gender=product_profile.get("target_gender", ""))
            tts_duration = int((time.time() - step_start) * 1000)
            cost_voice = (len(script) / 1000) * 0.0001

            try:
                update_step(job_id, 'tts', {'duration_ms': tts_duration, 'output_path': voice_path})
                update_cost(job_id, 'voice', cost_voice)
            except Exception:
                pass
        else:
            logger.info(f"Step 7/9: Skipped (no voice)")
            voice_path = None
            cost_voice = 0.0

        # ── STEP 8: Generate 1 Video (Wan 2.7 Sync, 1 clip full duration) ──
        # WHY 1 clip: Wan 2.7 img2vid generates from a SINGLE image reference.
        # Multiple independent clips from the same static image = jarring cuts,
        # same product angle every scene, zero visual continuity.
        # 1 continuous generation = smooth motion, natural flow.
        step_start = time.time()
        video_paths = []
        
        vprompt = video_prompts[0] if video_prompts else "Product showcase, smooth motion, elegant presentation"
        logger.info(f"  Generating 1 continuous video ({total_duration}s): {vprompt[:80]}...")
        
        vid_path, cost_video = generate_video(
            image_path=str(img_path),
            prompt=vprompt,
            duration=total_duration,
            audio_path=voice_path,
            negative_prompt=negative_prompt,
        )
        video_paths.append(vid_path)
        
        video_gen_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'video_gen', {
                'duration_ms': video_gen_duration,
                'output_path': video_paths[-1] if video_paths else ''
            })
            update_cost(job_id, 'video', cost_video)
        except Exception:
            pass

        # ── STEP 9: Compose ──
        final_duration = recipe.get("total_duration", 0)
        final_path = compose_video(video_paths, voice_path, run_id, bgm_style, target_duration=final_duration)

        # Cost summary
        cost_total = cost_image + cost_voice + cost_video
        total_duration_ms = int((time.time() - pipeline_start) * 1000)

        logger.info(f"{'='*60}")
        logger.info(f"Pipeline v6 complete: {final_path}")
        logger.info(f"Cost: ${cost_total:.4f}")
        logger.info(f"Time: {total_duration_ms/1000:.1f}s")
        logger.info(f"{'='*60}")

        # Log completion
        try:
            complete_job(
                job_id,
                final_path=str(final_path),
                total_duration_ms=total_duration_ms,
                total_video_duration=total_duration,
                total_scenes=num_scenes
            )
        except Exception as e:
            logger.warning(f"Pipeline logger complete failed: {e}")

        return {
            "run_id": run_id,
            "final_path": str(final_path),
            "duration": total_duration,
            "cost_estimate": round(cost_total, 4),
            "cost_breakdown": {
                "image": round(cost_image, 4),
                "voice": round(cost_voice, 4),
                "video": round(cost_video, 4),
                "total": round(cost_total, 4),
            },
            "product_profile": {k: v for k, v in product_profile.items() if not k.startswith("_")},
            "hashtags": product_profile.get('hashtags', []),
            "recipe": recipe_name,
            "script": script,
            "image_path": str(img_path),
            "video_paths": video_paths,
            "job_id": job_id,
        }

    except Exception as e:
        try:
            fail_job(job_id, str(e), 'unknown')
        except Exception as e2:
            logger.warning(f"Pipeline logger fail failed: {e2}")
        raise


# ─── CLI ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Affiliate Video Pipeline v6")
    parser.add_argument("--product-name", required=True, help="ชื่อสินค้า")
    parser.add_argument("--product-image", required=True, help="รูปสินค้า (URL/path)")
    parser.add_argument("--recipe", default="tus", help="Recipe name")
    parser.add_argument("--voice", default="Aoede", help="TTS voice")
    parser.add_argument("--bgm", default="chill_loft", help="BGM style")
    parser.add_argument("--description", default="", help="คําอธิบายสินค้า")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    result = run_pipeline(
        product_name=args.product_name,
        product_image=args.product_image,
        recipe_name=args.recipe,
        voice=args.voice,
        bgm_style=args.bgm,
        description=args.description,
    )

    print("\n✅ Pipeline v6 Done!")
    print(f"  Final: {result['final_path']}")
    print(f"  Duration: {result['duration']}s")
    print(f"  Cost: ${result['cost_estimate']}")
    print(f"  Script: {result['script'][:80]}...")