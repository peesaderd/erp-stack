"""
Post Queue — SQLite persistence for scheduled/queued posts.
Simple, flat schema — one queue for all platforms (TikTok first).
"""

import os
import json
import uuid
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger("post-queue")

DB_PATH = Path(__file__).parent.parent / "post_queue.db"

STATUSES = ["pending", "scheduled", "posting", "posted", "failed", "cancelled"]
PLATFORMS = ["tiktok", "youtube", "instagram"]


def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS post_queue (
            id TEXT PRIMARY KEY,
            job_id TEXT,
            video_path TEXT NOT NULL,
            caption TEXT,
            hashtags TEXT DEFAULT '[]',
            affiliate_link TEXT,
            platform TEXT DEFAULT 'tiktok',
            schedule_at TEXT,
            status TEXT DEFAULT 'pending',
            publish_id TEXT,
            post_url TEXT,
            error TEXT,
            attempt_count INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    # Index for fast scheduler queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_schedule_status 
        ON post_queue(status, schedule_at)
    """)
    conn.commit()
    conn.close()


init_db()


def enqueue(
    job_id: str = "",
    video_path: str = "",
    caption: str = "",
    hashtags: list = None,
    affiliate_link: str = "",
    platform: str = "tiktok",
    schedule_at: str = None,
) -> str:
    """Add a video to the post queue. Returns post id."""
    post_id = f"pq_{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow().isoformat()
    status = "scheduled" if schedule_at else "pending"

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """INSERT INTO post_queue 
           (id, job_id, video_path, caption, hashtags, affiliate_link, 
            platform, schedule_at, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            post_id, job_id, video_path, caption,
            json.dumps(hashtags or []), affiliate_link,
            platform, schedule_at, status, now, now,
        ),
    )
    conn.commit()
    conn.close()
    logger.info(f"Enqueued post {post_id} — platform={platform} schedule={schedule_at or 'immediate'}")
    return post_id


def get_due_posts(now: str = None) -> List[Dict]:
    """Get posts ready to be published now.
    - status=scheduled with schedule_at <= now
    - status=pending (immediate posts)
    - status=failed with attempt_count < max_attempts
    """
    if now is None:
        now = datetime.utcnow().isoformat()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """SELECT * FROM post_queue WHERE 
           (status = 'pending')
           OR (status = 'scheduled' AND schedule_at <= ?)
           OR (status = 'failed' AND attempt_count < max_attempts)
           ORDER BY created_at ASC
           LIMIT 20""",
        (now,),
    ).fetchall()
    conn.close()

    return [dict(r) for r in rows]


def mark_posting(post_id: str):
    _update(post_id, status="posting", attempt="+1")


def mark_posted(post_id: str, publish_id: str = "", post_url: str = ""):
    _update(post_id, status="posted", publish_id=publish_id, post_url=post_url)


def mark_failed(post_id: str, error: str):
    _update(post_id, status="failed", error=error)


def cancel(post_id: str):
    _update(post_id, status="cancelled")


def _update(post_id: str, status: str = None, publish_id: str = None,
            post_url: str = None, error: str = None, attempt: str = None):
    """Update post queue entry."""
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(str(DB_PATH))
    sets = ["updated_at = ?"]
    params = [now]

    if status:
        sets.append("status = ?")
        params.append(status)
    if publish_id is not None:
        sets.append("publish_id = ?")
        params.append(publish_id)
    if post_url is not None:
        sets.append("post_url = ?")
        params.append(post_url)
    if error is not None:
        sets.append("error = ?")
        params.append(error)
    if attempt == "+1":
        sets.append("attempt_count = attempt_count + 1")

    params.append(post_id)
    conn.execute(
        f"UPDATE post_queue SET {', '.join(sets)} WHERE id = ?",
        params,
    )
    conn.commit()
    conn.close()


def list_posts(status: str = None, platform: str = None, limit: int = 50) -> List[Dict]:
    """List posts with optional filters."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    query = "SELECT * FROM post_queue WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if platform:
        query += " AND platform = ?"
        params.append(platform)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_post(post_id: str) -> Optional[Dict]:
    """Get a single post by ID."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM post_queue WHERE id = ?", (post_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_post(post_id: str) -> bool:
    """Delete a post from queue."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM post_queue WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    return True


def get_stats() -> Dict[str, int]:
    """Get queue statistics."""
    conn = sqlite3.connect(str(DB_PATH))
    stats = {}
    for status in STATUSES:
        row = conn.execute(
            "SELECT COUNT(*) FROM post_queue WHERE status = ?", (status,)
        ).fetchone()
        stats[status] = row[0] if row else 0
    conn.close()
    return stats


def get_calendar(days: int = 7) -> List[Dict]:
    """Get upcoming schedule for content calendar."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    start = datetime.utcnow().isoformat()
    end = (datetime.utcnow() + timedelta(days=days)).isoformat()

    rows = conn.execute(
        """SELECT * FROM post_queue 
           WHERE schedule_at >= ? AND schedule_at < ? 
           AND status IN ('scheduled', 'pending')
           ORDER BY schedule_at ASC""",
        (start, end),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
