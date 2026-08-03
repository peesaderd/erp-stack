"""Batch generator routes — queue management + bash worker spawn."""
import json
import os
import shutil
import sqlite3
import subprocess
import threading
import uuid
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException

from .deps import PIPELINE_DB_PATH, logger

router = APIRouter(tags=["batch"])


def _init_batch_db():
    """Create batch queue table if not exists."""
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS batch_jobs (
            id TEXT PRIMARY KEY,
            name TEXT,
            style TEXT DEFAULT 'holding',
            duration INTEGER DEFAULT 15,
            concurrency INTEGER DEFAULT 3,
            total INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT,
            error_message TEXT
        )
    ''')
    conn.commit()
    conn.close()

_init_batch_db()
@router.post("/batch/create")
async def batch_create(data: dict):
    """Create a new batch job from selected products."""
    import json, uuid, time
    from datetime import datetime
    
    products = data.get("products", [])
    style = data.get("style", "holding")
    duration = data.get("duration", 15)
    concurrency = data.get("concurrency", 3)
    
    if not products:
        raise HTTPException(status_code=400, detail="No products selected")
    
    batch_id = "batch_" + uuid.uuid4().hex[:10]
    now = datetime.utcnow().isoformat()
    
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    conn.execute(
        "INSERT INTO batch_jobs (id, name, style, duration, concurrency, total, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (batch_id, f"Batch {len(products)} products", style, duration, concurrency, len(products), "running", now, now)
    )
    conn.commit()
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS batch_queue (
            id TEXT PRIMARY KEY,
            batch_id TEXT,
            product_title TEXT,
            product_image TEXT,
            product_url TEXT,
            style TEXT,
            duration INTEGER,
            status TEXT DEFAULT 'pending',
            pipeline_job_id TEXT,
            error_message TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    
    # Insert each product as a queue item
    for p in products:
        qid = "bq_" + uuid.uuid4().hex[:10]
        conn.execute(
            "INSERT OR IGNORE INTO batch_queue (id, batch_id, product_title, product_image, product_url, style, duration, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (qid, batch_id, p.get("title",""), p.get("image",""), p.get("url",""), style, duration, "pending", now, now)
        )
    conn.commit()
    conn.close()
    
    # Spawn bash worker in background
    import subprocess, threading
    
    def _worker(bid):
        time.sleep(1)
        try:
            bash_path = shutil.which("ugc") or shutil.which("bash") or "/bin/bash"
            if os.path.exists("/home/openhands/erp-stack/bin/ugc.sh"):
                cmd = ["bash", "/home/openhands/erp-stack/bin/ugc.sh", "batch", "--batch-id", bid]
            else:
                cmd = ["python3", os.path.join(os.path.dirname(os.path.dirname(__file__)), "batch_worker.py"), "--batch-id", bid]
            subprocess.Popen(cmd, cwd=os.path.dirname(os.path.dirname(__file__)), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as ex:
            conn2 = sqlite3.connect(PIPELINE_DB_PATH)
            conn2.execute("UPDATE batch_jobs SET status=?, error_message=? WHERE id=?", ("failed", str(ex), bid))
            conn2.commit()
            conn2.close()
    
    threading.Thread(target=_worker, args=(batch_id,), daemon=True).start()
    
    return {"success": True, "batch_id": batch_id, "total": len(products)}

@router.get("/batch/list")
def batch_list():
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    rows = conn.execute(
        "SELECT id, name, style, duration, concurrency, total, completed, failed, status, created_at, updated_at, error_message FROM batch_jobs ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return {
        "batches": [
            {
                "id": r[0], "name": r[1], "style": r[2], "duration": r[3],
                "concurrency": r[4], "total": r[5], "completed": r[6],
                "failed": r[7], "status": r[8], "created_at": r[9],
                "updated_at": r[10], "error_message": r[11]
            }
            for r in rows
        ]
    }

@router.get("/batch/{batch_id}/status")
def batch_status(batch_id: str):
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    row = conn.execute(
        "SELECT id, name, style, duration, concurrency, total, completed, failed, status, created_at, updated_at, error_message FROM batch_jobs WHERE id=?",
        (batch_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    items = conn.execute(
        "SELECT id, product_title, status, pipeline_job_id, error_message FROM batch_queue WHERE batch_id=? ORDER BY created_at",
        (batch_id,)
    ).fetchall()
    conn.close()
    
    return {
        "batch": {
            "id": row[0], "name": row[1], "style": row[2], "duration": row[3],
            "concurrency": row[4], "total": row[5], "completed": row[6],
            "failed": row[7], "status": row[8], "created_at": row[9],
            "updated_at": row[10], "error_message": row[11]
        },
        "items": [
            {"id": i[0], "product_title": i[1], "status": i[2], "pipeline_job_id": i[3], "error_message": i[4]}
            for i in items
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════
# AITOEARN ROUTES — Campaigns, Affiliates, Earnings bridge
# ═══════════════════════════════════════════════════════════════════════════

