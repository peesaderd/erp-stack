"""Scheduler Micro-Service — Auto Post Scheduler
FastAPI server on port 8130.

Background worker that polls scheduled_posts.db every 60 seconds,
and calls tiktok-ugc-studio to execute the actual post when due.

PM2: process name 'scheduler', port 8130
"""

import os
import sys
import json
import time
import sqlite3
import threading
import logging
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")

# ─── Paths ────────────────────────────────────────────────────────────────
MODULE_DIR = Path(__file__).parent
DB_PATH = MODULE_DIR / "scheduled_posts.db"
TUS_API = os.environ.get("TUS_API", "http://localhost:8105")

app = FastAPI(title="Scheduler Service", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── Database ─────────────────────────────────────────────────────────────
def _init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            account_id TEXT,
            caption TEXT,
            affiliate_link TEXT DEFAULT '',
            video_path TEXT,
            schedule_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            error TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            posted_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info(f"DB ready: {DB_PATH}")

_init_db()


# ─── Pydantic Models ──────────────────────────────────────────────────────
class ScheduleCreate(BaseModel):
    job_id: str = ""
    account_id: str
    caption: str
    affiliate_link: str = ""
    video_path: str
    schedule_at: str  # ISO datetime or "now"


class ScheduleResponse(BaseModel):
    success: bool
    scheduled: bool = False
    schedule_id: int = 0
    job_id: str = ""
    account_id: str = ""
    schedule_at: str = ""
    capton: str = ""
    error: str = ""


# ─── API Endpoints ────────────────────────────────────────────────────────

@app.post("/schedule")
async def schedule_post(req: ScheduleCreate):
    """Create or execute a scheduled post.
    
    If schedule_at is 'now' or in the past → execute immediately via TUS API.
    If schedule_at is in the future → store in DB for background worker.
    """
    is_now = req.schedule_at.lower() == 'now' if req.schedule_at else True
    
    if not is_now:
        try:
            sched_dt = datetime.fromisoformat(req.schedule_at)
            if sched_dt <= datetime.now():
                is_now = True
        except ValueError:
            is_now = True
    
    if is_now:
        # Execute immediately via TUS API
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(f"{TUS_API}/video/do-post", json={
                    "job_id": req.job_id,
                    "account_id": req.account_id,
                    "caption": req.caption,
                    "affiliate_link": req.affiliate_link,
                    "video_path": req.video_path,
                })
                data = resp.json()
                return {
                    "success": resp.status_code < 400,
                    "scheduled": False,
                    "immediate": True,
                    "job_id": req.job_id,
                    "result": data,
                }
        except Exception as e:
            return {"success": False, "error": f"Immediate post failed: {str(e)[:300]}"}
    
    # Store for later
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO scheduled_posts (job_id, account_id, caption, affiliate_link, video_path, schedule_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 'pending')",
            (req.job_id, req.account_id, req.caption, req.affiliate_link or "", req.video_path, req.schedule_at)
        )
        conn.commit()
        post_id = conn.lastrowid
        conn.close()
        logger.info(f"Scheduled post {post_id} for {req.schedule_at}")
        return {
            "success": True,
            "scheduled": True,
            "schedule_id": post_id,
            "job_id": req.job_id,
            "account_id": req.account_id,
            "schedule_at": req.schedule_at,
            "caption": req.caption,
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


@app.get("/scheduled")
async def list_scheduled(status: str = "", limit: int = 50):
    """List all scheduled posts."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        if status:
            rows = conn.execute(
                "SELECT id, job_id, account_id, caption, affiliate_link, video_path, schedule_at, status, error, created_at, posted_at "
                "FROM scheduled_posts WHERE status=? ORDER BY schedule_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, job_id, account_id, caption, affiliate_link, video_path, schedule_at, status, error, created_at, posted_at "
                "FROM scheduled_posts ORDER BY schedule_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        conn.close()
        posts = [{
            "id": r[0], "job_id": r[1], "account_id": r[2],
            "caption": r[3], "affiliate_link": r[4], "video_path": r[5],
            "schedule_at": r[6], "status": r[7], "error": r[8],
            "created_at": r[9], "posted_at": r[10],
        } for r in rows]
        return {"success": True, "posts": posts, "count": len(posts)}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


@app.delete("/scheduled/{post_id}")
async def cancel_scheduled(post_id: int):
    """Cancel a pending scheduled post."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("DELETE FROM scheduled_posts WHERE id=? AND status='pending'", (post_id,))
        conn.commit()
        affected = conn.total_changes
        conn.close()
        return {"success": True, "canceled": affected > 0}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "service": "scheduler", "uptime": time.time()}


# ─── Background Worker ────────────────────────────────────────────────────
def _worker_loop():
    """Daemon thread: poll every 60s for due scheduled posts."""
    logger.info("Scheduler worker started (poll every 60s)")
    while True:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            due = conn.execute(
                "SELECT id, job_id, account_id, caption, affiliate_link, video_path, schedule_at "
                "FROM scheduled_posts WHERE status='pending' AND schedule_at <= datetime('now')"
            ).fetchall()
            
            for row in due:
                pid, jid, acct, cap, aff_link, vpath, sched_at = row
                try:
                    # Build final caption
                    final_caption = cap
                    if aff_link:
                        final_caption += f"\n\n\U0001f517 {aff_link}"
                    
                    # Call TUS API to do the actual post
                    resp = httpx.post(
                        f"{TUS_API}/video/do-post",
                        json={
                            "job_id": jid,
                            "account_id": acct,
                            "caption": final_caption,
                            "affiliate_link": aff_link,
                            "video_path": vpath,
                        },
                        timeout=120
                    )
                    if resp.status_code < 400:
                        conn.execute(
                            "UPDATE scheduled_posts SET status='published', posted_at=datetime('now') WHERE id=?",
                            (pid,)
                        )
                        logger.info(f"Post {pid} published to {acct}")
                    else:
                        err = resp.text[:200]
                        conn.execute(
                            "UPDATE scheduled_posts SET status='failed', error=? WHERE id=?",
                            (err, pid)
                        )
                        logger.error(f"Post {pid} failed: {err}")
                except Exception as e:
                    conn.execute(
                        "UPDATE scheduled_posts SET status='failed', error=? WHERE id=?",
                        (str(e)[:300], pid)
                    )
                    logger.error(f"Post {pid} exception: {e}")
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
        time.sleep(60)


@app.on_event("startup")
async def startup():
    """Start background worker thread on service startup."""
    thread = threading.Thread(target=_worker_loop, daemon=True)
    thread.start()
    logger.info("Scheduler service started on port 8130")


# ─── Main ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8130"))
    uvicorn.run(app, host="0.0.0.0", port=port)
