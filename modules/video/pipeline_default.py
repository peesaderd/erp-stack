#!/usr/bin/env python3
"""
TikTok UGC Studio - Default Pipeline v4 (Prodia + Wan 2.7 Audio-Driven)
======================================================================
Pipeline: SAM3 Analyze -> Voice (MiniMax) -> Wan 2.7 img2vid+Audio (Lip Sync in one!)

Design:
- Wan 2.7 img2vid + audio = Lip sync ในคลิปเดียว ไม่ต้อง VEED/Wav2Lip
- SAM3 วิเคราะห์รูปก่อน gen เพื่อ improve prompt + layout
- Voice สร้างก่อน video เพราะ Wan 2.7 ต้องการ audio input

Cost:
  8s = $0.034/clip (SAM3 + Voice + Video)
  16s = ~$0.064/clip (2 clips)
"""

import os
import json
import time
import uuid
import logging
import subprocess
import requests
from pathlib import Path
from typing import Optional

# SAM3 client (optional)
from sam3_client import segment_image, mask_to_rgba, track_object_in_video

logger = logging.getLogger("tiktok-ugc.pipeline_default")

# --- Load .env ---
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in open(_env_path):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# --- Config ---
PRODIA_TOKEN = os.environ.get("PRODIA_TOKEN", "")
FAL_KEY = os.environ.get("FAL_KEY", "")

STORAGE_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "storage"
TMP_DIR = STORAGE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Voice timing constants
VOICE_START_SEC = 1.5
VOICE_DURATION_SEC = 5
VOICE_END_SEC = VOICE_START_SEC + VOICE_DURATION_SEC  # 6.5s

# Prodia API
PRODIA_BASE = "https://inference.prodia.com/v2"
PRODIA_IMAGE_TYPE = "inference.flux-fast.schnell.txt2img.v2"
PRODIA_VIDEO_TYPE = "inference.wan2-7.txt2vid.v1"
PRODIA_IMG2VID_TYPE = "inference.wan2-7.img2vid.v1"  # Audio-driven lip sync!


# --- Helpers ---
def _prodia_headers():
    if not PRODIA_TOKEN:
        raise RuntimeError("PRODIA_TOKEN not set")
    return {"Authorization": f"Bearer {PRODIA_TOKEN}", "Content-Type": "application/json"}


def _poll_job(job_id: str, max_polls: int = 60, sleep_s: int = 3) -> dict:
    url = f"{PRODIA_BASE}/job/{job_id}"
    headers = _prodia_headers()
    for _ in range(max_polls):
        time.sleep(sleep_s)
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        status = data.get("status", "")
        if status == "completed":
            return data
        elif status in ("failed", "error"):
            raise RuntimeError(f"Prodia job failed: {data}")
    raise TimeoutError(f"Prodia job {job_id} timed out")


def _extract_url(data: dict, key: str = "url") -> str:
    output = data.get("output", {}) or data.get("result", {})
    if isinstance(output, dict):
        url = output.get(key, "") or output.get("image", {}).get(key, "") or output.get("video", {}).get(key, "")
    else:
        url = str(output) if output else ""
    if not url:
        url = data.get("output_url", "") or data.get("image", {}).get(key, "") or data.get("video", {}).get(key, "")
    if not url:
        raise RuntimeError(f"Cannot extract URL: {json.dumps(data, indent=2)[:300]}")
    return url


def download_file(url: str, output_path: Path) -> Path:
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path


# --- Step 0: SAM3 Analyze — วิเคราะห์ภาพสินค้า ก่อนสร้างอะไรทั้งสิ้น ---

def sam3_analyze_image(image_path: str, run_id: str = "") -> dict:
    """
    SAM3 Analyze — Scan รูปสินค้าเพื่อ:
    1. หาตำแหน่ง object หลัก (product, person)
    2. หาพื้นที่ว่างสำหรับวาง text/CTA/Logo
    3. สร้าง layout data สำหรับ artwork
    4. ปรับปรุง prompt สำหรับ FLUX / Wan 2.7

    Args:
        image_path: Path to product image (from scraper)
        run_id: Pipeline run ID

    Returns:
        dict {
            "objects": [{"label": "product", "bbox": [x1,y1,x2,y2], "center": [cx,cy]}]
            "safe_zones": [{"x1","y1","x2","y2","weight"}]  # พื้นที่ว่าง
            "layout": {"cta": [x,y], "logo": [x,y], "price": [x,y]}
            "prompt_insights": "prompt string for gen"
            "masks": [mask_bytes]
        }

    Cost: ~$0.0011/call
    """
    logger.info(f"[SAM3] Analyzing: {image_path}")

    from PIL import Image as PILImage

    # 1. Segment objects
    objects = []
    masks = {}
    img = PILImage.open(image_path)
    w, h = img.size

    # Run multiple SAM3 prompts to understand the scene
    for label in ["product", "person", "bag", "box", "bottle", "text", "logo"]:
        try:
            result_masks = segment_image(image_path, prompt=label, confidence=0.4)
            if result_masks:
                # Get bounding box from largest mask
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

                if best_mask and best_area > (w * h * 0.01):  # ignore tiny detections
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

    # 2. Calculate safe zones (พื้นที่ว่าง)
    # แบ่งภาพเป็น grid 4x4 แล้วดูว่าช่องไหนไม่ชน object
    occupied = [[False] * 4 for _ in range(4)]
    for obj in objects:
        cx, cy = obj["center"]
        gx = min(3, int(cx / w * 4))
        gy = min(3, int(cy / h * 4))
        occupied[gy][gx] = True
        # Mark neighbors as occupied too
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
                weight = 1.0 - (abs(row - 1.5) + abs(col - 1.5)) / 6  # prefer edges
                safe_cells.append({
                    "x": int(cx - w / 8), "y": int(cy - h / 8),
                    "x2": int(cx + w / 8), "y2": int(cy + h / 8),
                    "center": [int(cx), int(cy)],
                    "weight": round(weight, 2)
                })

    # 3. Layout suggestion
    layout = {}
    if safe_cells:
        # CTA -> lowest weight (bottom right, not blocking main view)
        cta_cell = max(safe_cells, key=lambda c: c["weight"] * (c["center"][0] / w) * (c["center"][1] / h))
        layout["cta"] = cta_cell["center"]
        # Logo -> top left or top right
        logo_cell = min(safe_cells, key=lambda c: c["center"][1])
        layout["logo"] = logo_cell["center"]
        # Price -> near product but not on it
        for obj in objects:
            if obj["label"] == "product":
                # place price just below product
                layout["price"] = [obj["center"][0], obj["bbox"][3] + 20]
                break
        else:
            # no product found, use safest corner
            layout["price"] = safe_cells[0]["center"]

    # 4. Prompt insights — ข้อมูลที่ Wan 2.7 / FLUX prompt ควรมี
    prompt_insights = ""
    for obj in objects:
        if obj["label"] == "person":
            prompt_insights += f"person at center, "
        elif obj["label"] == "product":
            prompt_insights += f"product at bottom center, "
    prompt_insights += "clean composition, space for text overlay"

    logger.info(f"[SAM3] Found {len(objects)} objects, {len(safe_cells)} safe zones")
    for obj in objects:
        logger.info(f"  [{obj['label']}] center=({obj['center'][0]:.0f},{obj['center'][1]:.0f}) {obj['area_pct']}%")

    return {
        "objects": objects,
        "safe_zones": safe_cells,
        "layout": layout,
        "prompt_insights": prompt_insights,
        "masks": masks,
        "image_width": w,
        "image_height": h,
    }


# --- Step 1: Image (FLUX schnell @ Prodia $0.001) ---
def generate_image(prompt: str, reference_analysis: dict = None) -> str:
    enhanced = prompt
    if reference_analysis and reference_analysis.get("prompt_insights"):
        enhanced = prompt + ", " + reference_analysis["prompt_insights"]
        logger.info(f"  Prompt enhanced with SAM3: {enhanced[:60]}...")

    logger.info(f"Image via Prodia FLUX: {enhanced[:40]}...")
    payload = {"type": PRODIA_IMAGE_TYPE, "config": {"prompt": enhanced, "steps": 4}}
    resp = requests.post(f"{PRODIA_BASE}/job", headers=_prodia_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    job_id = data.get("job", {}).get("id", "") or data.get("id", "")
    if not job_id:
        raise RuntimeError(f"Prodia image submit failed: {data}")
    result = _poll_job(job_id, max_polls=30, sleep_s=2)
    url = _extract_url(result, "url")
    logger.info(f"  Image OK")
    return url


# --- Step 2: Video (Wan 2.7 img2vid + Audio = Lip Sync in one) $0.03/gen ---
def generate_video(prompt: str, duration: int = 8, reference_analysis: dict = None) -> str:
    """Standard T2V (text-to-video) — no audio"""
    enhanced = prompt
    if reference_analysis and reference_analysis.get("prompt_insights"):
        enhanced = prompt + ", " + reference_analysis["prompt_insights"]

    logger.info(f"Video via Wan 2.7 T2V ({duration}s): {enhanced[:40]}...")
    payload = {"type": PRODIA_VIDEO_TYPE, "config": {"prompt": enhanced}}
    resp = requests.post(f"{PRODIA_BASE}/job", headers=_prodia_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    job_id = data.get("job", {}).get("id", "") or data.get("id", "")
    if not job_id:
        raise RuntimeError(f"Prodia video submit failed: {data}")
    result = _poll_job(job_id, max_polls=120, sleep_s=5)
    url = _extract_url(result, "url")
    logger.info(f"  Video OK")
    return url


def generate_video_with_image_and_audio(image_path: str, audio_path: str, prompt: str,
                                         duration: int = 8,
                                         resolution: str = "720P",
                                         reference_analysis: dict = None) -> str:
    """
    Wan 2.7 img2vid + Audio — สร้างคลิปที่มี Lip Sync ในคลิกเดียว!

    ส่งรูป (portrait/product) + เสียง (MP3/WAV)
    → Wan 2.7 สร้างคลิปปากขยับตามเสียง + movement

    Args:
        image_path: Path to image (product/portrait)
        audio_path: Path to audio file (MP3/WAV)
        prompt: Scene description
        duration: Clip duration (2-15s)
        resolution: 720P or 1080P
        reference_analysis: SAM3 analysis result (optional)

    Returns:
        URL of generated video with built-in lip sync

    Cost: $0.03/gen (เท่า T2V!) — ไม่ต้องเสีย VEED/Wav2Lip เพิ่ม!
    """
    enhanced = prompt
    if reference_analysis and reference_analysis.get("prompt_insights"):
        enhanced = prompt + ", " + reference_analysis["prompt_insights"]

    logger.info(f"Video via Wan 2.7 img2vid+audio ({duration}s): {enhanced[:40]}...")

    # Read file bytes
    with open(image_path, "rb") as f:
        image_data = f.read()
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    # Multipart upload: image + audio + config
    config_payload = {
        "type": PRODIA_IMG2VID_TYPE,
        "config": {
            "prompt": enhanced,
            "duration": duration,
            "resolution": resolution,
            "negative_prompt": "low resolution, error, worst quality, deformed, blurry",
        }
    }
    # Note: audio automatically trimmed to match duration

    files = {
        "image": ("image.png", image_data, "image/png"),
        "audio": ("audio.mp3", audio_data, "audio/mpeg"),
        "config": (None, json.dumps(config_payload), "application/json"),
    }

    resp = requests.post(f"{PRODIA_BASE}/job", headers=_prodia_headers(), files=files, timeout=60)
    resp.raise_for_status()

    # Check response type
    ct = resp.headers.get("content-type", "")
    job_id = ""
    if "multipart" in ct or "application/octet" in ct:
        # Direct binary output
        result_path = TMP_DIR / f"img2vid_{uuid.uuid4().hex[:8]}.mp4"
        with open(result_path, "wb") as f:
            f.write(resp.content)
        # Upload to temp storage or return URL
        # For now: save locally and return path
        logger.info(f"  Video saved locally: {result_path}")
        return str(result_path)

    try:
        data = resp.json()
        job_id = data.get("job", {}).get("id", "") or data.get("id", "")
    except:
        pass

    if not job_id:
        # Maybe direct binary response with unknown content type
        result_path = TMP_DIR / f"img2vid_{uuid.uuid4().hex[:8]}.mp4"
        with open(result_path, "wb") as f:
            f.write(resp.content)
        logger.info(f"  Video saved locally: {result_path}")
        return str(result_path)

    # Poll for completion
    result = _poll_job(f"{PRODIA_BASE}/job/{job_id}", _prodia_headers(), max_polls=120, sleep_s=5)

    url = _extract_url(result, "url")
    logger.info(f"  Video OK (with audio-driven lip sync!)")
    return url
    resp = requests.post(f"{PRODIA_BASE}/job", headers=_prodia_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    job_id = data.get("job", {}).get("id", "") or data.get("id", "")
    if not job_id:
        raise RuntimeError(f"Prodia video submit failed: {data}")
    result = _poll_job(job_id, max_polls=120, sleep_s=5)
    url = _extract_url(result, "url")
    logger.info(f"  Video OK")
    return url


# --- Step 3: Voice (MiniMax @ Fal.ai ~$0.003/5s) ---
def generate_voice(text: str, voice_id: str = "English_Trustworth_Man", speed: float = 1.0) -> str:
    if not FAL_KEY:
        raise RuntimeError("FAL_KEY not set")
    logger.info(f"Voice ({len(text)} chars)")
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
        raise RuntimeError(f"MiniMax voice failed: {data}")
    logger.info(f"  Voice OK")
    return audio_url


# --- Step 4: FFmpeg merge voice into video ---
def merge_voice_video(video_path: Path, voice_path: Path, output_path: Path, start_sec: float = VOICE_START_SEC) -> Path:
    logger.info(f"Merge voice at {start_sec}s for {VOICE_DURATION_SEC}s")
    delay_ms = int(start_sec * 1000)
    filter_complex = f"[1:a]adelay={delay_ms}|{delay_ms}[delayed];[0:a][delayed]amix=inputs=2:duration=first[out]"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(voice_path),
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[out]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    logger.info(f"  Merge OK")
    return output_path


# --- Step 4b: FFmpeg concat videos ---
def concat_videos(video_paths: list[Path], output_path: Path) -> Path:
    list_file = TMP_DIR / f"concat_{uuid.uuid4().hex}.txt"
    with open(list_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp.absolute()}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    list_file.unlink(missing_ok=True)
    return output_path


# --- Full Pipeline ---
def run_pipeline(
    script: str,
    scene_prompts: list[str],
    voice_id: str = "English_Trustworth_Man",
    voice_timing: float = VOICE_START_SEC,
    product_image: str = None,  # NEW: product image for SAM3 analysis
    enable_sam3: bool = True,   # NEW: toggle SAM3
) -> dict:
    run_id = uuid.uuid4().hex[:8]
    num_scenes = len(scene_prompts)
    clip_duration = 8
    total_duration = num_scenes * clip_duration

    logger.info(f"=== Pipeline run {run_id} ===")
    logger.info(f"Script: {script[:50]}...")
    logger.info(f"Scenes: {num_scenes} x {clip_duration}s = {total_duration}s")
    logger.info(f"Voice: {voice_timing}s -> {voice_timing + VOICE_DURATION_SEC}s")
    if product_image:
        logger.info(f"Product image: {product_image}")

    # Step 0 (NEW): SAM3 Analyze
    sam3_analysis = None
    cost_sam3 = 0.0
    if enable_sam3 and product_image and os.path.exists(product_image):
        logger.info(f"Step 0/{3 + num_scenes}: SAM3 Analyze")
        sam3_analysis = sam3_analyze_image(product_image, run_id)
        cost_sam3 = 0.0011  # ~1 SAM3 call

        # Export layout data for future use
        layout_path = TMP_DIR / f"layout_{run_id}.json"
        with open(layout_path, "w") as f:
            json.dump({
                "objects": sam3_analysis["objects"],
                "safe_zones": sam3_analysis["safe_zones"],
                "layout": sam3_analysis["layout"],
                "image_size": [sam3_analysis["image_width"], sam3_analysis["image_height"]],
                "prompt_insights": sam3_analysis["prompt_insights"],
            }, f, indent=2)
        logger.info(f"  Layout data -> {layout_path}")

    # Step 1: Images (with SAM3 enhanced prompt)
    image_paths = []
    for i, prompt in enumerate(scene_prompts):
        logger.info(f"Step {i+1}/{3 + num_scenes}: Image {i+1}")
        img_url = generate_image(prompt, reference_analysis=sam3_analysis)
        img_path = TMP_DIR / f"img_{run_id}_{i}.png"
        download_file(img_url, img_path)
        image_paths.append(img_path)
    cost_image = num_scenes * 0.001

    # Step 2: Voice (ต้องสร้างก่อน Video เพราะ Wan 2.7 ต้องการ audio input)
    logger.info(f"Step {1 + num_scenes}/{3 + num_scenes}: Voice (for audio-driven video)")
    voice_url = generate_voice(script, voice_id=voice_id)
    voice_path = TMP_DIR / f"voice_{run_id}.mp3"
    download_file(voice_url, voice_path)
    cost_voice = (len(script) / 1000) * 0.06

    # Step 3: Videos with Audio + Image (Wan 2.7 img2vid = Lip Sync in one!)
    video_paths = []
    for i, prompt in enumerate(scene_prompts):
        logger.info(f"Step {2 + num_scenes + i}/{3 + num_scenes}: Video {i+1} (img2vid+audio)")

        # Reuse image from Step 1 instead of generating again
        if product_image and os.path.exists(product_image):
            ref_img = product_image
        else:
            ref_img = image_paths[i]

        vid_url = generate_video_with_image_and_audio(
            image_path=ref_img,
            audio_path=voice_path,
            prompt=prompt,
            duration=clip_duration,
            reference_analysis=sam3_analysis
        )
        vid_path = TMP_DIR / f"vid_{run_id}_{i}.mp4"
        download_file(vid_url, vid_path)
        video_paths.append(vid_path)
    cost_video = num_scenes * 0.03

    # Step 4: Concat if multi-scene (video already has audio from Wan 2.7 img2vid!)
    if num_scenes > 1:
        logger.info(f"Step {3 + num_scenes}/{3 + num_scenes}: Concat {num_scenes} clips")
        final_path = STORAGE_DIR / f"default_{run_id}.mp4"
        concat_videos(video_paths, final_path)
    else:
        # Single scene — just rename/download
        final_path = STORAGE_DIR / f"default_{run_id}.mp4"
        # If vid_url is remote, download to final
        if str(video_paths[0]).startswith("http"):
            download_file(video_paths[0], final_path)
        else:
            # Already local
            import shutil
            shutil.copy2(video_paths[0], final_path)

    # Cost summary
    cost_total = cost_sam3 + cost_image + cost_video + cost_voice
    cost_breakdown = {
        "sam3": round(cost_sam3, 4),
        "image": round(cost_image, 4),
        "video": round(cost_video, 4),
        "voice": round(cost_voice, 4),
        "lip_sync": 0.0,
        "total": round(cost_total, 4)
    }

    logger.info(f"=== Done: {final_path} (${cost_total}) ===")

    # Cleanup
    for fp in image_paths:
        fp.unlink(missing_ok=True)
    for fp in video_paths:
        if fp.exists():
            fp.unlink(missing_ok=True)
    if voice_path and voice_path.exists():
        voice_path.unlink(missing_ok=True)

    return {
        "run_id": run_id,
        "final_path": str(final_path),
        "duration": total_duration,
        "scenes": num_scenes,
        "voice_script": script,
        "voice_timing": {"start": 0, "duration": clip_duration, "end": clip_duration},  # Audio native in video
        "lip_sync": "built-in (Wan 2.7 img2vid+audio)",
        "cost_estimate": cost_total,
        "cost_breakdown": cost_breakdown,
        "files": {"final": str(final_path)},
        "sam3": {
            "enabled": sam3_analysis is not None,
            "objects": [o["label"] for o in (sam3_analysis["objects"] if sam3_analysis else [])],
            "safe_zones": len(sam3_analysis["safe_zones"]) if sam3_analysis else 0,
            "layout": sam3_analysis.get("layout", {}) if sam3_analysis else {},
        } if sam3_analysis else None,
    }


# --- CLI ---
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Default Prodia Pipeline")
    parser.add_argument("--script", required=True, help="Voice text (~50-80 chars for 5s)")
    parser.add_argument("--prompts", nargs="+", required=True, help="Scene prompts (1 for 8s, 2 for 16s)")
    parser.add_argument("--voice", default="English_Trustworth_Man", help="Voice ID")
    parser.add_argument("--voice-timing", type=float, default=VOICE_START_SEC, help="Voice start (sec)")
    parser.add_argument("--product-image", default="", help="Product image path for SAM3 analysis")
    parser.add_argument("--no-sam3", action="store_true", help="Disable SAM3 analysis")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    result = run_pipeline(
        script=args.script,
        scene_prompts=args.prompts,
        voice_id=args.voice,
        voice_timing=args.voice_timing,
        product_image=args.product_image if args.product_image else None,
        enable_sam3=not args.no_sam3,
    )

    dur = result["duration"]
    cost = result["cost_estimate"]
    t = result["voice_timing"]
    print(f"\n{'='*50}")
    print(f"Pipeline complete!")
    print(f"  Duration: {dur}s ({result['scenes']} scenes)")
    print(f"  Voice: {t['start']}s -> {t['end']}s ({t['duration']}s)")
    print(f"  Cost: ${cost}")
    print(f"  Final: {result['final_path']}")
    if result.get("sam3"):
        print(f"  SAM3: {result['sam3']['objects']} | layout: {result['sam3']['layout']}")
    print(f"{'='*50}")
