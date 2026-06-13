"""
TikTok UGC Studio — Affiliate Video Pipeline (MVP)
===================================================
Pipeline: WaveSpeed Wan 2.2 Ultra (video) → MiniMax Speech (voice) → VEED Lip Sync (optional) → FFmpeg (merge)

ต้นทุนต่อคลิป:
  - 8 วิ (ไม่มี Lip Sync):  ~$0.17
  - 16 วิ (ไม่มี Lip Sync): ~$0.33
  - 8 วิ (มี Lip Sync):     ~$0.22
  - 16 วิ (มี Lip Sync):    ~$0.44
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
WAVESPEED_KEY = os.environ.get("WAVESPEED_API_KEY", "") or os.environ.get("WAVESPEED_KEY", "")
PRODIA_TOKEN = os.environ.get("PRODIA_TOKEN", "") or os.environ.get("PRODIA_KEY", "")

STORAGE_DIR = Path(__file__).parent / "storage"
TMP_DIR = STORAGE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# ─── Step 0: Image Generation (FLUX schnell @ Prodia) ────────────────────

def generate_image(prompt: str, image_size: str = "square_hd", num_images: int = 1) -> str:
    """
    สร้างรูปภาพผ่าน FLUX schnell @ Prodia
    ถูกกว่า Seedream 40 เท่า

    Args:
        prompt: คำอธิบายภาพ
        image_size: ขนาด (square_hd=1024x1024)
        num_images: จำนวนภาพ

    Returns:
        URL ของรูปภาพ

    Cost: $0.001/ภาพ
    """
    if not PRODIA_TOKEN:
        # Fallback to Seedream if Prodia not configured
        logger.warning("PRODIA_TOKEN not configured, falling back to Seedream")
        return generate_image_fal(prompt, image_size, num_images)

    # Prodia FLUX schnell — asynchronous job + poll
    submit_url = "https://inference.prodia.com/v2/job"
    headers = {"Authorization": f"Bearer {PRODIA_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "type": "inference.flux-fast.schnell.txt2img.v2",
        "config": {
            "prompt": prompt,
            "steps": 4,
            "seed": -1
        }
    }

    resp = requests.post(submit_url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    job_id = data.get("job", {}).get("id", "") or data.get("id", "")
    if not job_id:
        raise RuntimeError(f"Prodia image submit failed: {data}")

    # Poll
    status_url = f"https://inference.prodia.com/v2/job/{job_id}"
    for _ in range(60):
        time.sleep(2)
        status_resp = requests.get(status_url, headers=headers, timeout=10)
        status_data = status_resp.json()
        status = status_data.get("status", "")
        if status == "completed":
            output = status_data.get("output", {}) or status_data.get("result", {})
            if isinstance(output, dict):
                url = output.get("url", "") or output.get("image", {}).get("url", "")
            else:
                url = str(output) if output else ""
            if not url:
                image_url = status_data.get("image", {}).get("url", "") or status_data.get("output_url", "")
                if image_url:
                    return image_url
                raise RuntimeError(f"Prodia image completed but no URL: {status_data}")
            return url
        elif status in ("failed", "error"):
            raise RuntimeError(f"Prodia image failed: {status_data}")

    raise TimeoutError("Prodia image generation timed out")


def generate_image_fal(prompt: str, image_size: str = "square_hd", num_images: int = 1) -> str:
    """
    Fallback: Seedream V4.5 @ Fal.ai ($0.04/ภาพ)
    """
    url = "https://fal.run/fal-ai/bytedance/seedream/v4.5/text-to-image"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt,
        "image_size": image_size,
        "num_images": num_images,
        "expand_prompt": True
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    images = data.get("images", [])
    if not images:
        raise RuntimeError(f"Seedream failed: {data}")
    return images[0].get("url", "")


# ─── Step 1: Voice Over (MiniMax Speech @ Fal.ai) ─────────────────────────

def generate_voice(text: str, voice_id: str = "English_Trustworth_Man",
                   speed: float = 1.0) -> str:
    """
    สร้างเสียงพากย์ภาษาไทยผ่าน MiniMax Speech-02 Turbo @ Fal.ai

    Args:
        text: ข้อความภาษาไทย
        voice_id: เสียง (แนะนำ: English_Trustworth_Man)
        speed: ความเร็ว 0.5-2.0

    Returns:
        URL ของไฟล์เสียง MP3

    Cost: ~$0.06/1K chars → 5 วิ (~75 chars) = ~$0.005
    """
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


# ─── Step 2a: Video Scene (Wan 2.2 Ultra Fast @ WaveSpeed) ────────────────

def generate_video_wavespeed(prompt: str, duration: int = 8,
                              negative_prompt: str = "blurry, low quality, distorted") -> str:
    """
    สร้างวิดีโอ 1 scene ผ่าน WaveSpeed Wan 2.2 Ultra Fast 480p

    Args:
        prompt: คำอธิบาย scene
        duration: ความยาววินาที (8 วิ default)
        negative_prompt: สิ่งที่ไม่ต้องการ

    Returns:
        URL ของไฟล์วิดีโอ MP4

    Cost: $0.16/8วิ
    """
    submit_url = "https://api.wavespeed.ai/api/v3/wavespeed-ai/wan-2.2/t2v-480p-ultra-fast"
    headers = {"Authorization": f"Bearer {WAVESPEED_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "size": "832*480",
        "duration": duration,
        "seed": -1
    }

    resp = requests.post(submit_url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"WaveSpeed submit failed: {data}")
    inner = data.get("data", {})
    prediction_id = inner.get("id", "")
    status_url = inner.get("urls", {}).get("get", "")
    if not status_url:
        raise RuntimeError(f"WaveSpeed: no status URL in response: {data}")

    for _ in range(60):
        time.sleep(5)
        status_resp = requests.get(status_url, headers=headers, timeout=10)
        status_data = status_resp.json()
        inner_data = status_data.get("data", {}) if status_data.get("code") == 200 else status_data
        st = inner_data.get("status", "")
        outputs = inner_data.get("outputs", [])
        if st == "completed" and outputs:
            return outputs[0]
        elif st in ("failed", "error"):
            raise RuntimeError(f"WaveSpeed failed: {status_data}")
        elif st == "created" or not st:
            continue
    raise TimeoutError("WaveSpeed video generation timed out")


# ─── Step 2b: Video Scene (Wan 2.7 @ Prodia) ──────────────────────────────

def generate_video_prodia(prompt: str, duration: int = 8) -> str:
    """
    สร้างวิดีโอ 1 scene ผ่าน Prodia Wan 2.7 480p
    รองรับ 2-15 วิ ต่อ gen

    Args:
        prompt: คำอธิบาย scene
        duration: ความยาววินาที (2-15 วิ)

    Returns:
        URL ของไฟล์วิดีโอ MP4

    Cost: $0.03/gen (ไม่จำกัดวินาที)
    """
    if not PRODIA_TOKEN:
        raise RuntimeError("PRODIA_TOKEN not configured")

    # Prodia REST API v2
    job_url = "https://inference.prodia.com/v2/job"
    headers = {"Authorization": f"Bearer {PRODIA_TOKEN}", "Content-Type": "application/json"}

    # Submit job
    payload = {
        "type": "inference.wan2-7.txt2vid.v1",
        "config": {
            "prompt": prompt,
            "num_inference_steps": 30,
        }
    }

    resp = requests.post(job_url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    job_id = data.get("job", {}).get("id", "") or data.get("id", "")
    if not job_id:
        raise RuntimeError(f"Prodia submit failed: {data}")

    # Poll until complete
    status_url = f"https://inference.prodia.com/v2/job/{job_id}"
    for _ in range(120):  # max 10 min
        time.sleep(5)
        status_resp = requests.get(status_url, headers=headers, timeout=10)
        status_data = status_resp.json()
        status = status_data.get("status", "")

        if status == "completed":
            # Get output URL
            output = status_data.get("output", {}) or status_data.get("result", {})
            if isinstance(output, dict):
                url = output.get("url", "") or output.get("video", {}).get("url", "")
            else:
                url = str(output) if output else ""
            if not url:
                # Check alternative response format
                video_url = status_data.get("video", {}).get("url", "") or status_data.get("output_url", "")
                if video_url:
                    return video_url
                raise RuntimeError(f"Prodia completed but no video URL: {status_data}")
            return url

        elif status in ("failed", "error"):
            raise RuntimeError(f"Prodia failed: {status_data}")

    raise TimeoutError("Prodia video generation timed out")


# ─── Video Scene (Prodia Wan 2.7 — วิธีเดียว) ─────────────────────────────

def generate_video_scene(prompt: str, duration: int = 8, **kwargs) -> str:
    """สร้างวิดีโอ 1 scene ผ่าน Prodia Wan 2.7 ($0.03/gen)"""
    return generate_video_prodia(prompt, duration)


# ─── Step 3: Lip Sync (VEED @ Fal.ai) — Optional ─────────────────────────

def lip_sync(video_url: str, audio_url: str) -> str:
    """
    Lip Sync วิดีโอ + เสียงพากย์ (optional step)

    Args:
        video_url: URL วิดีโอต้นทาง
        audio_url: URL เสียงพากย์

    Returns:
        URL วิดีโอที่ lip sync แล้ว

    Cost: $0.40/นาที → 8 วิ = $0.054, 16 วิ = $0.107
    """
    url = "https://fal.run/veed/lipsync"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "video_url": video_url,
        "audio_url": audio_url
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    output_url = data.get("video", {}).get("url", "") or data.get("output", {}).get("url", "")
    if not output_url:
        raise RuntimeError(f"VEED Lip Sync failed: {data}")
    return output_url


# ─── Step 4: Download + Concat + Merge (FFmpeg) ──────────────────────────

def download_file(url: str, output_path: Path) -> Path:
    """ดาวน์โหลดไฟล์จาก URL"""
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path


def concat_videos(video_paths: list[Path], output_path: Path) -> Path:
    """ต่อวิดีโอหลาย scene ด้วย FFmpeg concat"""
    list_file = TMP_DIR / f"concat_{uuid.uuid4().hex}.txt"
    with open(list_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp.absolute()}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink(missing_ok=True)
    return output_path


def merge_audio_video(video_path: Path, voice_path: Path,
                      bgm_path: Optional[Path], output_path: Path,
                      voice_volume: float = 1.0, bgm_volume: float = 0.3) -> Path:
    """
    รวมวิดีโอ + เสียงพากย์ + BGM

    Args:
        video_path: วิดีโอหลัก (อาจเป็น concat แล้ว)
        voice_path: เสียงพากย์
        bgm_path: BGM (ถ้ามี)
        output_path: ไฟล์สุดท้าย
        voice_volume: ความดังเสียงพากย์
        bgm_volume: ความดัง BGM

    Returns:
        Path ของไฟล์สุดท้าย
    """
    if bgm_path and bgm_path.exists():
        # Mix voice + BGM
        filter_complex = (
            f"[1:a]volume={voice_volume}[v];"
            f"[2:a]volume={bgm_volume}[b];"
            f"[v][b]amix=inputs=2:duration=first[a]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(voice_path),
            "-i", str(bgm_path),
            "-filter_complex", filter_complex,
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", str(output_path)
        ]
    else:
        # Only voice
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(voice_path),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


# ─── Full Pipeline ─────────────────────────────────────────────────────────

def run_pipeline(
    script: str,
    scene_prompts: list[str],
    voice_id: str = "English_Trustworth_Man",
    bgm_url: Optional[str] = None,
    enable_lip_sync: bool = False,
    video_duration: int = 8,
    image_prompt: Optional[str] = None
) -> dict:
    """
    รัน full pipeline สร้างคลิป Affiliate
    ใช้ Prodia Wan 2.7 + FLUX schnell ($0.03-0.04/clip)

    Args:
        script: ข้อความเสียงพากย์ (ภาษาไทย)
        scene_prompts: list ของ prompt แต่ละ scene
        voice_id: เสียงพากย์
        bgm_url: URL BGM (ไม่ใส่ = ไม่มี BGM)
        enable_lip_sync: เปิด Lip Sync หรือไม่
        video_duration: ความยาวต่อ scene (วินาที)
        image_prompt: ถ้าใส่ = สร้างรูป FLUX ก่อน

    Returns:
        dict { "final_path": Path, "cost_estimate": float, "files": {...} }
    """
    run_id = uuid.uuid4().hex[:8]
    logger.info(f"=== Pipeline run {run_id} ===")
    logger.info(f"Script: {script[:50]}...")
    logger.info(f"Scenes: {len(scene_prompts)} × {video_duration}s")
    logger.info(f"Lip Sync: {'ON' if enable_lip_sync else 'OFF'}")

    cost_image = 0.0
    image_path = None

    # 0. Optional Image (Seedream)
    if image_prompt:
        logger.info("Step 0/6: Generating image via Seedream V4.5...")
        image_url = generate_image(image_prompt)
        image_path = TMP_DIR / f"image_{run_id}.png"
        download_file(image_url, image_path)
        cost_image = 0.001  # Prodia FLUX; fallback Seedream = 0.04

    # 1. Voice
    logger.info("Step 1/6: Generating voice...")
    voice_url = generate_voice(script, voice_id=voice_id)
    voice_path = TMP_DIR / f"voice_{run_id}.mp3"
    download_file(voice_url, voice_path)
    voice_char_count = len(script)
    cost_voice = (voice_char_count / 1000) * 0.06

    # 2. Video scenes
    logger.info("Step 2/6: Generating video scenes...")
    video_paths = []
    for i, prompt in enumerate(scene_prompts):
        logger.info(f"  Scene {i+1}/{len(scene_prompts)}: {prompt[:40]}...")
        video_url = generate_video_scene(prompt, duration=video_duration)
        vpath = TMP_DIR / f"scene_{run_id}_{i}.mp4"
        download_file(video_url, vpath)
        video_paths.append(vpath)

    total_seconds = len(scene_prompts) * video_duration
    cost_video = len(scene_prompts) * 0.03  # Prodia Wan 2.7 = $0.03/scene

    # 3. Concat scenes
    if len(video_paths) > 1:
        logger.info("Step 3/6: Concatenating scenes...")
        concat_path = TMP_DIR / f"concat_{run_id}.mp4"
        concat_videos(video_paths, concat_path)
    else:
        concat_path = video_paths[0]

    # 4. Optional Lip Sync
    if enable_lip_sync:
        logger.info("Step 4/6: Lip sync...")
        logger.warning("Lip Sync requires hosted URLs — implement upload sub-step")
        cost_lip_sync = total_seconds * 0.0067
    else:
        cost_lip_sync = 0.0

    # 5. Download BGM
    bgm_path = None
    if bgm_url:
        logger.info("Downloading BGM...")
        bgm_path = TMP_DIR / f"bgm_{run_id}.mp3"
        download_file(bgm_url, bgm_path)

    # 6. Final merge
    logger.info("Final step: Merging audio + video...")
    final_path = STORAGE_DIR / f"affiliate_{run_id}.mp4"
    merge_audio_video(concat_path, voice_path, bgm_path, final_path)

    # Cost summary
    cost_total = cost_voice + cost_video + cost_lip_sync + cost_image
    cost_breakdown = {
        "image": round(cost_image, 4),
        "voice": round(cost_voice, 4),
        "video": round(cost_video, 4),
        "lip_sync": round(cost_lip_sync, 4),
        "total": round(cost_total, 4)
    }

    logger.info(f"=== Pipeline complete: {final_path} ===")
    logger.info(f"Cost: ${cost_total}")

    return {
        "run_id": run_id,
        "final_path": str(final_path),
        "cost_estimate": cost_total,
        "cost_breakdown": cost_breakdown,
        "files": {
            "voice": str(voice_path),
            "video": str(concat_path),
            "bgm": str(bgm_path) if bgm_path else None,
            "final": str(final_path)
        }
    }


# ─── CLI Usage ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Affiliate Video Pipeline")
    parser.add_argument("--script", required=True, help="Voice over text (Thai)")
    parser.add_argument("--prompts", nargs="+", required=True, help="Scene prompts")
    parser.add_argument("--voice", default="English_Trustworth_Man", help="Voice ID")
    parser.add_argument("--bgm", default="", help="BGM URL (optional)")
    parser.add_argument("--lip-sync", action="store_true", help="Enable lip sync")
    parser.add_argument("--duration", type=int, default=8, help="Seconds per scene")
    parser.add_argument("--image", default="", help="Seedream image prompt (optional)")
    # Prodia เท่านั้น
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    result = run_pipeline(
        script=args.script,
        scene_prompts=args.prompts,
        voice_id=args.voice,
        bgm_url=args.bgm or None,
        enable_lip_sync=args.lip_sync,
        video_duration=args.duration,
        image_prompt=args.image or None
    )

    print("\n✅ Done!")
    print(f"  Final: {result['final_path']}")
    print(f"  Cost:  ${result['cost_estimate']}")
    print(f"  Breakdown: {result['cost_breakdown']}")
