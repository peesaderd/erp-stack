"""
TikTok UGC Studio — Affiliate Video Pipeline v5 (Module-based)
=================================================================
Pipeline: Nano Banana Img2Img → Gemini TTS → Wan 2.7 img2vid → FFmpeg Voice Merge + BGM

Flow:
  1. Image — Nano Banana Img2Img ($0.005) สร้างรูปอ้างอิงจากสินค้า
  2. Voice — Gemini TTS สร้างเสียงพากย์
  3. Video — Wan 2.7 img2vid ($0.03) สร้างคลิป silent
  4. Voice Merge — FFmpeg ใส่เสียงพากย์ + BGM
  5. Concat — FFmpeg ต่อหลาย scene (ถ้ามี)

ข้อดี:
  - Nano Banana: img2img คุณภาพสูง เก่งคนไทย
  - Gemini TTS: เสียงธรรมชาติ รองรับภาษาไทย
  - Wan 2.7: สร้าง video จากภาพ + prompt
  - FFmpeg merge เสียงแยก — mix level ควบคุมได้

ต้นทุนต่อคลิป:
  - 8 วิ (Nano Banana + Gemini TTS + Wan 2.7):   ~$0.038
  - 16 วิ (2 scenes + concat):                    ~$0.068

Bug fix v5:
  - ส่ง input_image ไปยัง Nano Banana ถูกต้อง (fix สินค้าไม่ตรง)
  - ใช้ shared_config.py สำหรับ API keys
  - ใช้ Gemini TTS จาก gemini_tts.py
"""

import os
import sys
import json
import time
import uuid
import logging
import subprocess
from pathlib import Path
from typing import Optional

import requests

# Add erp-stack to path for shared_config
_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from shared_config import PRODIA_TOKEN, GEMINI_API_KEY

logger = logging.getLogger("tiktok-ugc.pipeline_affiliate")

# ─── Config ────────────────────────────────────────────────────────────────

STORAGE_DIR = Path(__file__).parent / "storage"
TMP_DIR = STORAGE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

PRODIA_BASE = "https://inference.prodia.com/v2"
PRODIA_IMG2IMG_TYPE = "inference.nano-banana.img2img.v1"
PRODIA_IMG2VID_TYPE = "inference.wan2-7.img2vid.v1"

# Image Gen Service URL (localhost:8110)
IMAGE_GEN_URL = "http://localhost:8110/api/image/v1/generate"


# ─── Helpers ───────────────────────────────────────────────────────────────

def _prodia_headers():
    return {"Authorization": f"Bearer {PRODIA_TOKEN()}"}


def download_file(url: str, output_path: Path) -> Path:
    """Download from URL to local path."""
    if os.path.exists(url):
        import shutil
        shutil.copy2(url, output_path)
        return output_path
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path


def concat_videos(video_paths: list[Path], output_path: Path) -> Path:
    """Concat multiple videos with FFmpeg."""
    list_file = TMP_DIR / f"concat_{uuid.uuid4().hex}.txt"
    with open(list_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp.absolute()}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(list_file), "-c", "copy", str(output_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink(missing_ok=True)
    return output_path


# ─── Step 1: Image (Nano Banana Img2Img via Image-Gen Service) ─────────────

def generate_image(
    prompt: str,
    aspect_ratio: str = "9:16",
    input_image: str = None,
    product_image: str = None,
) -> str:
    """Generate image via image-gen service (Nano Banana on localhost:8110).
    
    ใช้ Nano Banana Img2Img เพื่อสร้างรูป UGC จากสินค้า
    
    aspect_ratio: 9:16 (TikTok portrait), 1:1 (square), 16:9 (landscape)
    input_image: URL ของรูปสินค้าสำหรับ img2img (สำคัญมาก!)
    product_image: fallback ถ้าไม่มี input_image
    
    Returns:
        URL ของรูปที่สร้าง
    """
    # ใช้ product_image เป็น fallback
    ref_image = input_image or product_image
    
    logger.info(f"Nano Banana Img2Img: {prompt[:40]}...")
    if ref_image:
        logger.info(f"  Reference image: {ref_image[:60]}...")
    else:
        logger.warning("  No reference image! Will generate generic product image")
    
    payload = {
        "prompt": prompt,
        "count": 1,
        "upscale": False,
        "aspectRatio": aspect_ratio,
    }
    
    # ส่ง input_image สำหรับ Nano Banana Img2Img
    if ref_image:
        payload["inputImage"] = ref_image
        payload["modelTier"] = "nano.banana"  # ใช้ Nano Banana
        payload["provider"] = "prodia"
        payload["thaiModel"] = True
    
    try:
        resp = requests.post(IMAGE_GEN_URL, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        
        if not (data.get("success") or data.get("ok")) or not data.get("images"):
            raise RuntimeError(f"Image-gen service failed: {data}")
        
        img_info = data["images"][0]
        url = img_info.get("full_url") or img_info.get("url")
        if not url:
            raise RuntimeError(f"Image-gen service returned no URL: {data}")
        
        logger.info(f"  Image OK: {url[:60]}...")
        return url
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Image-gen service error: {e}")
        raise


# ─── Step 2: Voice (Gemini TTS) ────────────────────────────────────────────

def generate_voice(
    text: str,
    voice: str = "Aoede",
    run_id: str = "",
) -> str:
    """Generate Thai voice via Gemini 3.1 Flash TTS Preview.
    
    Args:
        text: ข้อความสำหรับ TTS (ภาษาไทย)
        voice: ชื่อเสียง (Aoede, Wise_Woman, etc.)
        run_id: สำหรับสร้าง filename
    
    Returns:
        Path ของไฟล์เสียงที่สร้าง
    """
    logger.info(f"  TTS (Gemini): chars={len(text)}, voice={voice}")
    
    try:
        # Import จาก gemini_tts.py ใน modules/video
        from video.gemini_tts import gemini_text_to_speech
        
        output_path = str(TMP_DIR / f"voice_{run_id}.mp3")
        tts_path = gemini_text_to_speech(text, output_path=output_path, voice=voice)
        
        if tts_path and Path(tts_path).exists():
            logger.info(f"  TTS OK: {tts_path}")
            return tts_path
        else:
            raise RuntimeError(f"Gemini TTS returned invalid path: {tts_path}")
            
    except ImportError as e:
        logger.error(f"Cannot import gemini_tts: {e}")
        raise
    except Exception as e:
        logger.error(f"Gemini TTS failed: {e}")
        raise


# ─── Step 3: Video (Wan 2.7 img2vid) ───────────────────────────────────────

def generate_video(
    image_path: str,
    prompt: str,
    duration: int = 8,
) -> str:
    """
    Wan 2.7 img2vid — สร้าง video จากภาพ
    
    Args:
        image_path: Path หรือ URL ของรูป
        prompt: คำบรรยาย scene
        duration: ความยาวคลิป (2-15s)
    
    Returns:
        Path ของไฟล์ video ที่สร้าง (silent)
    
    Cost: $0.03/gen
    """
    logger.info(f"Wan 2.7 img2vid ({duration}s): {prompt[:40]}...")

    # Read image bytes (support URL or local path)
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
            "negative_prompt": "low resolution, error, worst quality, deformed, blurry, disfigured face, wrong mouth, speaking, lips moving",
        }
    }

    files = [
        ("job", ("job.json", json.dumps(config_payload), "application/json")),
        ("input", ("image.png", image_data, "image/png")),
    ]

    resp = requests.post(
        f"{PRODIA_BASE}/job",
        headers=_prodia_headers(),
        files=files,
        timeout=300
    )
    resp.raise_for_status()

    ct = resp.headers.get("content-type", "")

    # Prodia v2 sync — could be binary video (MP4) or JSON
    if "json" in ct:
        data = resp.json()
        state = data.get("state", {}).get("current", "")
        if state == "failed":
            raise RuntimeError(f"Prodia Wan 2.7 failed: {data.get('error')}")

        # Extract output URL from JSON response
        url = ""
        url_info = data.get("config", {}).get("url_info", [])
        if url_info and len(url_info) > 0:
            url = url_info[0].get("url", "")
        if not url:
            output = data.get("output", {})
            url = output.get("url", "") or output.get("video", {}).get("url", "")

        if not url:
            raise RuntimeError(f"Prodia Wan 2.7: no URL in response: {data}")

        # Download video from URL
        vid_resp = requests.get(url, timeout=60)
        vid_resp.raise_for_status()
        result_path = TMP_DIR / f"img2vid_{uuid.uuid4().hex[:8]}.mp4"
        with open(result_path, "wb") as f:
            f.write(vid_resp.content)
        logger.info(f"  Video OK (downloaded from URL)")
        return str(result_path)
    else:
        # Binary video response (MP4)
        result_path = TMP_DIR / f"img2vid_{uuid.uuid4().hex[:8]}.mp4"
        with open(result_path, "wb") as f:
            f.write(resp.content)
        logger.info(f"  Video OK (binary MP4, {len(resp.content)} bytes)")
        return str(result_path)


# ─── Full Pipeline v5 ──────────────────────────────────────────────────────

def run_pipeline(
    script: str,
    scene_prompts: list[str],
    voice: str = "Aoede",
    video_duration: int = 8,
    image_prompt: Optional[str] = None,
    product_image: Optional[str] = None,
    bgm_style: str = "chill_loft",
    video_prompts: list[str] = None,
) -> dict:
    """
    Run full Affiliate Pipeline v5 — Nano Banana → Gemini TTS → Wan 2.7 → FFmpeg

    Args:
        script: Voice over text (Thai)
        scene_prompts: List of scene prompts
        voice: Gemini TTS voice name
        video_duration: Seconds per scene
        image_prompt: คำบรรยายสำหรับสร้างรูป (ถ้าไม่มีจะใช้ scene_prompts[0])
        product_image: URL หรือ path ของรูปสินค้า (สำคัญมากสำหรับ Nano Banana!)
        bgm_style: สไตล์เพลงพื้นหลัง
        video_prompts: คำบรรยายสำหรับ video (ถ้าต่างจาก scene_prompts)

    Returns:
        dict { final_path, cost_estimate, ... }
    """
    run_id = uuid.uuid4().hex[:8]
    num_scenes = len(scene_prompts)

    logger.info(f"=== Pipeline v5 run {run_id} ===")
    logger.info(f"Script: {script[:50]}...")
    logger.info(f"Scenes: {num_scenes} x {video_duration}s")
    logger.info(f"Product image: {product_image or 'None (will generate generic)'}")

    cost_image = 0.0
    cost_voice = 0.0
    cost_video = 0.0

    # ── Step 1: Image (Nano Banana Img2Img) ──
    logger.info("Step 1/4: Nano Banana Image")
    
    if not product_image:
        logger.warning("No product_image! Image might not match actual product")
    
    # ใช้ scene_prompts[0] หรือ image_prompt เป็น base prompt
    base_prompt = image_prompt or scene_prompts[0] if scene_prompts else "product showcase, clean background"
    
    img_url = generate_image(
        prompt=base_prompt,
        input_image=product_image,
        product_image=product_image,
    )
    img_path = TMP_DIR / f"image_{run_id}.png"
    download_file(img_url, img_path)
    ref_image_for_video = str(img_path)
    cost_image = 0.005  # Nano Banana cost

    # ── Step 2: Voice (Gemini TTS) ──
    logger.info(f"Step 2/4: Voice [voice: {voice}]")
    voice_path = generate_voice(script, voice=voice, run_id=run_id)
    voice_char_count = len(script)
    cost_voice = (voice_char_count / 1000) * 0.0001  # Gemini TTS cost estimate

    # ── Step 3: Video — Wan 2.7 img2vid ──
    logger.info("Step 3/4: Video (img2vid)")
    video_paths = []
    vid_prompts = video_prompts if video_prompts else scene_prompts
    
    for i in range(num_scenes):
        vprompt = vid_prompts[i] if i < len(vid_prompts) else scene_prompts[i]
        logger.info(f"  Scene {i+1}/{num_scenes}: {vprompt[:60]}...")
        
        vid_path = generate_video(
            image_path=ref_image_for_video,
            prompt=vprompt,
            duration=video_duration,
        )
        video_paths.append(Path(vid_path))

    cost_video = num_scenes * 0.03

    # ── Voice Merge: FFmpeg เอา voice audio ใส่ video ──
    logger.info("Voice Merge: mixing voice audio into video")
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
            logger.info(f"  Scene {i}: voice merged")
        except Exception as e:
            logger.warning(f"  Voice merge failed for scene {i}: {e}, using original")
            merged_paths.append(vpath)
    video_paths = merged_paths

    # ── Step 4: Concat scenes (ถ้ามีหลาย scene) ──
    if num_scenes > 1:
        logger.info("Step 4/4: Concat")
        final_path = STORAGE_DIR / f"affiliate_{run_id}.mp4"
        concat_videos(video_paths, final_path)
    else:
        final_path = STORAGE_DIR / f"affiliate_{run_id}.mp4"
        import shutil
        shutil.copy2(video_paths[0], final_path)

    # ── Step 5: BGM (add background music) ──
    if bgm_style:
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
                logger.info(f"  BGM ({bgm_filename}) added")
                final_path = bgm_output
            except Exception as bgm_err:
                logger.warning(f"  BGM failed: {bgm_err}")

    # Cost summary
    cost_total = cost_image + cost_voice + cost_video
    cost_breakdown = {
        "image": round(cost_image, 4),
        "voice": round(cost_voice, 4),
        "video": round(cost_video, 4),
        "total": round(cost_total, 4),
    }

    logger.info(f"=== Pipeline complete: {final_path} ===")
    logger.info(f"Cost: ${cost_total}")
    for k, v in cost_breakdown.items():
        logger.info(f"  {k}: ${v}")

    return {
        "run_id": run_id,
        "final_path": str(final_path),
        "duration": num_scenes * video_duration,
        "cost_estimate": cost_total,
        "cost_breakdown": cost_breakdown,
        "files": {"final": str(final_path)},
    }


# ─── CLI ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Affiliate Video Pipeline v5")
    parser.add_argument("--script", required=True, help="Voice over text (Thai)")
    parser.add_argument("--prompts", nargs="+", required=True, help="Scene prompts")
    parser.add_argument("--voice", default="Aoede", help="Gemini TTS voice")
    parser.add_argument("--duration", type=int, default=8, help="Seconds per scene")
    parser.add_argument("--image", default="", help="Image prompt (optional)")
    parser.add_argument("--product-image", required=True, help="Product image URL/path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    result = run_pipeline(
        script=args.script,
        scene_prompts=args.prompts,
        voice=args.voice,
        video_duration=args.duration,
        image_prompt=args.image or None,
        product_image=args.product_image,
    )

    print("\n✅ Done!")
    print(f"  Final: {result['final_path']}")
    print(f"  Cost:  ${result['cost_estimate']}")
    print(f"  Breakdown: {result['cost_breakdown']}")
