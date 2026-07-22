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
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests

# Add erp-stack to path for shared_config
_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from shared_config import PRODIA_TOKEN, GEMINI_API_KEY

# ─── Schema Engine UGC Style Client ─────────────────────────────────
_ugc_client_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompt-builder-service")
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

def analyze_product(product_name: str, product_image: str = None, description: str = "", ugc_style: str = "holding") -> dict:
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
        # Fallback: basic profile
        return {
            "category": "other",
            "target_gender": "unisex",
            "target_age": "20-35",
            "target_audience": "ทุกคน",
            "customer_problem": "",
            "main_benefit": "คุณภาพดี",
            "hashtags": [product_name.replace(" ", "")[:20]],
            "setting": "clean modern lifestyle",
            "_image_prompt": f"{product_name}, product showcase, clean background",
            "_video_prompt": f"{product_name} showcase, smooth motion",
            "_negative_prompt": "no text, no watermark",
        }


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
    config = row.get("config", {})

    recipe = {
        "name": row.get("name", recipe_name),
        "description": row.get("description", ""),
        "version": row.get("version", "1.0"),
        "total_duration": row.get("total_duration", 15),
        "language": row.get("language", "th"),
        "default_style": row.get("default_style", "holding"),
        "scenes": config.get("scenes", []),
        "video_model": config.get("video_model", "wan2.7"),
        "video_count": config.get("video_count", 1),
        "ugc_styles": config.get("ugc_styles", ["holding", "review", "usage", "talking"]),
        "voice_tone": config.get("voice_tone", "friendly, authentic, enthusiastic"),
        "target_audience": config.get("target_audience", "Thai TikTok users"),
        "image_generation": config.get("image_generation", {}),
        "video_generation": config.get("video_generation", {}),
        "tts": config.get("tts"),  # None = no voiceover
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
) -> str:
    """
    Step 3: Generate script via Gemini

    Args:
        product_name: ชื่อสินค้า
        product_profile: ผลจาก analyze_product()
        recipe: ผลจาก load_recipe()

    Returns:
        str: full_script
    """
    logger.info(f"Step 3/9: Generate script (Gemini)")

    try:
        # Import script_gen จาก modules/video
        sys.path.insert(0, str(Path(__file__).parent))
        from script_gen import generate_tiktok_review_script

        result = generate_tiktok_review_script(
            product_name=product_name,
            customer_problem=product_profile.get("customer_problem", ""),
            main_benefit=product_profile.get("main_benefit", ""),
            target_audience=product_profile.get("target_audience", ""),
            tone="เป็นกันเอง พูดเร็ว",
            duration=f"{recipe.get('total_duration', 8)}s",
        )

        script = result.get("script", "")
        logger.info(f"  Script: {script[:50]}... (uses_llm={result.get('uses_llm')})")

        return script

    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        # Fallback: template script
        return f"{product_profile.get('customer_problem', 'ปัญหาที่เจอบ่อย')} ใช่ไหมคะ? วันนี้เรามี {product_name} มาบอกต่อ {product_profile.get('main_benefit', 'คุณภาพดี')} ค่ะ กดตะกร้าเลย!"


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
        logger.info(f"  Image prompt: {image_prompt[:60]}...")
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
    logger.info(f"  Prompt: {prompt[:40]}...")
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
        logger.error(f"Image generation failed: {e}")
        raise


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
        ugc_style: UGC style — "holding" uses generic hold for ALL scenes

    Returns:
        list: video_prompts (1 prompt per scene)
    """
    logger.info(f"Step 6/9: Build video prompts (ugc_style={ugc_style})")

    scenes = recipe.get("scenes", [])
    video_prompts = []

    setting = product_profile.get("setting", "clean modern lifestyle")
    category = product_profile.get("category", "other")

    # Lighting map (simple version)
    lighting_map = {
        "beauty": "soft diffused natural window lighting",
        "tools": "bright functional lighting",
        "electronics": "clean bright studio lighting",
        "food": "warm golden hour lighting",
        "fashion": "bright studio lighting",
        "home": "bright natural daylight",
        "other": "soft natural lighting",
    }
    lighting = lighting_map.get(category, "soft natural lighting")

    # ── For "holding" style: ALL scenes use video_prompt from prompt-builder ──
    # IMPORTANT: Use the _video_prompt from prompt-builder-service (has packaging, clothing, hair, age)
    # Not the hardcoded hold_base — prompt builder has all the rich details
    model_age = random.randint(18, 25)
    
    if ugc_style == "holding":
        # Try to use prompt builder's video prompt (more detailed than hardcoded)
        prompt_builder_vp = product_profile.get("_video_prompt", "")
        if prompt_builder_vp and len(prompt_builder_vp) > 50:
            # Replace hardcoded 25 with randomized age
            vp_fixed_age = re.sub(r'\b25\s+years?\s+old\b', f'{model_age} years old', prompt_builder_vp)
            enhanced = vp_fixed_age
        else:
            # Fallback: simple hold prompt
            thai_face = "Ethnic Thai woman with porcelain white glowing skin, monolid eyes, Southeast Asian features"
            enhanced = (
                f"{thai_face}, {model_age} years old, holding product gently in both hands, product packaging facing camera, "
                f"slight head tilt, natural breathing motion. "
                f"Do NOT open or apply the product. No squeezing, no pumping, no spraying. "
                f"Setting: {setting}. {lighting}. "
                f"9:16 portrait, smooth natural motion, no text, no watermark"
            )
        
        # Same prompt for all scenes — no scene-specific usage action
        for scene in scenes:
            video_prompts.append(enhanced)
        logger.info(f"  Generated {len(video_prompts)} video prompts")
        return video_prompts

    # ── Non-holding styles: scene-specific prompts ──
    for scene in scenes:
        scene_name = scene.get("name", "Scene")
        scene_prompt = scene.get("prompt", "")
        enhanced = f"{scene_prompt}. Setting: {setting}. {lighting}. 9:16 portrait, smooth natural motion."

        # Add scene-specific details for non-holding styles
        if scene_name == "Hook":
            enhanced += " Beautiful opening shot, product clearly visible"
        elif scene_name == "Problem":
            enhanced += " Person showing concern, relatable emotion"
        elif scene_name == "Discovery":
            enhanced += " Excited expression, discovering product"
        elif scene_name == "Features":
            enhanced += " Close-up texture, product in use"
        elif scene_name == "Transformation":
            enhanced += " Before-after comparison, clear improvement"
        elif scene_name == "CTA":
            enhanced += " Final product shot, encouraging purchase"

        video_prompts.append(enhanced)

    logger.info(f"  Generated {len(video_prompts)} video prompts")

    return video_prompts


# ═══════════════════════════════════════════════════════════════════════════
# STEP 7: TTS (Gemini)
# ═══════════════════════════════════════════════════════════════════════════

def generate_voice(
    text: str,
    voice: str = "Aoede",
    run_id: str = "",
) -> str:
    """
    Step 7: Generate voice via Gemini TTS

    Args:
        text: script จาก Step 3
        voice: ชื่อเสียง (Aoede, Wise_Woman, etc.)
        run_id: สําหรับสร้าง filename

    Returns:
        str: path ของไฟล์เสียง
    """
    logger.info(f"Step 7/9: TTS (Gemini)")
    logger.info(f"  Text: {text[:50]}...")

    try:
        from gemini_tts import gemini_text_to_speech

        output_path = str(TMP_DIR / f"voice_{run_id}.mp3")
        tts_path = gemini_text_to_speech(text, output_path=output_path, voice=voice)

        if tts_path and Path(tts_path).exists():
            logger.info(f"  TTS OK: {tts_path}")
            return tts_path
        else:
            raise RuntimeError(f"TTS returned invalid path: {tts_path}")

    except Exception as e:
        logger.error(f"TTS failed: {e}")
        raise


# ═══════════════════════════════════════════════════════════════════════════
# STEP 8: Generate Video (Prodia Wan 2.7 Sync API)
# ═══════════════════════════════════════════════════════════════════════════

# ── Shared Prodia v2 Async Client ──
from prodia_client import ProdiaV2Client, ProdiaV2Error, ProdiaValidationError


def generate_video(
    image_path: str,
    prompt: str,
    duration: int = 8,
    resolution: str = "720P",
    audio_path: Optional[str] = None,
) -> tuple:
    """
    Step 8: Generate video via Wan 2.7 Async API (shared ProdiaV2Client)

    Uses the shared prodia_client.ProdiaV2Client for job creation, polling,
    and price tracking through /v2/job/async.

    Args:
        image_path: path หรือ URL ของ image จาก Step 5
        prompt: video_prompt จาก Step 6
        duration: ความยาวคลิป (default 8s)
        resolution: 720P (per user spec)
        audio_path: path ของ TTS audio สำหรับ lip-sync (optional)

    Returns:
        tuple: (video_path, cost_usd)
    """
    logger.info(f"Step 8/9: Generate video (Wan 2.7, {resolution})")
    logger.info(f"  Prompt: {prompt[:80]}...")

    # Read image bytes
    if image_path.startswith("http://") or image_path.startswith("https://"):
        resp = requests.get(image_path, timeout=30)
        resp.raise_for_status()
        image_data = resp.content
    else:
        with open(image_path, "rb") as f:
            image_data = f.read()

    # Read audio bytes if provided
    audio_bytes = None
    if audio_path:
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        logger.info(f"  Audio: {len(audio_bytes)} bytes")

    # ── Generate via shared client ──
    client = ProdiaV2Client(token=PRODIA_TOKEN())

    try:
        result = client.generate_video(
            prompt=prompt,
            input_image=image_data,
            duration=duration,
            resolution=resolution,
            audio_bytes=audio_bytes,
            job_type="inference.wan2-7.img2vid.v1",
            negative_prompt="low resolution, error, worst quality, deformed",
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

        return str(result_path), cost_video

    except ProdiaValidationError as e:
        raise RuntimeError(f"Wan 2.7 config rejected: {e}")
    except ProdiaV2Error as e:
        raise RuntimeError(f"Wan 2.7 failed: {e}")
    except Exception as e:
        raise RuntimeError(f"Wan 2.7 error: {e}")
def compose_video(
    video_paths: list,
    voice_path: Optional[str] = None,
    run_id: str = "",
    bgm_style: str = "chill_loft",
) -> str:
    """
    Step 9: Compose final video (merge voice + BGM + concat scenes)

    Args:
        video_paths: list ของ video paths จาก Step 8
        voice_path: path ของ voice จาก Step 7 (None = ไม่มี voiceover)
        run_id: สำหรับสร้าง filename
        bgm_style: สไตล์เพลงพื้นหลัง

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

    # Step 9b: Merge voiceover with the concatenated video (ถ้ามี voice)
    if voice_path:
        logger.info(f"  9b: Merge voiceover")
        voiced_path = STORAGE_DIR / f"affiliate_{run_id}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(concat_path),
            "-i", str(voice_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-af", "atempo=1.3",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(voiced_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            # Verify output has video stream (Gemini TTS raw audio can break merge)
            vf_size = voiced_path.stat().st_size
            if vf_size < 5000:  # < 5KB = broken
                logger.warning(f"    Voiceover merge produced tiny file ({vf_size}B), using concat")
                final_path = concat_path
            else:
                logger.info(f"    Voiceover merged")
                final_path = voiced_path
        except Exception as e:
            logger.warning(f"    Voiceover merge failed ({e}), using silent video")
            final_path = concat_path
    else:
        logger.info(f"  9b: No voiceover — using silent video")
        final_path = concat_path

    # Step 9c: Add BGM
    if bgm_style:
        logger.info(f"  9c: Add BGM ({bgm_style})")
        bgm_map = {
            "chill_loft": "bg_chill.mp3",
            "informative_jazz": "bg_jazz.mp3",
            "energetic_edm": "bg_edm.mp3",
            "upbeat_pop": "bg_upbeat.mp3",
            "luxury_jazz": "bg_jazz.mp3",
            "asmr": "bg_ambient.mp3",
        }
        bgm_filename = bgm_map.get(bgm_style, "bg_chill.mp3")
        bgm_path = STORAGE_DIR / "sounds" / bgm_filename

        if bgm_path.exists():
            bgm_output = STORAGE_DIR / f"affiliate_{run_id}_bgm.mp4"
            # Strategy: mix BGM with video audio. If video has no usable audio, just copy BGM
            try:
                cmd_mix = [
                    "ffmpeg", "-y",
                    "-i", str(final_path),
                    "-i", str(bgm_path),
                    "-filter_complex",
                    "[1:a]volume=0.15[bg];[0:a][bg]amix=inputs=2:duration=first[out]",
                    "-map", "0:v",
                    "-map", "[out]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-shortest",
                    str(bgm_output),
                ]
                subprocess.run(cmd_mix, check=True, capture_output=True, timeout=60)
                logger.info(f"    BGM mixed")
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
                        "-shortest",
                        str(bgm_output),
                    ]
                    subprocess.run(cmd_bgm, check=True, capture_output=True, timeout=60)
                    logger.info(f"    BGM-only added")
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
    product_image: str,
    recipe_name: str = "tus",
    voice: str = "Aoede",
    bgm_style: str = "chill_loft",
    description: str = "",
    ugc_style: str = "holding",
    external_job_id: Optional[str] = None,
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

    pipeline_start = time.time()
    cost_image = 0.0
    cost_voice = 0.0
    cost_video = 0.0

    try:
        # ── STEP 1: Analyze ──
        step_start = time.time()
        product_profile = analyze_product(product_name, product_image, description, ugc_style=ugc_style)
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
        total_duration = recipe.get("total_duration", 8)

        try:
            update_step(job_id, 'recipe', {'duration_ms': recipe_duration, 'scenes': num_scenes})
        except Exception:
            pass

        # ── STEP 3: Generate Script ──
        step_start = time.time()
        script = generate_script(product_name, product_profile, recipe)
        script_duration = int((time.time() - step_start) * 1000)

        try:
            update_step(job_id, 'script', {'duration_ms': script_duration, 'script': script[:100]})
        except Exception:
            pass

        # ── STEP 4: Build Image Prompt ──
        step_start = time.time()
        image_prompt = build_image_prompt(product_name, product_profile, recipe)
        img_prompt_duration = int((time.time() - step_start) * 1000)

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

        # ── STEP 6: Build Video Prompts ──
        step_start = time.time()
        video_prompts = build_video_prompts(product_profile, recipe, str(img_path), ugc_style=ugc_style)
        vid_prompt_duration = int((time.time() - step_start) * 1000)

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
                'negative_prompt': '',
                'hashtags': product_profile.get('hashtags', []),
            })
        except Exception as e:
            logger.warning(f"Logger update_prompts failed: {e}")

        # ── STEP 7: TTS (ข้ามถ้าไม่มี voice หรือ recipe ไม่ได้ตั้งค่า tts) ──
        has_tts_config = bool(recipe.get("tts"))
        if voice and has_tts_config:
            step_start = time.time()
            voice_path = generate_voice(script, voice=voice, run_id=run_id)
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

        # ── STEP 8: Generate 1 Video (Wan 2.7 Sync, 1 scene) ──
        step_start = time.time()
        video_paths = []
        
        # 1 scene only — ใช้ prompt แรก (Hook) + duration เต็ม
        vprompt = video_prompts[0] if video_prompts else "Product showcase, smooth motion"
        logger.info(f"  Generating 1 video ({total_duration}s): {vprompt[:60]}...")
        
        vid_path, cost_video = generate_video(
            image_path=str(img_path),
            prompt=vprompt,
            duration=total_duration,
            audio_path=voice_path,
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
        final_path = compose_video(video_paths, voice_path, run_id, bgm_style)

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