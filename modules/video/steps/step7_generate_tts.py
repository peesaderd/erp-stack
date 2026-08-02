"""Pipeline Step7 Generate Tts — extracted from pipeline_affiliate.py."""
import os, sys, json, time, uuid, logging, subprocess, shutil, re
from pathlib import Path
from typing import Optional, List, Dict, Any
import requests

# Add parent paths
_erp_stack = Path(__file__).parent.parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from shared_config import PRODIA_TOKEN, GEMINI_API_KEY
_ugc_client_dir = os.path.join(str(_erp_stack), "prompt-builder-service")
if _ugc_client_dir not in sys.path:
    sys.path.insert(0, _ugc_client_dir)
from ugc_schema_client import get_default_style, get_style_config, validate_ugc_style, is_valid_style

from .common import (
    logger, STORAGE_DIR, TMP_DIR, IMAGE_GEN_URL, PROMPT_BUILDER_URL,
    download_file, concat_videos, get_bgm_path,
)


def generate_voice(
    text: str,
    voice: str = "Aoede",
    run_id: str = "",
) -> str:
    """Step 7: Generate Thai voice via Gemini TTS ONLY (EdgeTTS removed per project policy)."""
    logger.info(f"Step 7/9: TTS (Gemini TTS)")
    logger.info(f"  Voice: {voice}")
    logger.info(f"  Text: {text[:50]}...")

    output_path = str(TMP_DIR / f"voice_{run_id}.mp3")

    # GEMINI TTS ONLY — EdgeTTS removed (ไม่ใช้ Edge TTS เราใช้ Gemini TTS เท่านั้น)
    try:
        from gemini_tts import gemini_text_to_speech
        tts_path = gemini_text_to_speech(text, output_path=output_path, voice=voice)
        if tts_path and Path(tts_path).exists():
            logger.info(f"  Gemini TTS OK: {tts_path}")
            return tts_path
    except Exception as e:
        logger.error(f"Gemini TTS failed: {e}")

    return ""

