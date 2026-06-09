"""
Scout Targets — competitor account tracking & analysis.

Manages target TikTok accounts, their clips, and clone generation.
"""

import json
import os
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict

logger = logging.getLogger("scout.targets")

DB_PATH = Path(__file__).parent.parent / "storage" / "scout_targets.db"

def _get_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            niche TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            follower_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS target_clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER NOT NULL,
            video_url TEXT DEFAULT '',
            caption TEXT DEFAULT '',
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            hook_type TEXT DEFAULT '',
            template_id TEXT DEFAULT '',
            duration_sec INTEGER DEFAULT 0,
            thumbnail_url TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (target_id) REFERENCES targets(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    return conn


# ─── Target CRUD ─────────────────────────────────────────────────────────

async def list_targets() -> List[dict]:
    conn = _get_db()
    rows = conn.execute("SELECT * FROM targets ORDER BY created_at DESC").fetchall()
    results = []
    for r in rows:
        d = dict(r)
        # count clips
        clip_count = conn.execute(
            "SELECT COUNT(*) FROM target_clips WHERE target_id = ?", (d["id"],)
        ).fetchone()[0]
        d["clip_count"] = clip_count
        results.append(d)
    conn.close()
    return results


async def get_target(target_id: int) -> Optional[dict]:
    conn = _get_db()
    row = conn.execute("SELECT * FROM targets WHERE id = ?", (target_id,)).fetchone()
    if not row:
        conn.close()
        return None
    target = dict(row)
    clips = conn.execute(
        "SELECT * FROM target_clips WHERE target_id = ? ORDER BY created_at DESC", (target_id,)
    ).fetchall()
    target["clips"] = [dict(c) for c in clips]
    conn.close()
    return target


async def create_target(data: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_db()
    cur = conn.execute(
        """INSERT INTO targets (username, display_name, niche, notes, avatar_url, follower_count, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data.get("username", ""),
            data.get("display_name", ""),
            data.get("niche", ""),
            data.get("notes", ""),
            data.get("avatar_url", ""),
            int(data.get("follower_count", 0)),
            now, now,
        ),
    )
    conn.commit()
    target_id = cur.lastrowid
    conn.close()
    return await get_target(target_id)


async def update_target(target_id: int, data: dict) -> Optional[dict]:
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_db()
    existing = conn.execute("SELECT * FROM targets WHERE id = ?", (target_id,)).fetchone()
    if not existing:
        conn.close()
        return None
    updates = {}
    for field in ("username", "display_name", "niche", "notes", "avatar_url", "follower_count"):
        if field in data:
            updates[field] = data[field]
    if not updates:
        conn.close()
        return dict(existing)
    updates["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [target_id]
    conn.execute(f"UPDATE targets SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return await get_target(target_id)


async def delete_target(target_id: int) -> bool:
    conn = _get_db()
    conn.execute("DELETE FROM target_clips WHERE target_id = ?", (target_id,))
    conn.execute("DELETE FROM targets WHERE id = ?", (target_id,))
    conn.commit()
    conn.close()
    return True


# ─── Clip CRUD ───────────────────────────────────────────────────────────

async def add_clip(target_id: int, data: dict) -> Optional[dict]:
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_db()
    existing = conn.execute("SELECT id FROM targets WHERE id = ?", (target_id,)).fetchone()
    if not existing:
        conn.close()
        return None
    cur = conn.execute(
        """INSERT INTO target_clips
           (target_id, video_url, caption, views, likes, comments, shares,
            hook_type, template_id, duration_sec, thumbnail_url, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            target_id,
            data.get("video_url", ""),
            data.get("caption", ""),
            int(data.get("views", 0)),
            int(data.get("likes", 0)),
            int(data.get("comments", 0)),
            int(data.get("shares", 0)),
            data.get("hook_type", ""),
            data.get("template_id", ""),
            int(data.get("duration_sec", 0)),
            data.get("thumbnail_url", ""),
            data.get("notes", ""),
            now,
        ),
    )
    conn.commit()
    clip_id = cur.lastrowid
    conn.close()
    return {"id": clip_id, "target_id": target_id, "success": True}


async def remove_clip(clip_id: int) -> bool:
    conn = _get_db()
    conn.execute("DELETE FROM target_clips WHERE id = ?", (clip_id,))
    conn.commit()
    conn.close()
    return True


async def batch_analyze_targets(target_ids: List[int]) -> dict:
    """Analyze all clips from given targets and return insights."""
    conn = _get_db()
    results = {"targets": [], "insights": [], "top_hooks": [], "top_templates": []}
    all_hooks = {}
    all_templates = {}

    for tid in target_ids:
        target = conn.execute("SELECT * FROM targets WHERE id = ?", (tid,)).fetchone()
        if not target:
            continue
        clips = conn.execute(
            "SELECT * FROM target_clips WHERE target_id = ? ORDER BY views DESC", (tid,)
        ).fetchall()
        t = dict(target)
        t["clips"] = [dict(c) for c in clips]
        t["clip_count"] = len(t["clips"])
        t["avg_views"] = round(sum(c["views"] for c in t["clips"]) / len(t["clips"])) if t["clips"] else 0
        t["total_views"] = sum(c["views"] for c in t["clips"])
        results["targets"].append(t)

        for c in t["clips"]:
            hook = c.get("hook_type", "") or "unknown"
            all_hooks[hook] = all_hooks.get(hook, 0) + c.get("views", 0)
            tpl = c.get("template_id", "") or "unknown"
            all_templates[tpl] = all_templates.get(tpl, 0) + c.get("views", 0)

    conn.close()

    # Sort by view count
    results["top_hooks"] = sorted(
        [{"hook": k, "total_views": v} for k, v in all_hooks.items()],
        key=lambda x: x["total_views"], reverse=True
    )
    results["top_templates"] = sorted(
        [{"template": k, "total_views": v} for k, v in all_templates.items()],
        key=lambda x: x["total_views"], reverse=True
    )

    results["insights"] = _generate_insights(results["targets"])
    return results


def _generate_insights(targets: List[dict]) -> List[str]:
    insights = []
    for t in targets:
        if t["clip_count"] >= 2 and t["avg_views"] > 1000:
            insights.append(
                f"@{t['username']} — avg {t['avg_views']:,.0f} views/clip "
                f"({t['clip_count']} clips, niche: {t['niche'] or '?'})"
            )
        elif t["clip_count"] >= 2:
            insights.append(
                f"@{t['username']} — {t['clip_count']} clips, "
                f"avg {t['avg_views']:,.0f} views, กำลังเริ่มต้น"
            )
        else:
            insights.append(
                f"@{t['username']} — มี {t['clip_count']} clip, ยังไม่พอวิเคราะห์"
            )
    return insights
