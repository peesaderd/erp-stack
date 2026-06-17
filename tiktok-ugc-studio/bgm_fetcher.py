"""
BGM Fetcher — ดาวน์โหลดเพลงฟรีจาก Mixkit + Pixabay (royalty-free) อัตโนมัติ
====================================================================
- ดึง track IDs จาก Mixkit CDN ตรงๆ (assets.mixkit.co/music/{id}/{id}.mp3)
- Fallback เมื่อ Mixkit ล้ม → Pixabay Audio API
- หลาย track ต่อ style เพื่อ random ความหลากหลาย
- Random track: ค่อยๆ สะสมไฟล์ bg_{style}_01, _02, ... เมื่อเรียกซ้ำๆ
"""

import logging
import random
import requests
from pathlib import Path

logger = logging.getLogger("tiktok-ugc.bgm_fetcher")

# ─── Pixabay API ─────────────────────────────────────────────────────────
PIXABAY_AUDIO_KEY = "49993674-1e89f87be1c5601323aacb5e7"
PIXABAY_API_URL = "https://pixabay.com/api/audio/"

# ─── Mixkit Track IDs (verified working) ──────────────────────────────────
STYLE_TRACKS = {
    "chill_loft":        [494, 16, 25, 256, 1077, 510, 1308, 935, 1276, 1435],
    "informative_jazz":  [493, 39, 24, 752, 644, 89, 830, 1061, 1453, 1638],
    "energetic_edm":     [371, 113, 124, 181, 157, 629, 889, 1204, 1571, 1699],
    "upbeat_pop":        [644, 528, 652, 820, 1092, 1401, 1621, 1772],
    "luxury_jazz":       [493, 39, 24, 752, 1386, 1503, 1685],
    "asmr":              [16, 494, 510, 1077, 1259, 1347, 1482, 1711],
}

STYLE_FILENAME = {
    "chill_loft":       "bg_chill.mp3",
    "informative_jazz": "bg_jazz.mp3",
    "energetic_edm":    "bg_edm.mp3",
    "upbeat_pop":       "bg_upbeat.mp3",
    "luxury_jazz":      "bg_jazz.mp3",
    "asmr":             "bg_ambient.mp3",
}

# Pixabay query keywords per style (tried in random order on fallback)
STYLE_PIXABAY_QUERIES = {
    "chill_loft":       ["chill", "lo-fi", "relaxing", "ambient", "soft"],
    "informative_jazz": ["jazz", "corporate background", "vlog", "ukulele", "inspirational"],
    "energetic_edm":    ["electronic", "energetic", "dance", "beat", "game"],
    "upbeat_pop":       ["upbeat", "pop", "happy", "summer", "positive"],
    "luxury_jazz":      ["jazz", "elegant", "piano", "classical", "luxury"],
    "asmr":             ["ambient", "nature", "calm", "meditation", "soft"],
}

FALLBACK_TRACK_ID = 494

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://mixkit.co/",
}


def _get_dest_path(bgm_dir: Path, style: str, index: int = None) -> Path:
    """Get destination path. If index is given, use bg_{style}_{index:02d}.mp3."""
    base = STYLE_FILENAME.get(style, "bg_chill.mp3")
    if index is not None:
        stem = base.replace(".mp3", "")
        return bgm_dir / f"{stem}_{index:02d}.mp3"
    return bgm_dir / base


def _try_mixkit(track_id: int, dest: Path) -> bool:
    """Try downloading a single Mixkit track. Returns True on success."""
    url = f"https://assets.mixkit.co/music/{track_id}/{track_id}.mp3"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200 and len(resp.content) > 100000:
            dest.write_bytes(resp.content)
            logger.info(f"  ✓ Mixkit track {track_id} → {dest.name} ({len(resp.content)} bytes)")
            return True
        logger.warning(f"  Mixkit track {track_id}: status={resp.status_code}, size={len(resp.content) if resp.content else 0}")
    except Exception as e:
        logger.warning(f"  Mixkit track {track_id}: {e}")
    return False


def _try_pixabay(style: str, dest: Path) -> bool:
    """Fallback: try Pixabay audio API. Returns True on success."""
    queries = STYLE_PIXABAY_QUERIES.get(style, ["background"])
    shuffled = random.sample(queries, len(queries))

    for query in shuffled:
        url = f"{PIXABAY_API_URL}?key={PIXABAY_AUDIO_KEY}&q={query}&per_page=10"
        try:
            resp = requests.get(url, timeout=15)
            data = resp.json()
            hits = data.get("hits", [])
            if not hits:
                logger.warning(f"  Pixabay '{query}': no hits")
                continue

            # Try first few hits
            for hit in hits[:3]:
                audio_url = hit.get("url") or hit.get("preview_url") or ""
                if not audio_url:
                    continue
                audio_resp = requests.get(audio_url, timeout=30)
                if audio_resp.status_code == 200 and len(audio_resp.content) > 100000:
                    dest.write_bytes(audio_resp.content)
                    logger.info(f"  ✓ Pixabay '{query}' → {dest.name} ({len(audio_resp.content)} bytes)")
                    return True
                logger.warning(f"  Pixabay '{query}' hit: status={audio_resp.status_code}, size={len(audio_resp.content) if audio_resp.content else 0}")
        except Exception as e:
            logger.warning(f"  Pixabay '{query}': {e}")
            continue

    return False


def fetch_bgm(style: str, bgm_dir: Path = None, random_track: bool = True) -> Path:
    """ดาวน์โหลด BGM ตาม style ถ้ายังไม่มีใน cache

    Args:
        style: ชื่อ style (chill_loft, informative_jazz, ฯลฯ)
        bgm_dir: โฟลเดอร์ที่เก็บไฟล์ BGM (default: bgm/ ข้าง pipeline)
        random_track: ถ้า True → สุ่ม track index (สะสมหลายไฟล์),
                      ถ้า False → ใช้ชื่อไฟล์เดียว (overwrite)

    Returns:
        Path ไปยังไฟล์ mp3
    """
    if bgm_dir is None:
        bgm_dir = Path(__file__).parent / "bgm"
    bgm_dir.mkdir(parents=True, exist_ok=True)

    base_filename = STYLE_FILENAME.get(style, "bg_chill.mp3")
    track_ids = STYLE_TRACKS.get(style, [FALLBACK_TRACK_ID])

    # ── Random track index mode ──────────────────────────────────────────
    if random_track:
        # Find next available index (keep growing the library)
        stem = base_filename.replace(".mp3", "")
        existing = sorted(bgm_dir.glob(f"{stem}_*.mp3"))
        # If we have < 5 files, try a new track; otherwise pick random from existing
        if len(existing) >= 5:
            chosen = random.choice(existing)
            logger.info(f"  BGM random track: {chosen.name}")
            return chosen

        # Try downloading a new track with next index
        next_idx = len(existing) + 1
        dest = _get_dest_path(bgm_dir, style, next_idx)
        if dest.exists() and dest.stat().st_size > 100000:
            return dest

        # Try Mixkit tracks (shuffled)
        shuffled = random.sample(track_ids, len(track_ids))
        for track_id in shuffled:
            if _try_mixkit(track_id, dest):
                return dest

        # Fallback: Pixabay
        if _try_pixabay(style, dest):
            return dest

        # Ultimate fallback: return whatever path (even if missing)
        logger.error(f"  BGM download ALL FAILED for style={style}")
        return dest

    # ── Single file mode (original behavior) ─────────────────────────────
    dest = bgm_dir / base_filename
    if dest.exists() and dest.stat().st_size > 100000:
        logger.info(f"  BGM {base_filename} already cached ({dest.stat().st_size} bytes)")
        return dest

    # Try Mixkit (shuffled)
    shuffled = random.sample(track_ids, len(track_ids))
    for track_id in shuffled:
        if _try_mixkit(track_id, dest):
            return dest

    # Fallback: Pixabay
    if _try_pixabay(style, dest):
        return dest

    # Ultimate fallback: try single fallback ID
    logger.warning(f"  All sources failed for style={style}, trying fallback {FALLBACK_TRACK_ID}")
    if _try_mixkit(FALLBACK_TRACK_ID, dest):
        return dest

    logger.error(f"  BGM download FAILED for style={style}")
    return dest
