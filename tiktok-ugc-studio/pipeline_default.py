#!/usr/bin/env python3
"""
TikTok UGC Studio - Default Pipeline (Prodia Only)
Pipeline: Image (FLUX) -> Video (Wan 2.7) -> Voice (MiniMax) -> FFmpeg

Design:
- 8s: 1 clip, voice 1.5s-6.5s (5s), end scene 6.5s-8s
- 16s: 2 clips, FFmpeg concat, same voice timing each clip
- Prodia ONLY - no provider option

Cost:
  8s = $0.034/scene
  16s = $0.064/scene
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

STORAGE_DIR = Path(__file__).parent / "storage"
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


# --- Step 1: Image (FLUX schnell @ Prodia $0.001) ---
def generate_image(prompt: str) -> str:
    logger.info(f"Image via Prodia FLUX: {prompt[:40]}...")
    payload = {"type": PRODIA_IMAGE_TYPE, "config": {"prompt": prompt, "steps": 4}}
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


# --- Step 2: Video (Wan 2.7 @ Prodia $0.03/gen) ---
def generate_video(prompt: str, duration: int = 8) -> str:
    logger.info(f"Video via Prodia Wan 2.7 ({duration}s): {prompt[:40]}...")
    payload = {"type": PRODIA_VIDEO_TYPE, "config": {"prompt": prompt}}
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
) -> dict:
    run_id = uuid.uuid4().hex[:8]
    num_scenes = len(scene_prompts)
    clip_duration = 8
    total_duration = num_scenes * clip_duration

    logger.info(f"=== Pipeline run {run_id} ===")
    logger.info(f"Script: {script[:50]}...")
    logger.info(f"Scenes: {num_scenes} x {clip_duration}s = {total_duration}s")
    logger.info(f"Voice: {voice_timing}s -> {voice_timing + VOICE_DURATION_SEC}s")

    # Step 1: Images
    image_paths = []
    for i, prompt in enumerate(scene_prompts):
        logger.info(f"Step {i+1}/{3 + num_scenes}: Image {i+1}")
        img_url = generate_image(prompt)
        img_path = TMP_DIR / f"img_{run_id}_{i}.png"
        download_file(img_url, img_path)
        image_paths.append(img_path)
    cost_image = num_scenes * 0.001

    # Step 2: Videos
    video_paths = []
    for i, prompt in enumerate(scene_prompts):
        logger.info(f"Step {1 + num_scenes + i}/{3 + num_scenes}: Video {i+1}")
        vid_url = generate_video(prompt, clip_duration)
        vid_path = TMP_DIR / f"vid_{run_id}_{i}.mp4"
        download_file(vid_url, vid_path)
        video_paths.append(vid_path)
    cost_video = num_scenes * 0.03

    # Step 3: Voice
    logger.info(f"Step {1 + 2*num_scenes}/{3 + num_scenes}: Voice")
    voice_url = generate_voice(script, voice_id=voice_id)
    voice_path = TMP_DIR / f"voice_{run_id}.mp3"
    download_file(voice_url, voice_path)
    cost_voice = (len(script) / 1000) * 0.06

    # Step 4: Concat if multi-scene
    if num_scenes > 1:
        logger.info(f"Step {2 + 2*num_scenes}/{3 + num_scenes}: Concat")
        concat_path = TMP_DIR / f"concat_{run_id}.mp4"
        concat_videos(video_paths, concat_path)
        video_for_merge = concat_path
    else:
        video_for_merge = video_paths[0]

    # Step 5: Merge voice
    final_path = STORAGE_DIR / f"default_{run_id}.mp4"
    merge_voice_video(video_for_merge, voice_path, final_path, start_sec=voice_timing)

    # Cost summary
    cost_total = cost_image + cost_video + cost_voice
    cost_breakdown = {
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
        fp.unlink(missing_ok=True)
    voice_path.unlink(missing_ok=True)
    if num_scenes > 1:
        concat_path.unlink(missing_ok=True)

    return {
        "run_id": run_id,
        "final_path": str(final_path),
        "duration": total_duration,
        "scenes": num_scenes,
        "voice_script": script,
        "voice_timing": {"start": voice_timing, "duration": VOICE_DURATION_SEC, "end": voice_timing + VOICE_DURATION_SEC},
        "cost_estimate": cost_total,
        "cost_breakdown": cost_breakdown,
        "files": {"final": str(final_path)}
    }


# --- CLI ---
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Default Prodia Pipeline")
    parser.add_argument("--script", required=True, help="Voice text (~50-80 chars for 5s)")
    parser.add_argument("--prompts", nargs="+", required=True, help="Scene prompts (1 for 8s, 2 for 16s)")
    parser.add_argument("--voice", default="English_Trustworth_Man", help="Voice ID")
    parser.add_argument("--voice-timing", type=float, default=VOICE_START_SEC, help="Voice start (sec)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    result = run_pipeline(
        script=args.script,
        scene_prompts=args.prompts,
        voice_id=args.voice,
        voice_timing=args.voice_timing,
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
    print(f"{'='*50}")
