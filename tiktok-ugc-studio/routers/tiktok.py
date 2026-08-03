"""TikTok routes — account management, upload, cookies."""
import os

from fastapi import APIRouter, HTTPException

from models import VideoPostRequest
from tiktok_accounts import (
    list_accounts as _list_tiktok_accounts,
    get_account as _get_tiktok_account,
    save_account as _save_tiktok_account,
    delete_account as _delete_tiktok_account,
)
from connect.tiktok_poster import poster as tiktok_poster
from .deps import VIDEOS_DIR, _pipeline_results

router = APIRouter(tags=["tiktok"])
@router.get("/tiktok/accounts")
async def list_tiktok_accounts():
    accounts = _list_tiktok_accounts()
    return {"success": True, "accounts": accounts}

@router.post("/tiktok/accounts")
async def save_tiktok_account(req: dict):
    account_id = req.pop("account_id", "")
    if not account_id:
        raise HTTPException(status_code=400, detail="account_id required")
    _save_tiktok_account(account_id, req)
    return {"success": True, "account_id": account_id}

@router.delete("/tiktok/accounts/{account_id}")
async def delete_tiktok_account(account_id: str):
    _delete_tiktok_account(account_id)
    return {"success": True}

@router.post("/tiktok/upload")
async def upload_to_tiktok(req: dict):
    """Upload video to TikTok with session token."""
    video_path = req.get("video_path", "")
    caption = req.get("caption", "")
    session_token = req.get("session_token", "")

    if not video_path or not session_token:
        raise HTTPException(status_code=400, detail="video_path and session_token required")

    os.environ["TIKTOK_SESSION"] = session_token
    try:
        from simple_tiktok_uploader import upload
        result = upload(video_path, caption)
        post_id = getattr(result, "id", "") or getattr(result, "video_id", "")
        return {"success": True, "video_id": post_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/video/post")
async def post_video_to_tiktok(req: VideoPostRequest):
    """Post a completed video to TikTok."""
    result = _pipeline_results.get(req.job_id)
    if not result or result.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    video_url = result.get("video_url", "")
    # Strip any prefix to get just the filename
    video_filename = video_url
    for prefix in ("/api/tiktok/static/videos/", "/static/videos/", "/storage/videos/"):
        if video_filename.startswith(prefix):
            video_filename = video_filename[len(prefix):]
            break
    video_path = VIDEOS_DIR / video_filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    meta = result.get("metadata", {})
    hook = meta.get("hook", "") or meta.get("product_name", "Check this out!")
    caption = req.caption or hook
    if req.affiliate_link:
        caption += f"\n\n🔗 {req.affiliate_link}"

    acct = _get_tiktok_account(req.account_id.lstrip("@"))
    if not acct or not acct.get("session_token"):
        raise HTTPException(status_code=400, detail="No session token for account")

    os.environ["TIKTOK_SESSION"] = acct["session_token"]
    try:
        from simple_tiktok_uploader import upload
        upl_result = upload(str(video_path), caption)
        post_id = getattr(upl_result, "id", "") or getattr(upl_result, "video_id", "")
        return {"success": True, "video_id": post_id, "account_id": req.account_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# ─── Payment & Profile Proxies ────────────────────────────────────────────
@router.post("/tiktok/cookies")
async def tiktok_save_cookies(req: dict):
    """Save TikTok session cookies for cookie-based posting."""
    cookies = req.get("cookies", req)
    if not cookies:
        raise HTTPException(status_code=400, detail="cookies required")
    tiktok_poster.save_cookies(cookies)
    return {"success": True, "method": "cookie", "message": "Cookies saved"}

@router.get("/tiktok/cookies/status")
async def tiktok_cookies_status():
    """Check if TikTok cookies are available."""
    has = tiktok_poster.has_cookies()
    return {"success": True, "has_cookies": has, "method": "cookie" if has else "aitoearn"}


# ═══════════════════════════════════════════════════════════════════════════
# MONITOR ROUTES — Performance tracking & content strategy optimization
