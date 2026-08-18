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
import re
import sys
import json
import time
import uuid
import logging
import random
import re
import subprocess
import shutil
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests

def get_bgm_path(bgm_style: str) -> Path:
    """Helper to resolve BGM path from style name."""
    bgm_map = {
        "chill_loft": "bg_chill.mp3",
        "informative_jazz": "bg_jazz.mp3",
        "energetic_edm": "bg_edm.mp3",
        "upbeat_pop": "bg_upbeat.mp3",
        "luxury_jazz": "bg_jazz.mp3",
        "asmr": "bg_ambient.mp3",
    }
    bgm_filename = bgm_map.get(bgm_style, "bg_chill.mp3")
    return STORAGE_DIR / "sounds" / bgm_filename

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

        # ── Beat-timed script จาก service (single source of truth) ──
        # timing_validation/scripts.full_script สร้างจาก router_config.scenes
        # (4-beat: hook→agitate→solve→cta) แล้ว → ใช้เป็น script หลักให้ sync กับ
        # 4-beat video prompt แทนการให้ Gemini gen ใหม่ที่หลุด beat
        _scripts = data.get("scripts", {}) or {}
        profile["_beat_timed_script"] = _scripts.get("full_script", "")
        profile["_script_tts_speed"] = (data.get("timing_validation", {}) or {}).get("tts_speed", 1.0)

        return profile

    except Exception as e:
        # NO hardcoded fallback profile. When the JSON-driven prompt-builder
        # fails we must fail loudly so it's fixable — a silently-substituted
        # hardcoded image/video/negative prompt would bypass your JSON prompt
        # sources and quietly produce off-brand output. ("break is break")
        logger.error(f"Analyze failed (prompt-builder unreachable/no prompt): {e}")
        raise RuntimeError(
            f"prompt-builder returned no usable prompt (refusing hardcoded fallback): {e}"
        ) from e


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
    try:
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
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        logger.warning(f"Schema Engine unreachable ({e}) — using default recipe")
        # Fallback: return a default recipe with standard scenes
        default_recipe = {
            "name": recipe_name,
            "description": "Default recipe (Schema Engine offline)",
            "version": "1.0",
            "total_duration": 15,
            "language": "th",
            "default_style": "holding",
            "scenes": [
                {"name": "hook", "duration": 5, "function": "hook"},
                {"name": "value", "duration": 5, "function": "value"},
                {"name": "cta", "duration": 5, "function": "cta"},
            ],
            "video_model": "wan2.7",
            "video_count": 1,
            "ugc_styles": ["holding", "review", "usage", "talking"],
            "voice_tone": "friendly, authentic, enthusiastic",
            "target_audience": "Thai TikTok users",
            "image_generation": {},
            "video_generation": {},
            "tts": {"enabled": True},
        }
        logger.info(f"  Recipe (default fallback): {recipe_name}, {len(default_recipe['scenes'])} scenes, {default_recipe['total_duration']}s")
        return default_recipe

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

    # ── Beat-timed script จาก service (single source of truth) ──────────
    # timing_validation/scripts.full_script ถูก build จาก router_config.scenes
    # (4-beat: hook→agitate→solve→cta) แล้ว → ใช้เลยให้ sync กับ 4-beat video prompt
    # ไม่งั้น Gemini gen ใหม่จะหลุด beat ไม่ตรงกับ cut ของวิดีโอ
    beat_timed = product_profile.get("_beat_timed_script", "")
    if beat_timed:
        logger.info(f"  Script: beat-timed จาก prompt-builder-service (sync 4-beat): {beat_timed[:80]}...")
        return beat_timed

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
        logger.info(f"  Script: {script[:100]}... (uses_llm={result.get('uses_llm')})")
        return script

    except Exception as e:
        # NO hardcoded Thai narration fallback. If script generation fails we
        # fail loudly so it's fixable — a hardcoded script would bypass the
        # JSON-driven content and could desync from the TTS/voiceover.
        logger.error(f"Script generation failed (refusing hardcoded fallback): {e}")
        raise RuntimeError(f"script generation failed (no fallback): {e}") from e


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

    # NO hardcoded fallback — image prompt must come from prompt-builder (JSON).
    # Breaking loudly beats silently generating with a generic hardcoded prompt.
    raise ValueError(
        "build_image_prompt: '_image_prompt' missing from product_profile — "
        "prompt-builder (JSON-driven) must supply it; refusing hardcoded fallback"
    )


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

def _clean_product_name_for_video(product_name: str) -> str:
    """Return generic 'product' for video prompts.
    
    Wan 2.7 may interpret product names as instructions.
    The reference image already shows the actual product.
    """
    return "product"


# STEP 7: TTS (Gemini only — NO Edge TTS)
# ═══════════════════════════════════════════════════════════════════════════
# 2026-08-15: Edge TTS ถูกถอดออกจาก TUS แล้ว — ใช้ Gemini TTS อย่างเดียว
# (เสียง Thai คุณภาพสูง + ไม่มี dependency กับ Microsoft endpoint)

def generate_voice(
    text: str,
    voice: str = "Aoede",
    run_id: str = "",
) -> str:
    """Step 7: Generate Thai voice via Gemini TTS only. NO Edge TTS."""
    logger.info(f"Step 7/9: TTS (Gemini — No Edge TTS)")
    logger.info(f"  Text: {text[:50]}...")

    output_path = str(TMP_DIR / f"voice_{run_id}.mp3")

    try:
        from video.gemini_tts import gemini_text_to_speech
        tts_path = gemini_text_to_speech(text, output_path=output_path, voice=voice)
        if tts_path and Path(tts_path).exists():
            logger.info(f"  Gemini TTS OK: {tts_path}")
            return tts_path
        logger.error(f"  Gemini TTS returned empty path: {tts_path}")
    except Exception as e:
        logger.error(f"  Gemini TTS failed: {e}")

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
    reference_image: Optional[str] = None,
    first_frame: Optional[str] = None,
    last_frame: Optional[str] = None,
    thai_script: Optional[str] = None,
    use_tus_voice: bool = False,
) -> tuple:
    """
    Step 8: Generate video via Wan 2.7 Async API (shared ProdiaV2Client)
    """
    logger.info(f"Step 8/9: Generate video (Wan 2.7, {resolution})")
    logger.info(f"  Prompt: {prompt[:80]}...")

    # First frame หลัก: ใช้ first_frame (ถ้าระบุ) แทน image_path
    main_img = first_frame or image_path
    if not main_img:
        raise RuntimeError("generate_video: ต้องมี image_path หรือ first_frame")
    if first_frame:
        logger.info(f"  ▶ first_frame: {first_frame}")

    # Helper อ่าน bytes จาก path หรือ URL
    def _read_bytes(src: Optional[str]) -> Optional[bytes]:
        if not src:
            return None
        try:
            if src.startswith("http://") or src.startswith("https://"):
                r = requests.get(src, timeout=30)
                r.raise_for_status()
                return r.content
            with open(src, "rb") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"  อ่านภาพผิดพลาด ({src}): {e}")
            return None

    # Read first frame bytes
    image_data = _read_bytes(main_img)
    if not image_data:
        raise RuntimeError(f"generate_video: อ่าน first frame ไม่ได้: {main_img}")

    # last_frame + reference_image bytes (Wan 2.7 start-end interpolation + reference)
    last_bytes = _read_bytes(last_frame) if last_frame else None
    ref_bytes = _read_bytes(reference_image) if reference_image else None
    if last_bytes:
        logger.info(f"  ▶ last_frame: {len(last_bytes)} bytes — start-end interpolation")
    if ref_bytes:
        logger.info(f"  ▶ reference_image: {len(ref_bytes)} bytes")

    # Docs-exact lip-sync (VALIDATED 2026-08-15, job abf8a2b2):
    # ส่ง TTS audio ให้ Wan เสมอเมื่อมีไฟล์เสียง (16k mono wav) — ขับปาก + ฝัง soundtrack
    # เสียงจริงที่ user ได้ยิน = TTS+BGM ทับที่ compose Step 9b/9c (แทนที่ audio track)
    audio_bytes = None
    if audio_path:
        ap = Path(audio_path)
        if ap.exists():
            with open(ap, "rb") as af:
                audio_bytes = af.read()
            logger.info(f"  🎤 Lip-Sync (TTS): {len(audio_bytes)} bytes — ส่ง audio ให้ Wan (docs-exact)")
        else:
            logger.warning(f"  ⚠️ audio_path ไม่พบ: {audio_path} — ข้าม lip-sync")

    # ── Thai script: ห้ามฝังลง prompt (docs-exact — script ใน prompt = ปากพูดคนละแบบ)
    # script ไปอยู่ที่ TTS อย่างเดียว (Step 7) แล้วทับที่ compose Step 9b
    final_prompt = prompt

    # ── Generate via shared client ──
    client = ProdiaV2Client(token=PRODIA_TOKEN())

    try:
        # negative_prompt must come from the JSON-driven prompt-builder.
        # No hardcoded fallback: if missing we raise clearly (single source of truth).
        if not negative_prompt:
            raise ValueError("generate_video: negative_prompt is required — supply it from prompt-builder (JSON-driven); refusing hardcoded fallback")
        neg_p = negative_prompt
        result = client.generate_video(
            prompt=final_prompt,
            input_image=image_data,
            duration=duration,
            resolution=resolution,
            audio_bytes=audio_bytes,
            job_type="inference.wan2-7.img2vid.v1",
            negative_prompt=neg_p,
            last_frame=last_bytes,
            reference=ref_bytes,
            # Control motion: disable Wan 2.7's prompt_extend so the model
            # follows our exact prompt (which now includes the end scene)
            # instead of rewriting/expanding it into unpredictable motion.
            prompt_extend=False,
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
        # Docs-exact: audio ส่งให้ Wan แล้ว → วิดีโอควรมี audio track (TTS ที่ส่งไป)
        # ยังไง compose Step 9b ก็จะแทนที่ด้วย TTS+BGM อยู่ดี (กันเสียงสองชั้น)
        if not has_audio_track(str(result_path)):
            logger.info("  Wan video has no audio track (compose Step 9b จะใส่ TTS+BGM ให้)")

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
    
    # Save raw concatenated video (no audio) for user download
    raw_path = STORAGE_DIR / f"affiliate_{run_id}_raw.mp4"
    shutil.copy2(concat_path, raw_path)
    logger.info(f"  9a: Raw video saved -> {raw_path}")

    # Step 9a.5: If video is shorter than target_duration, loop it to fill full duration
    if target_duration > 0:
        # Get actual duration of concat video
        try:
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(concat_path)
            ]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=False)
            actual_duration = float(probe_result.stdout.strip()) if probe_result.stdout.strip() else 0
        except Exception:
            actual_duration = 0

        if actual_duration > 0 and actual_duration < target_duration - 1:
            logger.info(f"  9a.5: Video is {actual_duration:.1f}s, looping to {target_duration}s")
            looped_path = TMP_DIR / f"looped_{run_id}.mp4"
            # Calculate how many loops needed, with slight overlap for smoothness
            loop_count = int(target_duration / actual_duration) + 1
            try:
                cmd_loop = [
                    "ffmpeg", "-y",
                    "-stream_loop", str(loop_count),
                    "-i", str(concat_path),
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-t", str(target_duration),
                    "-pix_fmt", "yuv420p",
                    str(looped_path)
                ]
                subprocess.run(cmd_loop, check=True, capture_output=True, timeout=120)
                if looped_path.exists() and looped_path.stat().st_size > 1000:
                    shutil.copy2(looped_path, concat_path)
                    logger.info(f"  9a.5: Looped video saved -> {concat_path}")
            except Exception as e:
                logger.warning(f"  9a.5: Loop failed ({e}), using original concat")

    # Step 9b: Force-merge Gemini TTS voiceover audio into the video
    final_path = concat_path
    if voice_path and Path(voice_path).exists():
        logger.info(f"  9b: Merging TTS voiceover audio {voice_path} into final video")
        voiced_path = STORAGE_DIR / f"affiliate_{run_id}_voiced.mp4"
        # FIX (dead voice_speed): apply the voice_speed via ffmpeg atempo filter.
        # voice_speed was declared (default 1.3) but never used — no speed filter
        # existed, so the "speak faster" param did nothing. atempo supports 0.5-2.0.
        cmd_voice = [
            "ffmpeg", "-y",
            "-i", str(concat_path),
            "-i", str(voice_path),
            "-filter:a", f"atempo={voice_speed}",
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-t", str(target_duration),
            str(voiced_path)
        ]
        try:
            subprocess.run(cmd_voice, check=True, capture_output=True, timeout=60)
            if voiced_path.exists() and voiced_path.stat().st_size > 1000:
                final_path = voiced_path
                logger.info(f"  9b: Voiceover merged successfully (atempo={voice_speed}) -> {final_path}")
        except Exception as ve:
            logger.error(f"  9b: Merging voiceover failed ({ve}), using concat video")
    else:
        final_path = concat_path


    # Step 9c: Add BGM
    if bgm_style:
        logger.info(f"  9c: Add BGM ({bgm_style})")
        bgm_filename = f"{bgm_style}.mp3" if not bgm_style.endswith((".mp3", ".wav")) else bgm_style
        bgm_path = STORAGE_DIR / "sounds" / bgm_filename

        if bgm_path.exists():
            bgm_output = STORAGE_DIR / f"affiliate_{run_id}_bgm.mp4"
            # Strategy: mix BGM with video audio. If video has no usable audio, just copy BGM
            try:
                cmd_mix = [
                    "ffmpeg", "-y",
                    "-i", str(final_path),
                    "-stream_loop", "-1",
                    "-i", str(bgm_path),
                    "-filter_complex",
                    "[1:a]volume=0.15[bg];[0:a][bg]amix=inputs=2:duration=first[out]",
                    "-map", "0:v",
                    "-map", "[out]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-t", str(target_duration),
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
                        "-t", str(target_duration),
                        str(bgm_output),
                    ]
                    subprocess.run(cmd_bgm, check=True, capture_output=True, timeout=60)
                    logger.info(f"    BGM-only added")
                    final_path = bgm_output
                except Exception as e2:
                    logger.warning(f"    BGM-only also failed: {e2}")

    logger.info(f"  Final: {final_path}")
    return str(final_path), str(raw_path)


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
    # ── First/Reference/Last frame + Thai script (Wan พูดเอง ไม่ใช้ TTS lip-sync ทับ) ──
    first_frame: Optional[str] = None,
    reference_image: Optional[str] = None,
    last_frame: Optional[str] = None,
    thai_script: Optional[str] = None,
    use_tus_voice: bool = False,
    audio_path: Optional[str] = None,
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
        first_frame: path/URL ของ first frame image (ใช้แทน image ที่ gen สำหรับ Wan)
        reference_image: path/URL ของ reference image (ส่งให้ Wan เป็น reference)
        last_frame: path/URL ของ target last-frame image (Wan 2.7 start-end interpolation)
        thai_script: บทพูดภาษาไทยที่ให้ Wan พูดเองในคลิป (ไม่ใช้ TTS lip-sync ทับ)
        use_tus_voice: DEPRECATED (ทิศทางเก่า "ให้ Wan พูดเอง" ปิดแล้ว 2026-08-15) —
            เก็บไว้รับค่า backward-compat เท่านั้น ไม่มีผลต่อ pipeline แล้ว
            ทิศทางใหม่: ส่ง TTS audio ให้ Wan เสมอ (lip-sync) + TTS/BGM ทับที่ compose

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
            # NO hardcoded generic prompt. This exact fallback is what produced
            # the "speaks Vietnamese/gibberish" raw video (a generic English prompt
            # with no Thai script went to Wan). Prompts MUST come from the
            # JSON-driven prompt-builder — break loudly instead of regressing.
            # (docs-exact 2026-08-15: ห้ามฝัง script ลง prompt — ไปอยู่ TTS อย่างเดียว)
            raise ValueError(
                "pipeline: video_prompts missing and no video_prompt supplied — "
                "refusing hardcoded generic prompt; wire the prompt-builder output"
            )
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

        # ── STEP 8: Generate 1 Video (Wan 2.7 Sync, 1 clip full duration) ──
        # WHY 1 clip: Wan 2.7 img2vid generates from a SINGLE image reference.
        # Multiple independent clips from the same static image = jarring cuts,
        # same product angle every scene, zero visual continuity.
        # 1 continuous generation = smooth motion, natural flow.
        step_start = time.time()
        video_paths = []
        
        vprompt = video_prompts[0] if video_prompts else ""
        if not vprompt:
            # No hardcoded video prompt — raise clearly. Prompts must come from
            # prompt-builder (JSON-driven). Breaking loudly beats a silent generic
            # fallback that diverges from the JSON prompt sources.
            raise ValueError("pipeline: video_prompts is empty/None — no prompt to generate video; refusing hardcoded fallback")
        logger.info(f"  Generating 1 continuous video ({total_duration}s): {vprompt[:80]}...")
        
        vid_path, cost_video = generate_video(
            image_path=str(img_path),
            prompt=vprompt,
            duration=total_duration,
            # docs-exact: ส่ง TTS audio ให้ Wan เสมอ (lip-sync ขับปาก)
            # override: ถ้า client �่ง audio_path มาใช้ของ client (FL2V+Audio path)
            audio_path=_convert_to_wav(audio_path or voice_path) if (audio_path or voice_path) else None,
            negative_prompt=negative_prompt,
            # first+last start-end interpolation per Prodia docs
            # (ห้ามส่ง reference แยก — ทำให้ Prodia เอา reference เป็นภาพหลักแทน interpolation)
            reference_image=None,
            first_frame=first_frame or None,
            last_frame=last_frame or None,
            thai_script=thai_script,
            use_tus_voice=use_tus_voice,
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
        # FIX (duration mismatch bug): use the ACTUAL Prodia Wan output duration,
        # not the recipe total_duration. Previously final_duration was forced to
        # recipe['total_duration']=15 even when the user requested a shorter job
        # (e.g. 4s) — compose_video would then -stream_loop the short clip up to
        # 15s, producing the "clip repeats / ถูกตัดซ้ำ" visual. Probing the real
        # clip avoids that: short jobs stay short, 15s jobs are already 15s.
        actual_video_duration = 0.0
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(vid_path)],
                capture_output=True, text=True, timeout=20,
            )
            if probe.stdout.strip():
                actual_video_duration = float(probe.stdout.strip())
        except Exception:
            actual_video_duration = 0.0
        if actual_video_duration > 0:
            final_duration = actual_video_duration
        else:
            # Fallback: requested duration, then recipe default
            final_duration = total_duration if total_duration > 0 else recipe.get("total_duration", 0)
        # เสียงจริง = TTS voiceover ทับที่ compose (docs-exact: TTS+BGM ที่ FFmpeg)
        compose_voice = voice_path
        final_path, raw_path = compose_video(video_paths, compose_voice, run_id, bgm_style, target_duration=final_duration)

        # Preserve the TRUE Prodia output (before any compose/edit) permanently.
        # raw_path = affiliate_{run_id}_raw.mp4 is a POST-compose concat output.
        # The raw Wan 2.7 Prodia file is vid_path (img2vid_*.mp4) — copy it out of
        # TMP (which gets cleaned) so the UI "ไฟล์ที่สร้าง" can show what Prodia
        # actually generated, letting the user see the un-edited lip-sync source.
        prodia_src = vid_path if vid_path else (video_paths[-1] if video_paths else '')
        prodia_raw_path = ''
        if prodia_src and os.path.exists(prodia_src):
            prodia_raw_path = str(STORAGE_DIR / f"raw_prodia_{run_id}.mp4")
            shutil.copy2(prodia_src, prodia_raw_path)
            logger.info(f"  Prodia raw preserved -> {prodia_raw_path}")

        # Cost summary
        cost_total = cost_image + cost_voice + cost_video
        total_duration_ms = int((time.time() - pipeline_start) * 1000)

        logger.info(f"{'='*60}")
        logger.info(f"Pipeline v6 complete: {final_path}")
        logger.info(f"Cost: ${cost_total:.4f}")
        logger.info(f"Time: {total_duration_ms/1000:.1f}s")
        logger.info(f"{'='*60}")

        # Log completion — raw_video_path now points at the true Prodia output
        # (raw_prodia_{run_id}.mp4). The compose-concat output (raw_path) stays
        # on disk for reference but is no longer exposed as "Raw Video".
        try:
            complete_job(
                job_id,
                final_path=str(final_path),
                total_duration_ms=total_duration_ms,
                total_video_duration=total_duration,
                total_scenes=num_scenes,
                raw_video_path=prodia_raw_path or str(raw_path)
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