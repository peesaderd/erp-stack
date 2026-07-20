"""Video performance tracker — fetches and stores performance data."""
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger("monitor.tracker")

STORAGE_DIR = Path(__file__).parent.parent / "storage"
PUBLISHED_LOG = STORAGE_DIR / "published.json"
ANALYTICS_LOG = STORAGE_DIR / "analytics.json"


def _ensure_storage():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _scan_generated_videos() -> List[Dict]:
    """Scan videos directory for generated files not yet in published log."""
    generated = []
    videos_dir = STORAGE_DIR / "videos"
    if not videos_dir.exists():
        return generated
    for vf in sorted(videos_dir.glob("*.mp4")):
        generated.append({
            "id": f"gen_{vf.stem}",
            "caption": vf.stem,
            "category": "",
            "hook_type": "",
            "views": 0,
            "likes": 0,
            "shares": 0,
            "comments": 0,
            "post_hour": None,
            "posted_at": "",
            "account_id": "",
            "status": "pending",
            "file": f"videos/{vf.name}",
        })
    return generated


async def get_published_videos(account_id: str = "", limit: int = 50) -> List[Dict]:
    """Fetch published and generated videos."""
    _ensure_storage()

    entries = []
    if PUBLISHED_LOG.exists():
        try:
            with open(PUBLISHED_LOG) as f:
                entries = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read published log: {e}")

    # Merge with generated videos from filesystem
    seen = {e.get("caption", "") for e in entries}
    generated = _scan_generated_videos()
    for g in generated:
        if g["caption"] not in seen:
            entries.append(g)

    if account_id:
        entries = [e for e in entries if e.get("account_id") == account_id]

    return entries[-limit:]


async def record_analytics(entry: dict):
    """Record analytics data for a video."""
    _ensure_storage()
    entries = []
    if ANALYTICS_LOG.exists():
        try:
            with open(ANALYTICS_LOG) as f:
                entries = json.load(f)
        except (json.JSONDecodeError, Exception):
            entries = []

    entry["recorded_at"] = datetime.now(timezone.utc).isoformat()
    entries.append(entry)

    # Keep last 1000 entries
    entries = entries[-1000:]

    with open(ANALYTICS_LOG, "w") as f:
        json.dump(entries, f, indent=2, default=str)


async def get_video_analytics(
    account_id: str = "",
    hours: int = 24,
    limit: int = 100,
) -> List[Dict]:
    """Get analytics for videos published in the last N hours."""
    _ensure_storage()
    if not ANALYTICS_LOG.exists():
        return []

    try:
        with open(ANALYTICS_LOG) as f:
            entries = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read analytics log: {e}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    filtered = []
    for e in entries:
        try:
            ts = e.get("recorded_at", "")
            if ts:
                t = datetime.fromisoformat(ts)
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                if t < cutoff:
                    continue
        except (ValueError, TypeError):
            pass
        if account_id and e.get("account_id") != account_id:
            continue
        filtered.append(e)

    return filtered[-limit:]


async def compute_performance_summary(
    account_id: str = "",
    hours: int = 168,
) -> Dict:
    """Compute performance summary over a time window."""
    videos = await get_video_analytics(account_id=account_id, hours=hours)

    if not videos:
        return {
            "total_videos": 0,
            "avg_views": 0,
            "avg_likes": 0,
            "avg_shares": 0,
            "avg_comments": 0,
            "total_views": 0,
            "best_video": None,
            "worst_video": None,
        }

    total = len(videos)
    total_views = sum(v.get("views", 0) for v in videos)
    total_likes = sum(v.get("likes", 0) for v in videos)
    total_shares = sum(v.get("shares", 0) for v in videos)
    total_comments = sum(v.get("comments", 0) for v in videos)

    best = max(videos, key=lambda v: v.get("views", 0))
    worst = min(videos, key=lambda v: v.get("views", 0))

    return {
        "total_videos": total,
        "avg_views": round(total_views / total, 1) if total else 0,
        "avg_likes": round(total_likes / total, 1) if total else 0,
        "avg_shares": round(total_shares / total, 1) if total else 0,
        "avg_comments": round(total_comments / total, 1) if total else 0,
        "total_views": total_views,
        "total_likes": total_likes,
        "best_video": {
            "caption": best.get("caption", "")[:80],
            "views": best.get("views", 0),
            "likes": best.get("likes", 0),
            "posted_at": best.get("posted_at", ""),
        },
        "worst_video": {
            "caption": worst.get("caption", "")[:80],
            "views": worst.get("views", 0),
            "likes": worst.get("likes", 0),
            "posted_at": worst.get("posted_at", ""),
        },
        "window_hours": hours,
    }
