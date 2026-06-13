"""
TikTok UGC Studio — Affiliate Video Pipeline v4 (Prodia Only)
===============================================================
Pipeline: SAM3 Analyze → FLUX Image → MiniMax TTS → Wan 2.7 img2vid+audio (Lip Sync in video!) → FFmpeg Concat

Flow:
  1. SAM3 Analyze — วิเคราะห์ภาพสินค้า (object, safe zones, prompt insights)
  2. Image — FLUX schnell ($0.001) สร้างรูปจาก prompt
  3. Voice — MiniMax Speech ($0.003) สร้างเสียงพากย์
  4. Video — Wan 2.7 img2vid+audio ($0.03) สร้างคลิป Lip Sync ในตัว!
  5. Concat — FFmpeg ต่อหลาย scene (ถ้ามี)
  6. BGM — เลือกใส่เพิ่มได้

ข้อดี:
  - ไม่ต้อง VEED/Wav2Lip ($0.054 ประหยัด!)
  - ไม่ต้อง FFmpeg merge voice (audio อยู่ใน video แล้ว)
  - Lip Sync native — ไม่มี overlay artifact
  - SAM3 ช่วย improve prompt + layout

ต้นทุนต่อคลิป:
  - 8 วิ (SAM3 + FLUX + TTS + Wan 2.7):  ~$0.034
  - 16 วิ (2 scenes + concat):            ~$0.064
"""

import os
import json
import time
import uuid
import logging
import subprocess
from pathlib import Path
from typing import Optional

import requests

# SAM3 client (optional)
from sam3_client import segment_image, mask_to_rgba, track_object_in_video

logger = logging.getLogger("tiktok-ugc.pipeline_affiliate")

# ─── Config ────────────────────────────────────────────────────────────────

FAL_KEY = os.environ.get("FAL_API_KEY", "") or os.environ.get("FAL_KEY", "")
PRODIA_TOKEN = os.environ.get("PRODIA_TOKEN", "") or os.environ.get("PRODIA_KEY", "")

STORAGE_DIR = Path(__file__).parent / "storage"
TMP_DIR = STORAGE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

PRODIA_BASE = "https://inference.prodia.com/v2"
PRODIA_IMAGE_TYPE = "inference.flux-fast.schnell.txt2img.v2"
PRODIA_IMG2VID_TYPE = "inference.wan2-7.img2vid.v1"

# Voice timing defaults (built-in audio, no separate merge needed)
VOICE_START_SEC = 1.5
VOICE_DURATION_SEC = 5.0


# ─── Helpers ───────────────────────────────────────────────────────────────

def _prodia_headers():
    return {"Authorization": f"Bearer {PRODIA_TOKEN}"}


def _poll_job(job_url: str, max_polls: int = 120, sleep_s: int = 2) -> dict:
    """Poll Prodia job until complete."""
    headers = _prodia_headers()
    for _ in range(max_polls):
        time.sleep(sleep_s)
        resp = requests.get(job_url, headers=headers, timeout=15)
        # Binary response (multipart/video)
        ct = resp.headers.get("content-type", "")
        if "multipart" in ct or "video" in ct:
            return {"_raw_video": True, "_response": resp}
        try:
            data = resp.json()
        except:
            return {"_raw_video": True, "_response": resp}
        status = data.get("status", "")
        if status == "completed":
            return data
        elif status in ("failed", "error"):
            raise RuntimeError(f"Prodia failed: {data}")
    raise TimeoutError("Prodia job timed out")


def _extract_url(result: dict, key: str = "url") -> str:
    """Extract URL from Prodia response (handles multiple response shapes)."""
    raw = result.get("_raw_video")
    if raw:
        # Binary response — save to temp and return
        resp = result["_response"]
        tmp_path = TMP_DIR / f"raw_{uuid.uuid4().hex[:8]}.mp4"
        with open(tmp_path, "wb") as f:
            f.write(resp.content)
        return str(tmp_path)

    output = result.get("output", {}) or result.get("result", {})
    if isinstance(output, dict):
        url = output.get(key, "") or output.get("video", {}).get("url", "")
    else:
        url = str(output) if output else ""
    if not url:
        url = result.get("video", {}).get("url", "") or result.get("output_url", "")
    if not url:
        raise RuntimeError(f"No URL in Prodia response: {result}")
    return url


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


# ─── Step 0: SAM3 Analyze — วิเคราะห์ภาพสินค้าก่อนสร้างอะไรทั้งสิ้น ────────

def sam3_analyze_image(image_path: str, run_id: str = "") -> dict:
    """
    SAM3 Analyze — Scan รูปสินค้าเพื่อ:
    1. หาตำแหน่ง object หลัก (product, person, bag, text)
    2. หาพื้นที่ว่างสำหรับวาง artwork (CTA, Logo, Price)
    3. สร้าง prompt insights ปรับปรุง FLUX / Wan 2.7 prompt

    Returns:
        dict {
            "objects": [...],
            "safe_zones": [...],
            "layout": {"cta": [x,y], "logo": [x,y], "price": [x,y]},
            "prompt_insights": "str",
        }

    Cost: ~$0.0011/call
    """
    from PIL import Image as PILImage
    import io

    logger.info(f"[SAM3] Analyzing: {image_path}")
    objects = []
    masks = {}
    img = PILImage.open(image_path)
    w, h = img.size

    for label in ["product", "person", "bag", "box", "bottle", "text", "logo"]:
        try:
            result_masks = segment_image(image_path, prompt=label, confidence=0.4)
            if result_masks:
                best_mask = None
                best_area = 0
                for m in result_masks:
                    mask_img = PILImage.open(io.BytesIO(m)).convert("L")
                    bbox = mask_img.getbbox()
                    if bbox:
                        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                        if area > best_area:
                            best_area = area
                            best_mask = m
                if best_mask and best_area > (w * h * 0.01):
                    mask_img = PILImage.open(io.BytesIO(best_mask)).convert("L")
                    bbox = mask_img.getbbox()
                    objects.append({
                        "label": label,
                        "bbox": list(bbox),
                        "center": [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2],
                        "area_pct": round(best_area / (w * h) * 100, 1),
                    })
                    masks[label] = best_mask
        except Exception as e:
            logger.debug(f"[SAM3] {label} not found: {e}")

    # Safe zones (4x4 grid)
    occupied = [[False] * 4 for _ in range(4)]
    for obj in objects:
        cx, cy = obj["center"]
        gx, gy = min(3, int(cx / w * 4)), min(3, int(cy / h * 4))
        occupied[gy][gx] = True
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                nx, ny = gx + dx, gy + dy
                if 0 <= nx < 4 and 0 <= ny < 4:
                    occupied[ny][nx] = True

    safe_cells = []
    for row in range(4):
        for col in range(4):
            if not occupied[row][col]:
                cx = (col + 0.5) * (w / 4)
                cy = (row + 0.5) * (h / 4)
                weight = 1.0 - (abs(row - 1.5) + abs(col - 1.5)) / 6
                safe_cells.append({
                    "center": [int(cx), int(cy)],
                    "weight": round(weight, 2),
                })

    layout = {}
    if safe_cells:
        cta_cell = max(safe_cells, key=lambda c: c["weight"] * (c["center"][0] / w) * (c["center"][1] / h))
        layout["cta"] = cta_cell["center"]
        logo_cell = min(safe_cells, key=lambda c: c["center"][1])
        layout["logo"] = logo_cell["center"]
        for obj in objects:
            if obj["label"] == "product":
                layout["price"] = [obj["center"][0], obj["bbox"][3] + 20]
                break
        else:
            layout["price"] = safe_cells[0]["center"]

    # Prompt insights
    prompt_insights = ""
    for obj in objects:
        if obj["label"] in ("person", "product"):
            prompt_insights += f"{obj['label']} at center, "
    prompt_insights += "clean composition, space for text overlay"

    logger.info(f"[SAM3] {len(objects)} objects, {len(safe_cells)} safe zones")
    return {
        "objects": objects,
        "safe_zones": safe_cells,
        "layout": layout,
        "prompt_insights": prompt_insights,
        "image_width": w,
        "image_height": h,
    }


# ─── Step 1: Image (FLUX schnell @ Prodia $0.001) ─────────────────────────

def generate_image(prompt: str, reference_analysis: dict = None) -> str:
    """Generate image via FLUX schnell, optionally enhanced with SAM3 insights."""
    enhanced = prompt
    if reference_analysis and reference_analysis.get("prompt_insights"):
        enhanced = prompt + ", " + reference_analysis["prompt_insights"]

    logger.info(f"FLUX Image: {enhanced[:40]}...")
    payload = {"type": PRODIA_IMAGE_TYPE, "config": {"prompt": enhanced, "steps": 4}}

    resp = requests.post(f"{PRODIA_BASE}/job", headers=_prodia_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    job_id = data.get("job", {}).get("id", "") or data.get("id", "")
    if not job_id:
        raise RuntimeError(f"Prodia image submit failed: {data}")
    result = _poll_job(f"{PRODIA_BASE}/job/{job_id}", max_polls=30, sleep_s=2)
    url = _extract_url(result, "url")
    logger.info(f"  Image OK")
    return url


# ─── Step 2: Voice (MiniMax Speech @ Fal.ai ~$0.003) ─────────────────────

def generate_voice(text: str, voice_id: str = "English_Trustworth_Man",
                   speed: float = 1.0) -> str:
    """Generate Thai voice via MiniMax Speech-02 Turbo."""
    url = "https://fal.run/fal-ai/minimax/speech-02-turbo"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "text": text,
        "voice_setting": {"voice_id": voice_id, "speed": speed, "vol": 1.0, "pitch": 0},
        "language_boost": "Thai",
        "output_format": "url"
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    audio_url = data.get("audio", {}).get("url", "")
    if not audio_url:
        raise RuntimeError(f"MiniMax Speech failed: {data}")
    return audio_url


# ─── Step 3: Video (Wan 2.7 img2vid+audio = Lip Sync in one!) $0.03 ─────

def generate_video_with_image_and_audio(
    image_path: str,
    audio_path: str,
    prompt: str,
    duration: int = 8,
    reference_analysis: dict = None,
) -> str:
    """
    Wan 2.7 img2vid + Audio — Lip Sync ในคลิปเดียว!

    ส่งรูปสินค้า + เสียงพากย์ → Wan 2.7 สร้างคลิปปากขยับตามเสียง.

    Args:
        image_path: Path to image (product/FLUX gen)
        audio_path: Path to audio (MiniMax MP3)
        prompt: Scene description
        duration: Clip duration (2-15s)
        reference_analysis: SAM3 analysis result (optional)

    Returns:
        URL or local path of generated video with built-in lip sync

    Cost: $0.03/gen (เท่า T2V!)
    """
    enhanced = prompt
    if reference_analysis and reference_analysis.get("prompt_insights"):
        enhanced = prompt + ", " + reference_analysis["prompt_insights"]

    logger.info(f"Wan 2.7 img2vid+audio ({duration}s): {enhanced[:40]}...")

    # Read file bytes
    with open(image_path, "rb") as f:
        image_data = f.read()
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    config_payload = {
        "type": PRODIA_IMG2VID_TYPE,
        "config": {
            "prompt": enhanced,
            "duration": duration,
            "negative_prompt": "low resolution, error, worst quality, deformed, blurry",
        }
    }

    files = {
        "image": ("image.png", image_data, "image/png"),
        "audio": ("audio.mp3", audio_data, "audio/mpeg"),
        "config": (None, json.dumps(config_payload), "application/json"),
    }

    resp = requests.post(f"{PRODIA_BASE}/job", headers=_prodia_headers(), files=files, timeout=60)
    resp.raise_for_status()

    # Check response — could be binary (MP4) or JSON (job ID for polling)
    ct = resp.headers.get("content-type", "")
    if "multipart" in ct or "video" in ct or "octet" in ct:
        result_path = TMP_DIR / f"img2vid_{uuid.uuid4().hex[:8]}.mp4"
        with open(result_path, "wb") as f:
            f.write(resp.content)
        logger.info(f"  Video (binary) -> {result_path}")
        return str(result_path)

    try:
        data = resp.json()
        job_id = data.get("job", {}).get("id", "") or data.get("id", "")
    except:
        # Binary fallback
        result_path = TMP_DIR / f"img2vid_{uuid.uuid4().hex[:8]}.mp4"
        with open(result_path, "wb") as f:
            f.write(resp.content)
        return str(result_path)

    if not job_id:
        raise RuntimeError(f"Prodia img2vid submit failed: {data}")

    result = _poll_job(f"{PRODIA_BASE}/job/{job_id}", max_polls=120, sleep_s=5)

    # Check for binary video in poll result
    if "_raw_video" in result:
        resp = result["_response"]
        result_path = TMP_DIR / f"img2vid_{uuid.uuid4().hex[:8]}.mp4"
        with open(result_path, "wb") as f:
            f.write(resp.content)
        return str(result_path)

    url = _extract_url(result, "url")
    logger.info(f"  Video OK (audio-driven lip sync!)")
    return url


# ─── Full Pipeline v4 ─────────────────────────────────────────────────────

def run_pipeline(
    script: str,
    scene_prompts: list[str],
    voice_id: str = "English_Trustworth_Man",
    video_duration: int = 8,
    image_prompt: Optional[str] = None,
    product_image: Optional[str] = None,
    enable_sam3: bool = True,
) -> dict:
    """
    Run full Affiliate Pipeline v4 — SAM3 → Voice → Wan 2.7 img2vid+audio

    Args:
        script: Voice over text (Thai)
        scene_prompts: List of scene prompts
        voice_id: MiniMax voice ID
        video_duration: Seconds per scene
        image_prompt: If set, generate FLUX image as video input
        product_image: If set, use real product image for SAM3 + video
        enable_sam3: Toggle SAM3 analysis

    Returns:
        dict { final_path, cost_estimate, ... }
    """
    run_id = uuid.uuid4().hex[:8]
    num_scenes = len(scene_prompts)

    logger.info(f"=== Pipeline v4 run {run_id} ===")
    logger.info(f"Script: {script[:50]}...")
    logger.info(f"Scenes: {num_scenes} x {video_duration}s")
    logger.info(f"Product image: {product_image or 'None (FLUX gen only)'}")
    logger.info(f"SAM3: {'ON' if enable_sam3 else 'OFF'}")

    cost_sam3 = 0.0
    cost_image = 0.0
    cost_voice = 0.0
    cost_video = 0.0

    # ── Step 0: SAM3 Analyze ──
    sam3_analysis = None
    ref_image_for_video = None

    if enable_sam3 and product_image and os.path.exists(product_image):
        logger.info("Step 0/4: SAM3 Analyze")
        sam3_analysis = sam3_analyze_image(product_image, run_id)
        cost_sam3 = 0.0011

        # Export layout
        layout_path = TMP_DIR / f"layout_{run_id}.json"
        with open(layout_path, "w") as f:
            json.dump({
                "objects": sam3_analysis["objects"],
                "safe_zones": sam3_analysis["safe_zones"],
                "layout": sam3_analysis["layout"],
                "prompt_insights": sam3_analysis["prompt_insights"],
            }, f, indent=2)
        logger.info(f"  Layout -> {layout_path}")

        # Use real product image as video reference
        ref_image_for_video = product_image

    # ── Step 1: Image (FLUX) ──
    # Need a base image for img2vid — either product_image or FLUX gen
    if not ref_image_for_video and image_prompt:
        logger.info("Step 1/4: FLUX Image")
        img_url = generate_image(image_prompt, reference_analysis=sam3_analysis)
        img_path = TMP_DIR / f"image_{run_id}.png"
        download_file(img_url, img_path)
        ref_image_for_video = str(img_path)
        cost_image = 0.001
    elif not ref_image_for_video:
        # Fallback: generate generic product image
        generic_prompt = scene_prompts[0] if scene_prompts else "product showcase, clean background"
        img_url = generate_image(generic_prompt, reference_analysis=sam3_analysis)
        img_path = TMP_DIR / f"image_{run_id}.png"
        download_file(img_url, img_path)
        ref_image_for_video = str(img_path)
        cost_image = 0.001

    # ── Step 2: Voice (สร้างก่อน video เพราะต้องใช้เป็น audio input!) ──
    logger.info("Step 2/4: Voice")
    voice_url = generate_voice(script, voice_id=voice_id)
    voice_path = TMP_DIR / f"voice_{run_id}.mp3"
    download_file(voice_url, voice_path)
    voice_char_count = len(script)
    cost_voice = (voice_char_count / 1000) * 0.06

    # ── Step 3: Video — Wan 2.7 img2vid+audio (Lip Sync in one!) ──
    logger.info("Step 3/4: Video (img2vid+audio)")
    video_paths = []
    for i, prompt in enumerate(scene_prompts):
        logger.info(f"  Scene {i+1}/{num_scenes}: {prompt[:40]}...")
        vid_url = generate_video_with_image_and_audio(
            image_path=ref_image_for_video,
            audio_path=voice_path,
            prompt=prompt,
            duration=video_duration,
            reference_analysis=sam3_analysis,
        )
        vpath = TMP_DIR / f"scene_{run_id}_{i}.mp4"
        download_file(vid_url, vpath)
        video_paths.append(vpath)

    cost_video = num_scenes * 0.03

    # ── Step 4: Concat scenes (ถ้ามีหลาย scene) ──
    if num_scenes > 1:
        logger.info("Step 4/4: Concat")
        final_path = STORAGE_DIR / f"affiliate_{run_id}.mp4"
        concat_videos(video_paths, final_path)
    else:
        final_path = STORAGE_DIR / f"affiliate_{run_id}.mp4"
        import shutil
        shutil.copy2(video_paths[0], final_path)

    # Cost summary
    cost_total = cost_sam3 + cost_image + cost_voice + cost_video
    cost_breakdown = {
        "sam3": round(cost_sam3, 4),
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
        "sam3": {
            "enabled": sam3_analysis is not None,
            "objects": [o["label"] for o in (sam3_analysis["objects"] if sam3_analysis else [])],
            "layout": sam3_analysis.get("layout", {}) if sam3_analysis else {},
        } if sam3_analysis else None,
    }


# ─── CLI ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Affiliate Video Pipeline v4 (Prodia)")
    parser.add_argument("--script", required=True, help="Voice over text (Thai)")
    parser.add_argument("--prompts", nargs="+", required=True, help="Scene prompts")
    parser.add_argument("--voice", default="English_Trustworth_Man", help="Voice ID")
    parser.add_argument("--duration", type=int, default=8, help="Seconds per scene")
    parser.add_argument("--image", default="", help="FLUX image prompt (optional)")
    parser.add_argument("--product-image", default="", help="Product image path for SAM3")
    parser.add_argument("--no-sam3", action="store_true", help="Disable SAM3 analysis")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    result = run_pipeline(
        script=args.script,
        scene_prompts=args.prompts,
        voice_id=args.voice,
        video_duration=args.duration,
        image_prompt=args.image or None,
        product_image=args.product_image or None,
        enable_sam3=not args.no_sam3,
    )

    print("\n✅ Done!")
    print(f"  Final: {result['final_path']}")
    print(f"  Cost:  ${result['cost_estimate']}")
    print(f"  Breakdown: {result['cost_breakdown']}")
    if result.get("sam3"):
        print(f"  SAM3: {result['sam3']['objects']}")
