"""
TikTok UGC Studio — FFmpeg Composer
Audio/video composition, overlay, and sync using FFmpeg subprocess calls.
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("tiktok-ugc.composer")


def _check_ffmpeg():
    """Verify ffmpeg is available on PATH."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(
            "FFmpeg not found. Install it with: sudo apt install ffmpeg"
        ) from e


def compose_video(video_path: str, audio_path: str, output_path: str) -> str:
    """
    Overlay audio track onto a video file.
    Replaces any existing audio in the video with the provided audio.

    Args:
        video_path: Path to input video file
        audio_path: Path to input audio file (MP3, WAV, etc.)
        output_path: Path to save the composed output video

    Returns:
        Path to the composed output video

    Raises:
        FileNotFoundError: If input files don't exist
        RuntimeError: If FFmpeg processing fails
    """
    _check_ffmpeg()

    for p, label in [(video_path, "video"), (audio_path, "audio")]:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Input {label} file not found: {p}")

    # Create output directory
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",      # Copy video stream (no re-encode)
        "-c:a", "aac",       # Re-encode audio to AAC
        "-map", "0:v:0",     # Video from first input
        "-map", "1:a:0",     # Audio from second input
        "-shortest",         # Match shortest stream duration
        output_path,
    ]

    logger.info(f"Composing video: {os.path.basename(video_path)} + {os.path.basename(audio_path)}")
    _run_ffmpeg(cmd)

    file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    logger.info(f"Composed video saved: {output_path} ({file_size / 1024:.0f} KB)")

    return output_path


def add_sound_effects(
    video_path: str,
    sound_path: str,
    output_path: str,
    volume: float = 0.3,
    mix: bool = True,
) -> str:
    """
    Add background music or sound effects to a video.
    Mixes the sound track with the original audio at a configurable volume.

    Args:
        video_path: Path to input video file
        sound_path: Path to background music / SFX audio file
        output_path: Path to save output video
        volume: Volume ratio for the background sound (0.0–1.0, default 0.3)
        mix: If True, mix with original audio. If False, replace entirely.

    Returns:
        Path to the output video

    Raises:
        FileNotFoundError: If input files don't exist
        RuntimeError: If FFmpeg processing fails
    """
    _check_ffmpeg()

    for p, label in [(video_path, "video"), (sound_path, "sound")]:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Input {label} file not found: {p}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if mix:
        # Mix: keep original audio + add background at reduced volume
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-i", sound_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-filter_complex",
            f"[1:a]volume={volume}[bga];[0:a][bga]amix=inputs=2:duration=first[audio]",
            "-map", "0:v:0",
            "-map", "[audio]",
            "-shortest",
            output_path,
        ]
    else:
        # Replace: remove original audio, add background
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-i", sound_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path,
        ]

    logger.info(
        f"Adding sound effects: vol={volume} mix={mix} "
        f"→ {os.path.basename(output_path)}"
    )
    _run_ffmpeg(cmd)

    file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    logger.info(f"Sound effects video saved: {output_path} ({file_size / 1024:.0f} KB)")

    return output_path


def merge_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    lip_sync_offset: float = 0.0,
) -> str:
    """
    Merge audio with video with optional lip-sync offset adjustment.

    Useful for voice output: overlay the lip-synced audio onto the original
    video with a configurable offset (in seconds) to fine-tune sync.

    Args:
        video_path: Path to input video file
        audio_path: Path to input audio file (lip-synced audio)
        output_path: Path to save merged output video
        lip_sync_offset: Seconds to delay/advance audio (negative = earlier,
                         positive = later). Default 0.

    Returns:
        Path to the merged output video

    Raises:
        FileNotFoundError: If input files don't exist
        RuntimeError: If FFmpeg processing fails
    """
    _check_ffmpeg()

    for p, label in [(video_path, "video"), (audio_path, "audio")]:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Input {label} file not found: {p}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if abs(lip_sync_offset) < 0.01:
        # No offset needed — simple replace
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path,
        ]
    else:
        # Apply audio delay via adelay filter
        delay_ms = int(lip_sync_offset * 1000)
        # adelay accepts delay in ms per channel
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-af", f"adelay={delay_ms}|{delay_ms}",
            "-shortest",
            output_path,
        ]

    logger.info(
        f"Merging audio+video: offset={lip_sync_offset}s "
        f"→ {os.path.basename(output_path)}"
    )
    _run_ffmpeg(cmd)

    file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    logger.info(f"Merged video saved: {output_path} ({file_size / 1024:.0f} KB)")

    return output_path


def _run_ffmpeg(cmd: list):
    """
    Run an FFmpeg command with logging. Raises on failure.

    Args:
        cmd: FFmpeg command list (passed to subprocess)

    Raises:
        RuntimeError: If FFmpeg returns non-zero exit code
    """
    logger.debug(f"FFmpeg: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10-minute max per operation
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg process timed out (600s limit)")

    if result.returncode != 0:
        stderr = result.stderr[-2000:] if result.stderr else "No stderr"
        raise RuntimeError(
            f"FFmpeg failed (exit={result.returncode}): {stderr}"
        )
