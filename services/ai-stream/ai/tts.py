"""
Text-to-Speech — Edge-TTS (Microsoft, ฟรี, คุณภาพสูง)
ใช้เสียงภาษาไทย th-TH-PremwadeeNeural
"""
import os
import uuid
import json
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TTS_VOICE = os.getenv("TTS_VOICE", "th-TH-PremwadeeNeural")
TTS_LANG = os.getenv("TTS_LANG", "th")
AUDIO_DIR = Path("data/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Cache: avoid re-generating same text
_tts_cache: dict[str, str] = {}


async def generate_speech(text: str, voice: str = None) -> str:
    """Generate speech audio file, return path."""
    voice = voice or TTS_VOICE
    
    # Check cache
    cache_key = f"{voice}:{text}"
    if cache_key in _tts_cache:
        return _tts_cache[cache_key]
    
    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = str(AUDIO_DIR / filename)
    
    try:
        # edge-tts CLI (no Python import issues)
        proc = await asyncio_create_subprocess(
            "edge-tts",
            "--voice", voice,
            "--text", text,
            "--write-media", filepath,
        )
        await proc.wait()
        
        if Path(filepath).exists() and Path(filepath).stat().st_size > 0:
            _tts_cache[cache_key] = filepath
            return filepath
        else:
            raise Exception("TTS output empty")
    except Exception as e:
        print(f"[TTS] Error: {e}")
        # Fallback: create a placeholder
        return ""


import asyncio


async def asyncio_create_subprocess(*args):
    """Helper to create subprocess."""
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return process


async def list_voices(lang: str = "th") -> list:
    """List available Thai voices."""
    proc = await asyncio_create_subprocess(
        "edge-tts", "--list-voices"
    )
    stdout, _ = await proc.communicate()
    voices = []
    for line in stdout.decode().split("\n"):
        if lang in line.lower():
            parts = line.strip().split()
            if parts:
                voices.append(parts[0])
    return voices
