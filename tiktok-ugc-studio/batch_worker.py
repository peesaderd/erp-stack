#!/usr/bin/env python3
"""
Batch Worker — Consumes batch_queue items from pipeline.db,
runs TUS pipeline for each product, and updates status.

Usage: python3 batch_worker.py --batch-id batch_xxx [--concurrency 3]
"""

import os, sys, json, sqlite3, time, argparse, traceback
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PIPELINE_DB_PATH = os.path.join(os.path.dirname(__file__), "pipeline.db")

def get_conn():
    return sqlite3.connect(PIPELINE_DB_PATH)

def log(msg):
    print(f"[{datetime.utcnow().isoformat()}] {msg}")

def create_pipeline_job(batch_item):
    """Create a TUS pipeline job and return its job_id."""
    conn = get_conn()
    import uuid as uuid_mod
    job_id = "vid_" + uuid_mod.uuid4().hex[:8]
    now = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT INTO pipeline_jobs (job_id, account_id, status, product_title, product_url, product_image, created_at, updated_at)
           VALUES (?, 'batch', 'pending', ?, ?, ?, ?, ?)""",
        (job_id,
         batch_item.get("product_title", ""),
         batch_item.get("product_url", ""),
         batch_item.get("product_image", ""),
         now, now)
    )
    conn.commit()
    conn.close()
    return job_id

def run_pipeline(job_id, batch_item):
    """Run the pipeline for one product."""
    from modules.pipeline.main import run_full_pipeline as pipeline_run
    
    product_data = {
        "title": batch_item.get("product_title", ""),
        "image": batch_item.get("product_image", ""),
        "url": batch_item.get("product_url", ""),
    }
    
    try:
        result = pipeline_run(
            product_title=product_data["title"],
            product_image=product_data["image"],
            product_url=product_data["url"],
            ugc_style=batch_item.get("style", "holding"),
            duration=batch_item.get("duration", 15),
            aspect_ratio="9:16",
            run_tts=True,
            run_video_gen=True,
            run_compose=True,
        )
        return result
    except Exception as e:
        log(f"Pipeline error for {job_id}: {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def process_batch(batch_id, concurrency=3):
    """Process all pending items in a batch with concurrency control."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    conn = get_conn()
    items = conn.execute(
        "SELECT id, product_title, product_image, product_url, style, duration FROM batch_queue WHERE batch_id=? AND status='pending' ORDER BY created_at",
        (batch_id,)
    ).fetchall()
    conn.close()
    
    log(f"Processing batch {batch_id}: {len(items)} items, concurrency={concurrency}")
    
    def process_one(item):
        qid, title, image, url, style, duration = item
        log(f"Starting: {title[:50]}")
        
        item_data = {
            "id": qid,
            "product_title": title,
            "product_image": image,
            "product_url": url,
            "style": style,
            "duration": duration,
        }
        
        # Create pipeline job
        job_id = create_pipeline_job(item_data)
        
        # Update queue item status
        conn2 = get_conn()
        conn2.execute(
            "UPDATE batch_queue SET status='running', pipeline_job_id=?, updated_at=? WHERE id=?",
            (job_id, datetime.utcnow().isoformat(), qid)
        )
        conn2.commit()
        conn2.close()
        
        # Run pipeline
        result = run_pipeline(job_id, item_data)
        
        # Update status based on result
        success = result.get("success", False) if isinstance(result, dict) else False
        conn3 = get_conn()
        conn3.execute(
            "UPDATE batch_queue SET status=?, error_message=?, updated_at=? WHERE id=?",
            ("completed" if success else "failed",
             None if success else result.get("error", str(result)),
             datetime.utcnow().isoformat(), qid)
        )
        
        # Update batch totals
        conn3.execute(
            "UPDATE batch_jobs SET completed=completed+?, failed=failed+?, updated_at=? WHERE id=?",
            (1 if success else 0, 0 if success else 1, datetime.utcnow().isoformat(), batch_id)
        )
        conn3.commit()
        conn3.close()
        
        log(f"{'✅' if success else '❌'} {title[:50]} -> {'completed' if success else 'failed'}")
        return success
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(process_one, item): item for item in items}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                log(f"Worker error: {e}")
    
    # Mark batch complete
    conn4 = get_conn()
    conn4.execute(
        "UPDATE batch_jobs SET status='completed', updated_at=? WHERE id=? AND failed=0 AND completed=total",
        (datetime.utcnow().isoformat(), batch_id)
    )
    conn4.execute(
        "UPDATE batch_jobs SET status='partial', updated_at=? WHERE id=? AND failed>0 AND (completed+failed)>=total",
        (datetime.utcnow().isoformat(), batch_id)
    )
    conn4.commit()
    conn4.close()
    
    log(f"Batch {batch_id} finished!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()
    process_batch(args.batch_id, args.concurrency)
