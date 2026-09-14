"""FFmpeg compose & helpers (Phase C split, move-only)."""
from ._shared import (  # noqa: F401
    os, re, sys, json, time, uuid, logging, random, subprocess, shutil, asyncio,
    Path, Optional, List, Dict, Any, requests,
    PRODIA_TOKEN, GEMINI_API_KEY, logger,
    IMAGE_GEN_URL, PROMPT_BUILDER_URL, STORAGE_DIR, TMP_DIR,
    get_default_style, get_style_config, validate_ugc_style, is_valid_style,
)

def get_bgm_path(bgm_style: str) -> Path:
    """Helper to resolve BGM path from style name.

    The actual BGM mp3 files live in the TUS studio dir (tiktok-ugc-studio/bgm),
    NOT in modules/video/storage/sounds (which is empty). Map styles to the real
    filenames that exist there.
    """
    bgm_map = {
        "chill_loft": "kontraa_water.mp3",   # no bg_chill.mp3 — reuse upbeat_02
        "informative_jazz": "bg_jazz.mp3",
        "energetic_edm": "bg_edm.mp3",
        "upbeat_pop": "kontraa_water.mp3",
        "luxury_jazz": "bg_jazz.mp3",
        "asmr": "kontraa_water.mp3",          # no bg_ambient.mp3 — fallback
    }
    bgm_filename = bgm_map.get(bgm_style, "kontraa_water.mp3")
    # BGM lives in the TUS studio dir: erp-stack/tiktok-ugc-studio/bgm
    # (pipeline_affiliate.py is at erp-stack/modules/video/ -> up 3 = erp-stack)
    repo_root = Path(__file__).resolve().parent.parent.parent
    tus_studio_bgm = repo_root / "tiktok-ugc-studio" / "bgm"
    return tus_studio_bgm / bgm_filename

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
            f.write(f"file '{Path(vp).absolute()}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(list_file), "-c", "copy", str(output_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    list_file.unlink(missing_ok=True)
    return output_path

def compose_video(
    video_paths: list,
    voice_path: Optional[str] = None,
    run_id: str = "",
    bgm_style: str = "chill_loft",
    target_duration: int = 0,
    voice_speed: float = 1.0,
) -> str:
    """
    Step 9: Compose final video (merge voice + BGM + concat scenes)

    Args:
---
# ─── Main TTS function ─────────────────────────────────────────────────────
        video_paths: list ของ video paths จาก Step 8
        voice_path: path ของ voice จาก Step 7 (None = ไม่มี voiceover)
        run_id: สำหรับสร้าง filename
        bgm_style: สไตล์เพลงพื้นหลัง
        voice_speed: ความเร็วเสียง 1.0=ปกติ (TTS speed จาก speaking_rate 1.2 แล้ว อย่าเร่งซ้ำ)

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
    
    # Save raw concatenated video (no audio) for user download
    raw_path = STORAGE_DIR / f"affiliate_{run_id}_raw.mp4"
    shutil.copy2(concat_path, raw_path)
    logger.info(f"  9a: Raw video saved -> {raw_path}")

    # Step 9a.5: If video is shorter than target_duration, loop it to fill full duration
    if target_duration > 0:
        # Get actual duration of concat video
        try:
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(concat_path)
            ]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=False)
            actual_duration = float(probe_result.stdout.strip()) if probe_result.stdout.strip() else 0
        except Exception:
            actual_duration = 0

        if actual_duration > 0 and actual_duration < target_duration - 1:
            logger.info(f"  9a.5: Video is {actual_duration:.1f}s, looping to {target_duration}s")
            looped_path = TMP_DIR / f"looped_{run_id}.mp4"
            # Calculate how many loops needed, with slight overlap for smoothness
            loop_count = int(target_duration / actual_duration) + 1
            try:
                cmd_loop = [
                    "ffmpeg", "-y",
                    "-stream_loop", str(loop_count),
                    "-i", str(concat_path),
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-t", str(target_duration),
                    "-pix_fmt", "yuv420p",
                    str(looped_path)
                ]
                subprocess.run(cmd_loop, check=True, capture_output=True, timeout=120)
                if looped_path.exists() and looped_path.stat().st_size > 1000:
                    shutil.copy2(looped_path, concat_path)
                    logger.info(f"  9a.5: Looped video saved -> {concat_path}")
            except Exception as e:
                logger.warning(f"  9a.5: Loop failed ({e}), using original concat")

    # Step 9b: REMOVED — Gemini TTS voiceover stripped from TUS (owner 2026-08-24).
    final_path = concat_path


    # Step 9c: Add BGM
    if bgm_style:
        logger.info(f"  9c: Add BGM ({bgm_style})")
        # Resolve the real BGM file via get_bgm_path() (lives in tiktok-ugc-studio/bgm)
        bgm_path = get_bgm_path(bgm_style)
        if not bgm_path.exists():
            logger.warning(f"    BGM file not found: {bgm_path}, trying sibling names")
            bgm_filename = f"{bgm_style}.mp3" if not bgm_style.endswith((".mp3", ".wav")) else bgm_style
            bgm_path = STORAGE_DIR / "sounds" / bgm_filename

        if bgm_path.exists():
            bgm_output = STORAGE_DIR / f"affiliate_{run_id}_bgm.mp4"
            # Strategy: mix BGM under the narration with SIDECHAIN DUCKING (owner 2026-09-09
            # 16:3x — boss: "เสียงพากย์ซ้อน"). Root: the narration (Wan voice mode A, embedded in
            # video audio) is fully clean/single in the raw; the perceived "doubled/layered voice"
            # came from the BGM bed staying at full level UNDER/OVER the whole narration with no
            # ducking, so voiced/sustained music overlapped the Thai voice. Fix: BGM volume drops
            # sharply the moment the narration speaks (sidechaincompress) and only returns in
            # pauses/tail, so voice never overlaps music → clean single narration.
            try:
                # 🔴 FIX (owner 2026-09-10 11:39): "มีแทรกหลังคำว่า เชื่อมเร็ว" — ต้นตอ =
                # BGM (kontraa_water, speech-band ~-25dB) โผล่กลับมาใน "ช่องว่างระหว่างวลี"
                # เพราะ volume=0.5 สูงไป + release=650ms สั้นไป → จังหวะที่บทพูดหยุดพักหายใจ
                # ระหว่างวลี ดนตรีดีดกลับดัง → ฟังเป็น "เสียงแทรก". แก้: ลด BGM เป็น 0.18
                # (ดนตรีเป็นแค่เบด ไม่แข่งกับเสียงพูด) + ducking หนักขึ้น (threshold สูงขึ้น,
                # ratio สูง, release ยาว 1200ms ให้ดนตรีค้างลงนานระหว่างวลี ไม่งั้นมันเด้งกลับ)
                cmd_mix = [
                    "ffmpeg", "-y",
                    "-i", str(final_path),
                    "-stream_loop", "-1",
                    "-i", str(bgm_path),
                    "-filter_complex",
                    "[0:a]apad=pad_dur=20[va];"
                    "[1:a]volume=0.18[bg];"   # BGM as a soft bed only — never compete with narration
                    "[va]asplit=2[voice][side];"
                    "[bg][side]sidechaincompress=threshold=0.06:ratio=20:attack=20:release=1200[duck];"
                    "[voice][duck]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[out]",
                    "-map", "0:v",
                    "-map", "[out]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-t", str(target_duration),
                    str(bgm_output),
                ]
                subprocess.run(cmd_mix, check=True, capture_output=True, timeout=90)
                logger.info(f"    BGM mixed (sidechain ducked under narration)")
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
                        "-t", str(target_duration),
                        str(bgm_output),
                    ]
                    subprocess.run(cmd_bgm, check=True, capture_output=True, timeout=60)
                    logger.info(f"    BGM-only added")
                    final_path = bgm_output
                except Exception as e2:
                    logger.warning(f"    BGM-only also failed: {e2}")

    logger.info(f"  Final: {final_path}")
    return str(final_path), str(raw_path)

