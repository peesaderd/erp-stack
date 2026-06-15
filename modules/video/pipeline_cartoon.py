"""
TikTok UGC Studio — Affiliate Cartoon Pipeline
===============================================
Pipeline: Seedream V4.5 (cartoon image) → Wan 2.2 Video → MiniMax Voice → FFmpeg Merge

ไม่ต้องอ้างอิงรูปสินค้า — ใช้ AI สร้างภาพการ์ตูน/illustration ล้วนๆ

ต้นทุนต่อคลิป:
  - 8 วิ (ไม่ Lip Sync): ~$0.20
  - 16 วิ (ไม่ Lip Sync): ~$0.36
  - 8 วิ (มี Lip Sync):   ~$0.25
  - 16 วิ (มี Lip Sync):  ~$0.47
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

logger = logging.getLogger("tiktok-ugc.pipeline_cartoon")

# ─── Config ────────────────────────────────────────────────────────────────

FAL_KEY = ***"FAL_API_KEY", "") or os.environ.get("FAL_KEY", "")
WAVESPEED_KEY = ***"WAVESPEED_API_KEY", "") or os.environ.get("WAVESPEED_KEY", "")

STORAGE_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "storage"
TMP_DIR = STORAGE_DIR / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

CARTOON_STYLES = [
    "anime",           # anime style
    "disney_pixar",    # 3D cartoon like Disney/Pixar
    "kawaii",          # cute kawaii chibi
    "vector_flat",     # flat vector illustration
    "watercolor",      # watercolor painting
    "comic",           # comic book style
    "2d_illustration", # 2D digital illustration
    "line_art",        # simple line art with color
]


# ─── Step 0: Cartoon Image (Seedream V4.5) ────────────────────────────────

def generate_cartoon_image(prompt: str, style: str = "anime",
                           image_size: str = "square_hd") -> str:
    """
    สร้างภาพการ์ตูน/illustration โดยไม่ต้องอ้างอิงรูปสินค้าจริง

    Args:
        prompt: คำอธิบายภาษาไทยหรืออังกฤษ
        style: สไตล์การ์ตูน (anime, disney_pixar, kawaii, vector_flat, etc.)
        image_size: ขนาดภาพ

    Returns:
        URL ของภาพที่สร้าง

    Cost: $0.04/ภาพ
    """
    style_hints = {
        "anime": "anime style, Japanese anime art, clean line art, vibrant colors",
        "disney_pixar": "3D cartoon style, Pixar/Disney style, soft rendering, cute characters",
        "kawaii": "kawaii chibi style, cute, pastel colors, round faces, adorable",
        "vector_flat": "flat vector illustration style, clean shapes, modern design, minimalist",
        "watercolor": "watercolor painting style, soft colors, artistic, dreamy",
        "comic": "comic book style, bold outlines, halftone shading, dynamic",
        "2d_illustration": "2D digital illustration, beautiful rendering, detailed background",
        "line_art": "line art with flat colors, simple, elegant, clean outlines"
    }
    style_hint = style_hints.get(style, style_hints["anime"])

    full_prompt = f"{prompt}, {style_hint}"

    url = "https://fal.run/fal-ai/bytedance/seedream/v4.5/text-to-image"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {
        "prompt": full_prompt,
        "image_size": image_size,
        "num_images": 1,
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

def generate_voice(text: str, voice_id: str = "English_Upbeat_Woman",
                   speed: float = 1.0) -> str:
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


# ─── Step 2: Video Scene (Wan 2.2 Ultra Fast @ WaveSpeed) ────────────────

def generate_video_scene(prompt: str, duration: int = 8,
                         negative_prompt: str = "blurry, low quality, distorted") -> str:
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
    status_url = inner.get("urls", {}).get("get", "")
    if not status_url:
        raise RuntimeError(f"WaveSpeed: no status URL: {data}")

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
    raise TimeoutError("WaveSpeed timed out")


# ─── Step 3: Lip Sync (VEED @ Fal.ai) — Optional ─────────────────────────

def lip_sync(video_url: str, audio_url: str) -> str:
    url = "https://fal.run/veed/lipsync"
    headers = {"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"}
    payload = {"video_url": video_url, "audio_url": audio_url}
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    output_url = data.get("video", {}).get("url", "") or data.get("output", {}).get("url", "")
    if not output_url:
        raise RuntimeError(f"VEED Lip Sync failed: {data}")
    return output_url


# ─── Step 4: Download + Concat + Merge (FFmpeg) ──────────────────────────

def download_file(url: str, output_path: Path) -> Path:
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path


def concat_videos(video_paths: list[Path], output_path: Path) -> Path:
    list_file = TMP_DIR / f"concat_{uuid.uuid4().hex}.txt"
    with open(list_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp.absolute()}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(list_file), "-c", "copy", str(output_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink(missing_ok=True)
    return output_path


def merge_audio_video(video_path: Path, voice_path: Path,
                      bgm_path: Optional[Path], output_path: Path,
                      voice_volume: float = 1.0, bgm_volume: float = 0.3) -> Path:
    if bgm_path and bgm_path.exists():
        filter_complex = (
            f"[1:a]volume={voice_volume}[v];"
            f"[2:a]volume={bgm_volume}[b];"
            f"[v][b]amix=inputs=2:duration=first[a]"
        )
        cmd = ["ffmpeg", "-y",
               "-i", str(video_path), "-i", str(voice_path), "-i", str(bgm_path),
               "-filter_complex", filter_complex,
               "-map", "0:v", "-map", "[a]", "-c:v", "copy", str(output_path)]
    else:
        cmd = ["ffmpeg", "-y",
               "-i", str(video_path), "-i", str(voice_path),
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(output_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


# ─── Full Pipeline ─────────────────────────────────────────────────────────

def run_pipeline(
    script: str,
    scene_prompts: list[str],
    voice_id: str = "English_Upbeat_Woman",
    bgm_url: Optional[str] = None,
    enable_lip_sync: bool = False,
    video_duration: int = 8,
    cartoon_style: str = "anime",
    cartoon_prompt: Optional[str] = None,
) -> dict:
    """
    รัน cartoon pipeline — สร้างคลิปสไตล์การ์ตูน/illustration สำหรับ Affiliate

    Args:
        script: ข้อความเสียงพากย์ (ภาษาไทย)
        scene_prompts: list ของ prompt แต่ละ scene
        voice_id: เสียงพากย์ (แนะนำ English_Upbeat_Woman สำหรับการ์ตูน)
        bgm_url: URL BGM (optional)
        enable_lip_sync: เปิด Lip Sync หรือไม่
        video_duration: ความยาวต่อ scene (วินาที)
        cartoon_style: สไตล์การ์ตูน (anime, disney_pixar, kawaii, ฯลฯ)
        cartoon_prompt: ถ้าใส่ = สร้างภาพการ์ตูน Seedream ก่อน

    Returns:
        dict { "final_path": Path, "cost_estimate": float, "files": {...} }
    """
    run_id = uuid.uuid4().hex[:8]
    logger.info(f"=== Cartoon Pipeline run {run_id} ===")
    logger.info(f"Script: {script[:50]}...")
    logger.info(f"Scenes: {len(scene_prompts)} × {video_duration}s")
    logger.info(f"Style: {cartoon_style}")

    cost_image = 0.0
    image_path = None

    # 0. Cartoon Image (optional)
    if cartoon_prompt:
        logger.info(f"Step 0/6: Generating cartoon image ({cartoon_style})...")
        image_url = generate_cartoon_image(cartoon_prompt, style=cartoon_style)
        image_path = TMP_DIR / f"cartoon_{run_id}.png"
        download_file(image_url, image_path)
        cost_image = 0.04
        logger.info(f"  Image URL: {image_url}")

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
    cost_video = len(scene_prompts) * 0.16

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

    # 5. BGM
    bgm_path = None
    if bgm_url:
        logger.info("Downloading BGM...")
        bgm_path = TMP_DIR / f"bgm_{run_id}.mp3"
        download_file(bgm_url, bgm_path)

    # 6. Final merge
    logger.info("Final step: Merging audio + video...")
    final_path = STORAGE_DIR / f"cartoon_{run_id}.mp4"
    merge_audio_video(concat_path, voice_path, bgm_path, final_path)

    cost_total = cost_voice + cost_video + cost_lip_sync + cost_image
    cost_breakdown = {
        "image": round(cost_image, 4),
        "voice": round(cost_voice, 4),
        "video": round(cost_video, 4),
        "lip_sync": round(cost_lip_sync, 4),
        "total": round(cost_total, 4)
    }

    logger.info(f"=== Cartoon Pipeline complete: {final_path} ===")
    logger.info(f"Cost: ${cost_total}")

    return {
        "run_id": run_id,
        "cartoon_style": cartoon_style,
        "final_path": str(final_path),
        "cost_estimate": cost_total,
        "cost_breakdown": cost_breakdown,
        "files": {
            "image": str(image_path) if image_path else None,
            "voice": str(voice_path),
            "video": str(concat_path),
            "bgm": str(bgm_path) if bgm_path else None,
            "final": str(final_path)
        }
    }


# ─── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Cartoon Affiliate Video Pipeline")
    parser.add_argument("--script", required=True, help="Voice over text (Thai)")
    parser.add_argument("--prompts", nargs="+", required=True, help="Scene prompts")
    parser.add_argument("--voice", default="English_Upbeat_Woman",
                        help="Voice ID (แนะนำ English_Upbeat_Woman สำหรับการ์ตูน)")
    parser.add_argument("--bgm", default="", help="BGM URL (optional)")
    parser.add_argument("--lip-sync", action="store_true", help="Enable lip sync")
    parser.add_argument("--duration", type=int, default=8, help="Seconds per scene")
    parser.add_argument("--style", default="anime",
                        help=f"Cartoon style: {', '.join(CARTOON_STYLES)}")
    parser.add_argument("--image", default="", help="Cartoon image prompt (optional)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    result = run_pipeline(
        script=args.script,
        scene_prompts=args.prompts,
        voice_id=args.voice,
        bgm_url=args.bgm or None,
        enable_lip_sync=args.lip_sync,
        video_duration=args.duration,
        cartoon_style=args.style,
        cartoon_prompt=args.image or None,
    )

    print("\n✅ Cartoon clip done!")
    print(f"  Style: {result['cartoon_style']}")
    print(f"  Final: {result['final_path']}")
    print(f"  Cost:  ${result['cost_estimate']}")
    print(f"  Breakdown: {result['cost_breakdown']}")
