"""Publisher routes — post queue, scheduler, calendar, retry."""
import asyncio
import json
import os
import sqlite3

from fastapi import APIRouter, HTTPException

from gemini_agent import generate_publish_content
from publisher import scheduler as publisher_scheduler
from publisher.post_queue import (
    list_posts as pq_list,
    get_post as pq_get,
    delete_post as pq_delete,
    get_calendar as pq_calendar,
)
from connect.tiktok_poster import poster as tiktok_poster
from connect.aitoearn_client import client as aitoearn
from .deps import logger, LOGS_DB_PATH, VIDEOS_DIR

router = APIRouter(tags=["publisher"])
@router.post("/publisher/save-content")
async def publisher_save_content(req: dict):
    """Save AI-generated title+description back into pipeline_logs.db."""
    job_id = req.get("job_id", "")
    title = req.get("title", "")
    description = req.get("description", "")
    platform = req.get("platform", "tiktok")

    if not job_id:
        raise HTTPException(status_code=400, detail="job_id required")

    logs_db = LOGS_DB_PATH
    if not os.path.exists(str(logs_db)):
        raise HTTPException(status_code=404, detail="pipeline_logs.db not found")

    try:
        conn = sqlite3.connect(str(logs_db))
        existing = conn.execute("SELECT 1 FROM pipeline_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE pipeline_jobs SET product_title = ?, product_description = ? WHERE job_id = ?",
                (title or "", description or "", job_id),
            )
        else:
            conn.execute(
                "INSERT INTO pipeline_jobs (job_id, product_title, product_description) VALUES (?, ?, ?)",
                (job_id, title or "", description or ""),
            )
        conn.commit()
        conn.close()
        return {"success": True, "saved": True, "job_id": job_id}
    except Exception as e:
        logger.error(f"save-content failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/publisher/generate-content")
async def publisher_generate_content(req: dict):
    """Generate platform-optimized title + description using Gemini."""
    product_name = req.get("product_name", "") or ""
    description = req.get("description", "") or ""
    tags = req.get("tags", []) or []
    platform = req.get("platform", "tiktok")

    if not product_name:
        raise HTTPException(status_code=400, detail="product_name required")

    result = generate_publish_content(
        product_name=product_name,
        description=description,
        tags=tags,
        platform=platform,
    )
    return {"success": True, **result}


@router.get("/publisher/status")
async def publisher_status():
    """Get publisher scheduler status + queue stats."""
    return {"success": True, "data": publisher_scheduler.get_status()}

@router.get("/publisher/queue")
async def publisher_queue(status: str = None, platform: str = None, limit: int = 50):
    """List posts in queue — filter by status/platform."""
    posts = pq_list(status=status, platform=platform, limit=limit)
    return {"success": True, "posts": posts, "count": len(posts)}

@router.post("/publisher/enqueue")
async def publisher_enqueue(req: dict):
    """Add a video to the post queue. Validates video exists + AitoEarn account."""
    video_path = req.get("video_path", "")
    title = req.get("title", "")
    description = req.get("description", "")
    caption = req.get("caption", "")
    hashtags = req.get("hashtags", [])
    platform = req.get("platform", "tiktok")
    account_id = req.get("account_id", "")  # Optional override
    schedule_at = req.get("schedule_at")
    job_id = req.get("job_id", "")
    affiliate_link = req.get("affiliate_link", "")

    if not video_path:
        raise HTTPException(status_code=400, detail="video_path required")

    # Resolve video path — handles web URLs, local paths, and storage
    resolved = video_path

    # Strip web path prefixes: /api/tiktok/static/videos/ → storage/videos/
    filename = os.path.basename(video_path)
    for prefix in ("/api/tiktok/static/videos/", "/static/videos/", "/storage/videos/"):
        if video_path.startswith(prefix):
            resolved = str(VIDEOS_DIR / filename)
            break

    # Fallback: check filesystem
    if not os.path.exists(resolved):
        alt = VIDEOS_DIR / filename
        if alt.exists():
            resolved = str(alt)
        else:
            raise HTTPException(status_code=400, detail=f"Video not found: {video_path} (resolved: {resolved})")

    # Resolve AitoEarn account
    account_info = None
    if aitoearn.configured:
        if account_id:
            account_info = await aitoearn.get_account(account_id)
        else:
            accounts = await aitoearn.list_accounts(platform=platform)
            active = [a for a in accounts if a.get("status") == 1]
            if active:
                account_id = active[0]["id"]
                account_info = active[0]

    try:
        post_id = publisher_scheduler.enqueue_completed_video(
            job_id=job_id,
            video_path=resolved,
            title=title,
            description=description,
            caption=caption,
            hashtags=hashtags,
            affiliate_link=affiliate_link,
            platform=platform,
            account_id=account_id,
            schedule_at=schedule_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {
        "success": True,
        "post_id": post_id,
        "schedule_at": schedule_at,
        "resolved_path": resolved,
        "platform": platform,
        "account": {
            "id": account_id,
            "nickname": account_info.get("nickname") if account_info else None,
            "avatar": account_info.get("avatar") if account_info else None,
        } if account_info else None,
    }

@router.post("/publisher/{post_id}/post-now")
async def publisher_post_now(post_id: str):
    """Post a queued video immediately (skip schedule). Only works if status is pending."""
    post = pq_get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] not in ("pending", "scheduled"):
        raise HTTPException(status_code=400, detail=f"Cannot post: status is '{post['status']}' (must be pending/scheduled)")
    
    # Check for duplicate video posts
    from publisher.post_queue import list_posts
    existing = list_posts(status="posted", limit=50)
    same_video = [p for p in existing if p.get("video_path") == post["video_path"]]
    if same_video:
        raise HTTPException(status_code=409, detail=f"Video already posted ({len(same_video)} times). Use a different video.")

    import json as _json
    hashtags = _json.loads(post.get("hashtags", "[]")) if post.get("hashtags") else []

    from publisher.post_queue import mark_posting
    mark_posting(post_id)

    try:
        result = await tiktok_poster.post(
            video_path=post["video_path"],
            caption=post.get("caption", ""),
            title=post.get("title", ""),
            description=post.get("description", ""),
            platform=post.get("platform", "tiktok"),
            account_id=post.get("account_id", ""),
            hashtags=hashtags,
        )
        if result.get("success"):
            from publisher.post_queue import mark_posted
            publish_id = result.get("task_id") or result.get("flow_id") or ""
            post_url = result.get("platform_work_id") or ""
            mark_posted(post_id, publish_id, post_url)
            return {
                "success": True,
                "post_id": post_id,
                "method": result.get("method"),
                "flow_id": result.get("flow_id"),
                "task_id": result.get("task_id"),
                "platform_work_id": result.get("platform_work_id"),
            }
        else:
            from publisher.post_queue import mark_failed
            mark_failed(post_id, result.get("error", "Unknown"))
            return {"success": False, "error": result.get("error")}
    except Exception as e:
        from publisher.post_queue import mark_failed
        mark_failed(post_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/publisher/bulk-schedule")
async def publisher_bulk_schedule(req: dict):
    """Bulk schedule multiple videos.
    
    Body: {
        video_ids: [{job_id, video_path, title?, description?, caption?, hashtags?}, ...],
        date_range_start: "2026-07-16",
        date_range_end: "2026-07-22",
        count_per_day: 3,
        mode: "random" | "fixed" | "sequential",
        time_window_start: "08:00",
        time_window_end: "22:00",
        platform: "tiktok"
    }
    """
    video_ids = req.get("video_ids", [])
    if not video_ids:
        raise HTTPException(status_code=400, detail="video_ids required")
    
    try:
        post_ids = publisher_scheduler.bulk_schedule(
            video_ids=video_ids,
            date_range_start=req.get("date_range_start"),
            date_range_end=req.get("date_range_end"),
            count_per_day=req.get("count_per_day", 3),
            mode=req.get("mode", "random"),
            time_window_start=req.get("time_window_start", "08:00"),
            time_window_end=req.get("time_window_end", "22:00"),
            platform=req.get("platform", "tiktok"),
        )
        return {
            "success": True,
            "scheduled": len(post_ids),
            "post_ids": post_ids,
            "config": {
                "date_range": f"{req.get('date_range_start','today')} → {req.get('date_range_end','+7d')}",
                "count_per_day": req.get("count_per_day", 3),
                "mode": req.get("mode", "random"),
                "window": f"{req.get('time_window_start','08:00')}–{req.get('time_window_end','22:00')}",
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/publisher/{post_id}")
async def publisher_cancel(post_id: str):
    """Cancel a scheduled post."""
    pq_delete(post_id)
    return {"success": True}

@router.post("/publisher/{post_id}/retry")
async def publisher_retry(post_id: str):
    """Retry a failed post with exponential backoff."""
    post = pq_get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post["status"] == "posted":
        return {"success": True, "message": "Already posted"}
    
    from publisher.post_queue import mark_posting
    mark_posting(post_id)
    
    import json as _json
    hashtags = _json.loads(post.get("hashtags", "[]")) if post.get("hashtags") else []
    
    # Exponential backoff based on attempts
    attempt = (post.get("attempt_count") or 0) + 1
    delay = min(30 * (2 ** attempt), 1800)  # 30s, 60s, 2min, 4min, ... max 30min
    logger.info(f"Retrying {post_id} attempt #{attempt} after {delay}s delay")
    await asyncio.sleep(min(delay / 10, 30))  # Wait scaled-down for API response
    
    try:
        result = await tiktok_poster.post(
            video_path=post["video_path"],
            caption=post.get("caption", ""),
            title=post.get("title", ""),
            description=post.get("description", ""),
            platform=post.get("platform", "tiktok"),
            account_id=post.get("account_id", ""),
            hashtags=hashtags,
        )
        if result.get("success"):
            from publisher.post_queue import mark_posted
            mark_posted(post_id, result.get("post_id", ""), result.get("post_url", ""))
            return {"success": True, "post_id": post_id, "method": result.get("method")}
        else:
            from publisher.post_queue import mark_failed
            mark_failed(post_id, result.get("error", "Retry failed"))
            raise HTTPException(status_code=500, detail=result.get("error"))
    except HTTPException:
        raise
    except Exception as e:
        from publisher.post_queue import mark_failed
        mark_failed(post_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/publisher/calendar")
async def publisher_calendar(days: int = 7):
    """Get content calendar for next N days."""
    items = pq_calendar(days=days)
    # Group by date
    from collections import defaultdict
    by_date = defaultdict(list)
    for item in items:
        date_key = (item.get("schedule_at") or "")[:10]
        by_date[date_key].append(item)
    return {"success": True, "days": days, "calendar": dict(by_date), "total": len(items)}

# ═══════════════════════════════════════════════════════════════════════════
# CONNECTION / TIKTOK ROUTES — Cookie management, OAuth, posting
# ═══════════════════════════════════════════════════════════════════════════
