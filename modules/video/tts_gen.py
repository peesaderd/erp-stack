"""
TikTok UGC Studio — gTTS Text-to-Speech Wrapper
"""

import os
import uuid
import logging
from pathlib import Path

logger = logging.getLogger("tiktok-ugc.tts_gen")


def text_to_speech(text: str, lang: str = "th", slow: bool = False, output_path: str = None) -> str:
    """
    Convert text to speech using gTTS and save as MP3.

    Args:
        text: Text to convert to speech
        lang: Language code (default "th" for Thai)
        output_path: Path to save MP3 file. If None, generates a temp path.

    Returns:
        Path to the saved MP3 file

    Raises:
        RuntimeError: If gTTS is not installed or network errors occur
    """
    try:
        from gtts import gTTS
    except ImportError:
        raise RuntimeError(
            "gTTS is not installed. Run: pip install gTTS"
        )

    if not text or not text.strip():
        raise ValueError("Text cannot be empty")

    if output_path is None:
        storage_dir = Path(__file__).parent / "storage" / "tts"
        storage_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(storage_dir / f"tts_{uuid.uuid4().hex[:8]}.mp3")

    try:
        tts = gTTS(text=text, lang=lang, slow=slow)
        tts.save(output_path)
        logger.info(f"TTS saved to {output_path} (lang={lang}, chars={len(text)})")
        return output_path
    except Exception as e:
        error_msg = f"gTTS failed: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
