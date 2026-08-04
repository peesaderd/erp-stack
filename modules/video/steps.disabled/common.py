"""Shared utilities for pipeline steps."""
import os
import sys
import json
import uuid
import logging
import subprocess
import shutil
from pathlib import Path
import requests

# Add erp-stack to path for shared_config
_erp_stack = Path(__file__).parent.parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from shared_config import PRODIA_TOKEN, GEMINI_API_KEY

logger = logging.getLogger("tiktok-ugc.pipeline")

# ─── Config ────────────────────────────────────────────────────────────────
STORAGE_DIR = Path(__file__).parent.parent / "storage"
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
            f.write(f"file \"{Path(vp).absolute()}\"\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(list_file), "-c", "copy", str(output_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink(missing_ok=True)
    return output_path


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
