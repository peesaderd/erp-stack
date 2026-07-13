"""Gemini 3.1 Flash TTS Preview — unified TTS for all pipelines.
Fixes:
  - Gemini returns raw PCM (audio/l16) → converts to proper .wav
  - Validates audio data isn't null bytes (transient failure guard)
  - Uses correct extension based on MIME type
"""
import os
import re
import json
import base64
import struct
import requests
import tempfile
import logging
from pathlib import Path
from typing import Optional

import sys
_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))
from shared_config import GEMINI_API_KEY

logger = logging.getLogger("tiktok-ugc.gemini_tts")

MODEL = "gemini-3.1-flash-tts-preview"
VOICE = "Aoede"

# ─── WAV header writer ─────────────────────────────────────────────────────

def _raw_pcm_to_wav(data: bytes, sample_rate: int = 24000,
                     channels: int = 1, bits_per_sample: int = 16) -> bytes:
    """Wrap raw PCM data in a proper WAV container (RIFF header)."""
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    data_size = len(data)

    # fmt chunk (16 bytes for PCM)
    fmt_chunk = struct.pack('<4sI HHIIHH',
        b'fmt ', 16,           # chunk id + size
        1,                     # audio format (1 = PCM)
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
    )

    # data chunk
    data_chunk = struct.pack('<4sI', b'data', data_size) + data

    # RIFF header
    riff_size = 4 + (8 + len(fmt_chunk)) + (8 + len(data_chunk))
    riff_header = struct.pack('<4sI', b'RIFF', riff_size) + b'WAVE'

    return riff_header + fmt_chunk + data_chunk


# ─── MIME parser ───────────────────────────────────────────────────────────

def _parse_mime(mime_str: str) -> dict:
    """Parse MIME type like 'audio/l16; rate=24000; channels=1'."""
    parts = [p.strip() for p in mime_str.split(';')]
    info = {
        'type': parts[0] if parts else 'audio/l16',
        'rate': 24000,
        'channels': 1,
    }
    for p in parts[1:]:
        m = re.match(r'(\w+)=(\w+)', p)
        if m:
            key = m.group(1).lower()
            if key == 'rate':
                info['rate'] = int(m.group(2))
            elif key == 'channels':
                info['channels'] = int(m.group(2))
    return info


# ─── Audio validation ──────────────────────────────────────────────────────

def _validate_audio(data: bytes, label: str = "audio") -> bool:
    """Ensure the audio data isn't all zeros or trivially small."""
    if len(data) < 100:
        logger.warning(f"{label}: too small ({len(data)} bytes)")
        return False

    # Check for all-null / silence
    non_zero = sum(1 for b in data if b != 0)
    ratio = non_zero / len(data)
    if ratio < 0.001:
        logger.warning(f"{label}: {non_zero}/{len(data)} non-zero bytes "
                       f"(ratio={ratio:.6f}) — likely empty/silent")
        return False

    return True


# ─── Main TTS function ─────────────────────────────────────────────────────

def gemini_text_to_speech(text: str, output_path: Optional[str] = None,
                          voice: str = VOICE) -> str:
    """
    Generate speech from text using Gemini 3.1 Flash TTS Preview.

    Gemini returns raw PCM 16-bit LE audio wrapped in a WAV container.
    Validates the audio data to catch transient empty responses.

    Args:
        text: Thai/English text to synthesize
        output_path: Where to save the WAV file (default: temp file)
        voice: Gemini voice name (Aoede, Wise_Woman, Fenrir, etc.)

    Returns:
        Path to the saved WAV file

    Raises:
        ValueError: If API key is missing
        RuntimeError: On API error, empty audio, or network failure
    """
    api_key = GEMINI_API_KEY()
    if not api_key:
        raise ValueError("GEMINI_API_KEY not configured (via shared_config)")

    url = (f"https://generativelanguage.googleapis.com/v1beta/"
           f"models/{MODEL}:generateContent?key={api_key}")

    payload = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice}
                }
            },
        },
    }

    logger.info(f"Gemini TTS: {len(text)} chars, voice={voice}")
    logger.debug(f"Text: {text[:100]}...")

    try:
        resp = requests.post(url, json=payload, timeout=120)
    except requests.exceptions.Timeout:
        raise RuntimeError("Gemini TTS timed out (120s)")

    if resp.status_code != 200:
        raise RuntimeError(
            f"Gemini TTS error {resp.status_code}: {resp.text[:300]}"
        )

    data = resp.json()

    # Extract audio from response
    audio_data = None
    mime_info = {'type': 'audio/l16', 'rate': 24000, 'channels': 1}

    for p in (data.get("candidates", [{}])[0]
              .get("content", {}).get("parts", [])):
        if "inlineData" in p:
            try:
                raw = base64.b64decode(p["inlineData"]["data"])
            except Exception as e:
                raise RuntimeError(
                    f"Failed to decode base64 audio: {e}"
                )

            # Parse MIME for PCM params
            mime_str = p["inlineData"].get("mimeType", "audio/l16")
            mime_info = _parse_mime(mime_str)

            logger.info(f"Gemini returned: {mime_str}, "
                        f"{len(raw)} bytes decoded")

            # Validate
            if not _validate_audio(raw, "gemini_tts"):
                raise RuntimeError(
                    "Gemini returned empty/silent audio data "
                    f"({len(raw)} bytes, {mime_str})"
                )

            audio_data = raw
            break

    if audio_data is None:
        raise RuntimeError("No audio data in Gemini TTS response")

    # Convert raw PCM → WAV
    mime_type = mime_info['type']
    if mime_type in ('audio/l16', 'audio/L16', 'audio/x-pcm',
                     'audio/pcm', 'audio/raw'):
        logger.info(f"Converting raw PCM to WAV "
                    f"({mime_info['rate']}Hz, {mime_info['channels']}ch)")
        audio_data = _raw_pcm_to_wav(
            audio_data,
            sample_rate=mime_info['rate'],
            channels=mime_info['channels'],
        )
        suffix = ".wav"
    elif mime_type == 'audio/mpeg':
        suffix = ".mp3"
    elif mime_type == 'audio/wav' or mime_type == 'audio/x-wav':
        suffix = ".wav"
    elif 'ogg' in mime_type:
        suffix = ".ogg"
    else:
        suffix = ".wav"
        logger.warning(f"Unknown MIME '{mime_type}', saving as WAV")

    # Determine output path
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
    else:
        # Ensure correct extension
        out_path = Path(output_path)
        expected = suffix
        if out_path.suffix != expected:
            output_path = str(out_path.with_suffix(expected))
            logger.info(f"Fixed extension: {out_path.name} -> "
                        f"{Path(output_path).name}")

    # Write audio file
    with open(output_path, "wb") as f:
        f.write(audio_data)

    file_size = os.path.getsize(output_path)
    logger.info(f"TTS saved: {output_path} ({file_size:,} bytes)")

    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test = gemini_text_to_speech(
        "สวัสดีครับ ทดสอบระบบเสียง Gemini TTS",
        "/tmp/gemini_tts_test_fixed.wav",
    )
    print("Test saved:", test)

    # Verify with ffprobe
    import subprocess
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_streams", test],
                       capture_output=True, text=True)
    print(r.stdout[:300])
