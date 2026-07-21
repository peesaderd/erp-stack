"""
Pipeline job tracker — SQLite persistence for pipeline jobs.
Extracted from main.py.
"""

import os
import json
import uuid
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger("pipeline-db")

STORAGE_DIR = Path(__file__).parent / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

PIPELINE_DB_PATH = os.path.join(os.path.dirname(__file__), "pipeline.db")
LOGS_DB_PATH = STORAGE_DIR / "pipeline_logs.db"


def init_db():
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_jobs (
            job_id TEXT PRIMARY KEY,
            account_id TEXT,
            product_url TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT,
            steps_data TEXT DEFAULT '{}'
        )
    """)
    conn.commit()
    conn.close()

# Auto-init on import
init_db()


def create_job(account_id: str = "", product_url: str = "", job_id: Optional[str] = None) -> str:
    """Create a new pipeline job entry."""
    if not job_id:
        job_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO pipeline_jobs (job_id, account_id, product_url, status, created_at, updated_at, steps_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (job_id, account_id, product_url, "pending", now, now, "{}")
    )
    conn.commit()
    conn.close()
    return job_id


def update_step(job_id: str, step_name: str, status: str, result: Optional[dict] = None):
    """Update a pipeline step status."""
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    row = conn.execute("SELECT steps_data FROM pipeline_jobs WHERE job_id = ?", (job_id,)).fetchone()
    if not row:
        conn.close()
        return
    steps = json.loads(row[0])
    steps[step_name] = {"status": status, **(result or {})}
    now = datetime.utcnow().isoformat()
    TERMINAL_STATUSES = {"success", "error", "skipped"}
    all_done = all(s.get("status") in TERMINAL_STATUSES for s in steps.values()) if steps else False
    overall = "completed" if all_done else "running"
    conn.execute(
        "UPDATE pipeline_jobs SET steps_data = ?, status = ?, updated_at = ? WHERE job_id = ?",
        (json.dumps(steps), overall, now, job_id)
    )
    conn.commit()
    conn.close()


def get_job(job_id: str) -> Optional[dict]:
    """Get a pipeline job by ID."""
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    row = conn.execute("SELECT * FROM pipeline_jobs WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "job_id": row[0],
        "account_id": row[1],
        "product_url": row[2],
        "status": row[3],
        "created_at": row[4],
        "updated_at": row[5],
        "steps": json.loads(row[6]),
    }


def list_jobs(limit: int = 20) -> list:
    """List recent pipeline jobs."""
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    rows = conn.execute(
        "SELECT job_id, account_id, status, product_url, created_at, updated_at FROM pipeline_jobs ORDER BY REPLACE(created_at, ' ', 'T') DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {"job_id": r[0], "account_id": r[1], "status": r[2], "product_url": r[3], "created_at": r[4], "updated_at": r[5]}
        for r in rows
    ]


def count_jobs() -> int:
    """Count total pipeline jobs."""
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    row = conn.execute("SELECT COUNT(*) FROM pipeline_jobs").fetchone()
    conn.close()
    return row[0] if row else 0


def _path_to_web_url(filepath: str) -> str:
    """Convert local file path to public web URL."""
    if not filepath:
        return ""
    fp = str(filepath)
    for prefix in [
        str(STORAGE_DIR),
        "/home/openhands/erp-stack/modules/video/storage",
        "/home/openhands/erp-stack/tiktok-ugc-studio/storage",
    ]:
        if fp.startswith(prefix):
            rel = fp[len(prefix):].lstrip("/")
            return f"/api/tiktok/static/{rel}"
    if fp.startswith("http://") or fp.startswith("https://"):
        return fp
    if fp.startswith("/api/") or fp.startswith("/static/"):
        if fp.startswith("/static/") and not fp.startswith("/api/"):
            return f"/api/tiktok{fp}"
        return fp
    return os.path.basename(fp)


def enrich_from_logs(job_data: dict) -> dict:
    """Try to enrich pipeline job with data from pipeline_logs.db."""
    if not LOGS_DB_PATH.exists():
        return job_data
    try:
        conn = sqlite3.connect(str(LOGS_DB_PATH))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM pipeline_jobs WHERE job_id = ?", (job_data.get("job_id", ""),)).fetchone()
        conn.close()
        if row:
            d = dict(row)
            job_data["logs"] = {
                "product_title": d.get("product_title", ""),
                "product_description": (d.get("product_description") or "")[:300],
                "product_price": d.get("product_price"),
                "image_prompt": d.get("image_prompt", ""),
                "video_prompts": d.get("video_prompts", ""),
                "script": d.get("script", ""),
                "negative_prompt": d.get("negative_prompt", ""),
                "hashtags": json.loads(d.get("hashtags", "[]")) if d.get("hashtags") else [],
                "final_video_path": d.get("final_video_path", ""),
                "cost_total": d.get("cost_total", 0),
                "cost_image": d.get("cost_image", 0),
                "cost_voice": d.get("cost_voice", 0),
                "cost_video": d.get("cost_video", 0),
                "aspect_ratio": d.get("aspect_ratio", "9:16"),
                "recipe_name": d.get("recipe_name", "tus"),
                "ugc_style": d.get("ugc_style", ""),
                "error_message": d.get("error_message", ""),
            }
            log = job_data["logs"]
            if log.get("final_video_path"):
                log["video_web_url"] = _path_to_web_url(log["final_video_path"])
    except Exception as e:
        logger.warning(f"Failed to enrich from logs DB: {e}")
    return job_data
