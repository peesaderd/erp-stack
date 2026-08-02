"""Pipeline Step8 Compose Video — extracted from pipeline_affiliate.py."""
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


from prodia_client import ProdiaV2Client, ProdiaV2Error, ProdiaValidationError


def _convert_to_wav(audio_path: str) -> str:
    """Convert TTS audio to 16kHz mono PCM WAV for accurate Prodia Lip-sync."""
    if not audio_path or not os.path.exists(audio_path):
        return audio_path
    wav_path = str(Path(audio_path).parent / f"{Path(audio_path).stem}_16k.wav")
    try:
        import subprocess
        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            wav_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 500:
            logger.info(f"Converted audio to 16kHz WAV for Lip-sync: {wav_path}")
            return wav_path
    except Exception as e:
        logger.warning(f"Audio WAV conversion notice ({e}), using original file: {audio_path}")
    return audio_path


def generate_video(
    image_path: str,
    prompt: str,
    duration: int = 8,
    resolution: str = "720P",
    audio_path: Optional[str] = None,
    negative_prompt: Optional[str] = None,
) -> tuple:
    """
    Step 8: Generate video via Wan 2.7 Async API (shared ProdiaV2Client)
    """
    logger.info(f"Step 8/9: Generate video (Wan 2.7, {resolution})")
    logger.info(f"  Prompt: {prompt[:80]}...")

    # Read image bytes
    if image_path.startswith("http://") or image_path.startswith("https://"):
        resp = requests.get(image_path, timeout=30)
        resp.raise_for_status()
        image_data = resp.content
    else:
        with open(image_path, "rb") as f:
            image_data = f.read()

    # Convert audio to clean 16kHz WAV for Prodia Lip Sync
    audio_bytes = None
    if audio_path:
        valid_wav_path = _convert_to_wav(audio_path)
        logger.info(f"  Audio: {Path(valid_wav_path).stat().st_size} bytes (sending 16kHz WAV to Prodia for lip-sync)")
        with open(valid_wav_path, "rb") as f:
            audio_bytes = f.read()

    # ── Generate via shared client ──
    client = ProdiaV2Client(token=PRODIA_TOKEN())

    try:
        neg_p = negative_prompt or "no text, no watermark, blurry, distorted, extra limbs, bad face, deformed"
        result = client.generate_video(
            prompt=prompt,
            input_image=image_data,
            duration=duration,
            resolution=resolution,
            audio_bytes=audio_bytes,
            job_type="inference.wan2-7.img2vid.v1",
            negative_prompt=neg_p,
        )

        output_url = result.get("output_url", "")
        price = result.get("price", {})
        cost_video = float(price.get("dollars", 0))

        if not output_url:
            raise RuntimeError(f"No output URL in result: {result.get('result_raw', {})}")

        # Download the video (Prodia output needs auth)
        auth_headers = {"Authorization": f"Bearer {PRODIA_TOKEN()}"} if "prodia.com" in (output_url or "") else {}
        video_resp = requests.get(output_url, headers=auth_headers, timeout=60)
        video_resp.raise_for_status()

        result_path = TMP_DIR / f"img2vid_{uuid.uuid4().hex[:8]}.mp4"
        with open(result_path, "wb") as f:
            f.write(video_resp.content)

        file_size = result_path.stat().st_size
        logger.info(f"  Video OK ({file_size} bytes, {resolution}): {result_path}")
        logger.info(f"  Cost: ${cost_video:.4f}")
        # Verify that the generated video contains an audio stream for lip‑sync
        if not has_audio_track(str(result_path)):
            logger.error("Wan 2.7 returned video without audio track – lip sync failed")
            raise RuntimeError("Lip sync failure: generated video lacks audio track")

        return str(result_path), cost_video
    except Exception as e:
        logger.error(f"  Prodia Wan 2.7 Video generation failed: {e}")
        raise RuntimeError(f"Prodia Wan 2.7 Video generation failed: {e}")

def _generate_fallback_video_from_image(image_path: str, duration: int = 15) -> str:
    """Generate a high-quality 1080x1920 video with smooth zoompan from a still image via FFmpeg."""
    fallback_path = TMP_DIR / f"img2vid_fallback_{uuid.uuid4().hex[:8]}.mp4"
    logger.info(f"Generating FFmpeg video fallback from image: {image_path}")
    
    local_img = image_path
    if str(image_path).startswith("http://") or str(image_path).startswith("https://"):
        local_img = TMP_DIR / f"temp_img_{uuid.uuid4().hex[:8]}.png"
        r = requests.get(image_path, timeout=30)
        with open(local_img, "wb") as f:
            f.write(r.content)
            
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(local_img),
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='min(zoom+0.0015,1.2)':d={duration*25}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920",
        "-r", "25",
        str(fallback_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    logger.info(f"FFmpeg Video Fallback Created OK -> {fallback_path}")
    return str(fallback_path)

def has_audio_track(video_path: str) -> bool:
    """Check if video contains an audio stream using ffprobe.
    Returns False on any error.
    """
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return bool(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Failed to probe audio track for {video_path}: {e}")
        return False
def compose_video(
    video_paths: list,
    voice_path: Optional[str] = None,
    run_id: str = "",
    bgm_style: str = "chill_loft",
    target_duration: int = 12,
    voice_speed: float = 1.3,
) -> str:
    """
    Step 9: Compose final video (merge voice + BGM + concat scenes)

    Args:
        video_paths: list ของ video paths จาก Step 8
        voice_path: path ของ voice จาก Step 7 (None = ไม่มี voiceover)
        run_id: สำหรับสร้าง filename
        bgm_style: สไตล์เพลงพื้นหลัง
        voice_speed: ความเร็วเสียง 1.0=ปกติ 1.3=เร่งสปีด (default ASMR/Sale voice)

    Returns:
        str: path ของ final video
    """
    logger.info(f"Step 9/9: Compose (FFmpeg)")

    # Step 9a: Concat scenes (filter None, fallback gracefully)
    valid_paths = [vp for vp in video_paths if vp is not None]
    logger.info(f"  9a: {len(valid_paths)}/{len(video_paths)} valid scenes")

    if not valid_paths:
        raise RuntimeError("No valid videos to compose (all None)")

    concat_path = TMP_DIR / f"concat_{run_id}.mp4"
    if len(valid_paths) > 1:
        concat_videos(valid_paths, concat_path)
    else:
        shutil.copy2(valid_paths[0], concat_path)

    # Step 9b: Force-merge Gemini TTS voiceover audio into the video
    final_path = concat_path
    if voice_path and Path(voice_path).exists():
        logger.info(f"  9b: Merging TTS voiceover audio {voice_path} into final video")
        voiced_path = STORAGE_DIR / f"affiliate_{run_id}_voiced.mp4"
        cmd_voice = [
            "ffmpeg", "-y",
            "-i", str(concat_path),
            "-i", str(voice_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            str(voiced_path)
        ]
        try:
            subprocess.run(cmd_voice, check=True, capture_output=True, timeout=60)
            if voiced_path.exists() and voiced_path.stat().st_size > 1000:
                final_path = voiced_path
                logger.info(f"  9b: Voiceover merged successfully -> {final_path}")
        except Exception as ve:
            logger.error(f"  9b: Merging voiceover failed ({ve}), using concat video")
    else:
        final_path = concat_path


    # Step 9c: Add BGM
    if bgm_style:
        logger.info(f"  9c: Add BGM ({bgm_style})")
        bgm_filename = f"{bgm_style}.mp3" if not bgm_style.endswith((".mp3", ".wav")) else bgm_style
        bgm_path = STORAGE_DIR / "sounds" / bgm_filename

        if bgm_path.exists():
            bgm_output = STORAGE_DIR / f"affiliate_{run_id}_bgm.mp4"
            # Strategy: mix BGM with video audio. If video has no usable audio, just copy BGM
            try:
                probe_cmd = [
                    "ffprobe", "-v", "quiet",
                    "-select_streams", "a:0",
                    "-show_entries", "stream=duration",
                    "-of", "csv=p=0",
                    str(final_path)
                ]
                probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=5)
                audio_dur = float(probe_res.stdout.strip() or "0")
                safe_dur = audio_dur + 0.5 if audio_dur > 0 else 12
                logger.info(f"Audio duration: {audio_dur:.1f}s, using target: {safe_dur:.1f}s")
                cmd_mix = [
                    "ffmpeg", "-y",
                    "-i", str(final_path),
                    "-stream_loop", "-1",
                    "-i", str(bgm_path),
                    "-filter_complex",
                    "[1:a]volume=0.15[bg];[0:a][bg]amix=inputs=2:duration=first[out]",
                    "-map", "0:v",
                    "-map", "[out]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-t", str(safe_dur),
                    str(bgm_output),
                ]
                subprocess.run(cmd_mix, check=True, capture_output=True, timeout=60)
                logger.info(f"    BGM mixed")
                final_path = bgm_output
            except Exception as e:
                logger.warning(f"    BGM mix failed ({e}), trying BGM-only")
                # Fallback: just copy video + BGM as sole audio
                try:
                    cmd_bgm = [
                        "ffmpeg", "-y",
                        "-i", str(concat_path),  # use original video with audio
                        "-i", str(bgm_path),
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        "-shortest",
                        str(bgm_output),
                    ]
                    subprocess.run(cmd_bgm, check=True, capture_output=True, timeout=60)
                    logger.info(f"    BGM-only added")
                    final_path = bgm_output
                except Exception as e2:
                    logger.warning(f"    BGM-only also failed: {e2}")

    logger.info(f"  Final: {final_path}")
    return str(final_path)


