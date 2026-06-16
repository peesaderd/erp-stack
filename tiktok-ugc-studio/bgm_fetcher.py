"""
BGM Fetcher — ดาวน์โหลดเพลงฟรีจาก Mixkit (royalty-free) อัตโนมัติ
===============================================================
- ดึง track IDs จาก Mixkit CDN ตรงๆ (assets.mixkit.co/music/{id}/{id}.mp3)
- หลาย track ต่อ style เพื่อความหลากหลาย
- Fallback ถ้า download ไม่ได้
"""

import logging
import random
from pathlib import Path

import requests

logger = logging.getLogger("tiktok-ugc.bgm_fetcher")

# Track IDs ที่รู้จักและใช้งานได้ (Mixkit Free Stock Music)
# แต่ละ style มีหลาย track เผื่อ random
STYLE_TRACKS = {
    "chill_loft": [494, 16, 25, 256, 1077, 510],
    "informative_jazz": [493, 39, 24, 752, 644, 89],
    "energetic_edm": [371, 113, 124, 181, 157, 629],
    "upbeat_pop": [644, 528, 652, 820],
    "luxury_jazz": [493, 39, 24, 752],
    "asmr": [16, 494, 510, 1077],
}

# Map style → output filename (ตรงกับ pipeline bgm_map)
STYLE_FILENAME = {
    "chill_loft": "bg_chill.mp3",
    "informative_jazz": "bg_jazz.mp3",
    "energetic_edm": "bg_edm.mp3",
    "upbeat_pop": "bg_upbeat.mp3",
    "luxury_jazz": "bg_jazz.mp3",
    "asmr": "bg_ambient.mp3",
}

# Fallback: ถ้า all track IDs ล้มหมด — ใช้ track 494 (chill)
FALLBACK_TRACK_ID = 494


def fetch_bgm(style: str, bgm_dir: Path = None) -> Path:
    """ดาวน์โหลด BGM ตาม style ถ้ายังไม่มีใน cache
    
    Args:
        style: ชื่อ style (chill_loft, informative_jazz, ฯลฯ)
        bgm_dir: โฟลเดอร์ที่เก็บไฟล์ BGM (default: bgm/ ข้าง pipeline)
    
    Returns:
        Path ไปยังไฟล์ mp3
    """
    if bgm_dir is None:
        bgm_dir = Path(__file__).parent / "bgm"
    bgm_dir.mkdir(parents=True, exist_ok=True)

    filename = STYLE_FILENAME.get(style, "bg_chill.mp3")
    dest = bgm_dir / filename

    # ถ้ามีไฟล์อยู่แล้ว → return
    if dest.exists() and dest.stat().st_size > 100000:
        logger.info(f"  BGM {filename} already cached ({dest.stat().st_size} bytes)")
        return dest

    # ลอง track IDs ตาม style
    track_ids = STYLE_TRACKS.get(style, [FALLBACK_TRACK_ID])
    # Random สลับลำดับ
    random.shuffle(track_ids)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://mixkit.co/",
    }

    for track_id in track_ids:
        url = f"https://assets.mixkit.co/music/{track_id}/{track_id}.mp3"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 100000:
                dest.write_bytes(resp.content)
                logger.info(f"  BGM downloaded: track {track_id} → {filename} ({len(resp.content)} bytes)")
                return dest
            else:
                logger.warning(f"  BGM track {track_id}: status={resp.status_code}, size={len(resp.content) if resp.content else 0}")
        except Exception as e:
            logger.warning(f"  BGM track {track_id}: {e}")
            continue

    # Fallback: ถ้าทุก track ล้ม → ใช้ FALLBACK_TRACK_ID
    logger.warning(f"  All tracks failed for style={style}, trying fallback {FALLBACK_TRACK_ID}")
    url = f"https://assets.mixkit.co/music/{FALLBACK_TRACK_ID}/{FALLBACK_TRACK_ID}.mp3"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 100000:
            dest.write_bytes(resp.content)
            logger.info(f"  BGM fallback: track {FALLBACK_TRACK_ID} → {filename}")
            return dest
    except Exception:
        pass

    # สุดท้าย: return fallback path (อาจไม่มีไฟล์ — pipeline จะ check เอง)
    logger.error(f"  BGM download FAILED for style={style}")
    return dest
