"""
TikTok UGC Studio — Affiliate Video Pipeline v6 (Structure-based)
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

# Import pipeline logger (same directory)
from pipeline_logger import start_job, update_step, update_cost, complete_job, fail_job

logger = logging.getLogger("tiktok-ugc.pipeline_affiliate")

# ─── Config ────────────────────────────────────────────────────────────────

STORAGE_DIR = Path(__file__).parent / "storage"
TMP_DIR = STORAGE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

PRODIA_BASE = "https://inference.prodia.com/v2"
PRODIA_IMG2IMG_TYPE = "inference.nano-banana.img2img.v1"
PRODIA_IMG2VID_TYPE = "inference.wan2-7.img2vid.v1"

# Service URLs
IMAGE_GEN_URL = "http://localhost:8110/api/v1/image/generate"
PROMPT_BUILDER_URL = "http://localhost:8117"

# ─── Helpers ───────────────────────────────────────────────────────────────

def _prodia_headers():
    return {"Authorization": f"Bearer {PRODIA_TOKEN()}"}


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
    """Concat multiple videos with FFmpeg."""
    list_file = TMP_DIR / f"concat_{uuid.uuid4().hex}.txt"
    with open(list_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{Path(vp).absolute()}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(list_file), "-c", "copy", str(output_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink(missing_ok=True)
    return output_path


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: Analyze Product (Mistral)
# ═══════════════════════════════════════════════════════════════════════════

def analyze_product(product_name: str, product_image: str = None, description: str = "") -> dict:
    """
    Step 1: Analyze product via Mistral → product_profile
    
    Args:
        product_name: ชื่อสินค้า
        product_image: URL ของรูปสินค้า (optional)
        description: คำอธิบายสินค้า (optional)
    
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
    
    try:
        # Call Prompt Builder API
        url = f"{PROMPT_BUILDER_URL}/api/v1/build"
        payload = {
            "product_name": product_name,
            "description": description,
            "product_image": product_image or "",
            "ugc_style": "holding",  # default
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
    
    Args:
        recipe_name: ชื่อ recipe (tus, etsy)
    
    Returns:
        dict: recipe {
            name, total_duration, scenes: [...]
        }
    """
    logger.info(f"Step 2/9: Load recipe ({recipe_name})")
    
    recipe_path = Path(__file__).parent.parent.parent / "prompt-builder-service" / "recipes" / f"{recipe_name}.json"
    
    try:
        with open(recipe_path, "r", encoding="utf-8") as f:
            recipe = json.load(f)
        
        scenes = recipe.get("scenes", [])
        logger.info(f"  Recipe: {recipe_name}, {len(scenes)} scenes, {recipe.get('total_duration')}s")
        
        return recipe
        
    except Exception as e:
        logger.error(f"Recipe load failed: {e}, using default tus")
        # Fallback: basic 8s recipe
        return {
            "name": "tus",
            "total_duration": 8,
            "scenes": [
                {"name": "Hook", "duration_range": [0.5, 1.0], "prompt": "Close-up product shot"},
                {"name": "Problem", "duration_range": [1.5, 3.0], "prompt": "Person showing concern"},
                {"name": "Discovery", "duration_range": [1.0, 2.0], "prompt": "Excited expression discovering product"},
                {"name": "Features", "duration_range": [2.0, 3.0], "prompt": "Close-up texture product in use"},
                {"name": "Transformation", "duration_range": [1.0, 2.0], "prompt": "Before-after comparison"},
                {"name": "CTA", "duration_range": [0.5, 1.0], "prompt": "Final product shot encouraging purchase"},
            ]
        }


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
) -> str:
    """
    Step 5: Generate image via Prodia Nano Banana Img2Img
    
    Args:
        prompt: image_prompt จาก Step 4
        product_image: URL ของรูปสินค้า (reference)
        aspect_ratio: 9:16 (TikTok portrait)
    
    Returns:
        str: URL ของรูปที่สร้าง
    """
    logger.info(f"Step 5/9: Generate image (Nano Banana)")
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
        
        logger.info(f"  Image OK: {url[:60]}...")
        return url
        
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
) -> list:
    """
    Step 6: Build video prompts from recipe + image context
    
    Args:
        product_profile: ผลจาก analyze_product()
        recipe: ผลจาก load_recipe()
        image_path: path ของ image ที่สร้างแล้ว (Step 5)
    
    Returns:
        list: video_prompts (1 prompt per scene)
    """
    logger.info(f"Step 6/9: Build video prompts (from recipe + image)")
    
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
    
    for scene in scenes:
        scene_name = scene.get("name", "Scene")
        scene_prompt = scene.get("prompt", "")
        
        # Enhance prompt with image context + recipe
        enhanced = f"{scene_prompt}. Setting: {setting}. {lighting}. 9:16 portrait, smooth natural motion."
        
        # Add scene-specific details
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
        run_id: สำหรับสร้าง filename
    
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
# STEP 8: Generate Video (Prodia Wan 2.7)
# ═══════════════════════════════════════════════════════════════════════════

def generate_video(
    image_path: str,
    prompt: str,
    duration: int = 8,
) -> str:
    """
    Step 8: Generate video via Wan 2.7 img2vid
    
    Args:
        image_path: path ของ image จาก Step 5
        prompt: video_prompt จาก Step 6
        duration: ความยาวคลิป (วินาที)
    
    Returns:
        str: path ของไฟล์ video
    """
    logger.info(f"Step 8/9: Generate video (Wan 2.7)")
    logger.info(f"  Prompt: {prompt[:40]}...")
    logger.info(f"  Duration: {duration}s")

    # Read image bytes
    if image_path.startswith("http://") or image_path.startswith("https://"):
        resp = requests.get(image_path, timeout=30)
        resp.raise_for_status()
        image_data = resp.content
    else:
        with open(image_path, "rb") as f:
            image_data = f.read()

    config_payload = {
        "type": PRODIA_IMG2VID_TYPE,
        "config": {
            "prompt": prompt,
            "duration": duration,
            "negative_prompt": "low resolution, error, worst quality, deformed, blurry, disfigured face",
        }
    }

    files = [
        ("job", ("job.json", json.dumps(config_payload), "application/json")),
        ("input", ("image.png", image_data, "image/png")),
    ]

    try:
        resp = requests.post(
            f"{PRODIA_BASE}/job",
            headers=_prodia_headers(),
            files=files,
            timeout=300
        )
        resp.raise_for_status()

        ct = resp.headers.get("content-type", "")

        if "json" in ct:
            data = resp.json()
            state = data.get("state", {}).get("current", "")
            if state == "failed":
                raise RuntimeError(f"Wan 2.7 failed: {data.get('error')}")

            url = ""
            url_info = data.get("config", {}).get("url_info", [])
            if url_info and len(url_info) > 0:
                url = url_info[0].get("url", "")
            if not url:
                output = data.get("output", {})
                url = output.get("url", "") or output.get("video", {}).get("url", "")

            if not url:
                raise RuntimeError(f"No URL in response: {data}")

            vid_resp = requests.get(url, timeout=60)
            vid_resp.raise_for_status()
            result_path = TMP_DIR / f"img2vid_{uuid.uuid4().hex[:8]}.mp4"
            with open(result_path, "wb") as f:
                f.write(vid_resp.content)
            
            logger.info(f"  Video OK (downloaded)")
            return str(result_path)
        else:
            result_path = TMP_DIR / f"img2vid_{uuid.uuid4().hex[:8]}.mp4"
            with open(result_path, "wb") as f:
                f.write(resp.content)
            logger.info(f"  Video OK (binary MP4)")
            return str(result_path)

    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        raise


# ═══════════════════════════════════════════════════════════════════════════
# STEP 9: Compose (FFmpeg)
# ═══════════════════════════════════════════════════════════════════════════

def compose_video(
    video_paths: list,
    voice_path: str,
    run_id: str,
    bgm_style: str = "chill_loft",
) -> str:
    """
    Step 9: Compose final video (merge voice + BGM + concat scenes)
    
    Args:
        video_paths: list ของ video paths จาก Step 8
        voice_path: path ของ voice จาก Step 7
        run_id: สำหรับสร้าง filename
        bgm_style: สไตล์เพลงพื้นหลัง
    
    Returns:
        str: path ของ final video
    """
    logger.info(f"Step 9/9: Compose (FFmpeg)")
    
    # Step 9a: Merge voice into each video
    logger.info(f"  9a: Merge voice")
    merged_paths = []
    for i, vpath in enumerate(video_paths):
        merged = TMP_DIR / f"merged_{run_id}_{i}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(vpath),
            "-i", str(voice_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(merged),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            merged_paths.append(merged)
            logger.info(f"    Scene {i}: merged")
        except Exception as e:
            logger.warning(f"    Scene {i}: merge failed ({e}), using original")
            merged_paths.append(Path(vpath))
    
    # Step 9b: Concat scenes (ถ้ามีหลาย scene)
    logger.info(f"  9b: Concat {len(merged_paths)} scenes")
    if len(merged_paths) > 1:
        final_path = STORAGE_DIR / f"affiliate_{run_id}.mp4"
        concat_videos(merged_paths, final_path)
    else:
        final_path = STORAGE_DIR / f"affiliate_{run_id}.mp4"
        shutil.copy2(merged_paths[0], final_path)
    
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
            cmd = [
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
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=60)
                logger.info(f"    BGM added")
                final_path = bgm_output
            except Exception as e:
                logger.warning(f"    BGM failed: {e}")
    
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
) -> dict:
    """
    Run full Affiliate Pipeline v6 (9 Steps ตาม PIPELINE_STRUCTURE.md)
    
    Args:
        product_name: ชื่อสินค้า
        product_image: URL ของรูปสินค้า (required!)
        recipe_name: ชื่อ recipe (tus, etsy)
        voice: ชื่อเสียง TTS
        bgm_style: สไตล์เพลงพื้นหลัง
        description: คำอธิบายสินค้า (optional)
    
    Returns:
        dict: {
            run_id, final_path, duration, cost_estimate, cost_breakdown,
            product_profile, recipe, script, image_path, video_paths
        }
    """
    run_id = uuid.uuid4().hex[:8]
    job_id = f"vid_{run_id}"
    
    logger.info(f"{'='*60}")
    logger.info(f"Pipeline v6 — Run {run_id}")
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
            'recipe_name': recipe_name,
            'voice': voice,
        })
    except Exception as e:
        logger.warning(f"Pipeline logger start failed: {e}")

    pipeline_start = time.time()
    cost_image = 0.0
    cost_voice = 0.0
    cost_video = 0.0

    try:
        # ── STEP 1: Analyze ──
        step_start = time.time()
        product_profile = analyze_product(product_name, product_image, description)
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
        img_url = generate_image(image_prompt, product_image)
        img_path = TMP_DIR / f"image_{run_id}.png"
        download_file(img_url, img_path)
        image_duration = int((time.time() - step_start) * 1000)
        cost_image = 0.005
        
        try:
            update_step(job_id, 'image_gen', {'duration_ms': image_duration, 'output_path': str(img_path)})
            update_cost(job_id, 'image', cost_image)
        except Exception:
            pass

        # ── STEP 6: Build Video Prompts ──
        step_start = time.time()
        video_prompts = build_video_prompts(product_profile, recipe, str(img_path))
        vid_prompt_duration = int((time.time() - step_start) * 1000)
        
        try:
            update_step(job_id, 'video_prompts', {'duration_ms': vid_prompt_duration, 'count': len(video_prompts)})
        except Exception:
            pass

        # ── STEP 7: TTS ──
        step_start = time.time()
        voice_path = generate_voice(script, voice=voice, run_id=run_id)
        tts_duration = int((time.time() - step_start) * 1000)
        cost_voice = (len(script) / 1000) * 0.0001
        
        try:
            update_step(job_id, 'tts', {'duration_ms': tts_duration, 'output_path': voice_path})
            update_cost(job_id, 'voice', cost_voice)
        except Exception:
            pass

        # ── STEP 8: Generate Videos (per scene) ──
        step_start = time.time()
        video_paths = []
        video_duration = total_duration // num_scenes if num_scenes > 0 else 8
        
        for i in range(num_scenes):
            vprompt = video_prompts[i] if i < len(video_prompts) else "Product showcase, smooth motion"
            logger.info(f"  Scene {i+1}/{num_scenes}: {vprompt[:60]}...")
            
            vid_path = generate_video(
                image_path=str(img_path),
                prompt=vprompt,
                duration=video_duration,
            )
            video_paths.append(vid_path)

        cost_video = num_scenes * 0.03
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
            "recipe": recipe_name,
            "script": script,
            "image_path": str(img_path),
            "video_paths": video_paths,
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
    parser.add_argument("--description", default="", help="คำอธิบายสินค้า")
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