"""AitoEarn routes — campaigns, accounts, earnings, affiliate links."""
from fastapi import APIRouter, HTTPException

from pipeline_db import get_job, enrich_from_logs
from connect.aitoearn_client import client as aitoearn

router = APIRouter(tags=["aitoearn"])
@router.get("/aitoearn/accounts")
async def aitoearn_accounts(platform: str = None):
    """List connected AitoEarn channel accounts."""
    if not aitoearn.configured:
        return {"success": False, "error": "AITOEARN_API_KEY not configured", "accounts": []}
    accounts = await aitoearn.list_accounts(platform=platform)
    return {"success": True, "accounts": accounts, "count": len(accounts)}

@router.get("/aitoearn/platforms")
async def aitoearn_platforms():
    """Get grouped connected platforms with their accounts."""
    if not aitoearn.configured:
        return {"success": False, "error": "AITOEARN_API_KEY not configured", "platforms": []}
    platforms = await aitoearn.get_connected_platforms()
    return {"success": True, "platforms": platforms, "total_platforms": len(platforms)}

@router.get("/aitoearn/accounts/{account_id}")
async def aitoearn_account_detail(account_id: str):
    """Get single account detail."""
    account = await aitoearn.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"success": True, "account": account}

@router.get("/aitoearn/connect/{platform}")
async def aitoearn_connect_start(platform: str, redirect_uri: str = ""):
    """Start OAuth for a platform. Returns auth URL to open in popup."""
    if not aitoearn.configured:
        raise HTTPException(status_code=503, detail="AITOEARN_API_KEY not configured")
    result = await aitoearn.start_oauth(platform, redirect_uri=redirect_uri)
    return result

@router.get("/aitoearn/connect/{platform}/status/{session_id}")
async def aitoearn_connect_status(platform: str, session_id: str):
    """Check OAuth session status."""
    result = await aitoearn.check_oauth_status(platform, session_id)
    return result

@router.get("/aitoearn/status")
async def aitoearn_status():
    """AitoEarn connection status — shows API key configured, connected platforms."""
    if not aitoearn.configured:
        return {"success": True, "connected": False, "reason": "AITOEARN_API_KEY not configured"}
    try:
        platforms = await aitoearn.get_connected_platforms()
        total_accounts = sum(p["count"] for p in platforms)
        return {
            "success": True,
            "connected": True,
            "api_configured": True,
            "platforms": platforms,
            "total_accounts": total_accounts,
        }
    except Exception as e:
        return {"success": False, "connected": False, "error": str(e)}

@router.get("/aitoearn/campaigns")
async def aitoearn_campaigns():
    """Get active AitoEarn campaigns."""
    campaigns = await aitoearn.get_active_campaigns()
    return {"success": True, "campaigns": campaigns, "count": len(campaigns)}

@router.get("/aitoearn/earnings")
async def aitoearn_earnings(period: str = "30d"):
    """Get AitoEarn earnings summary."""
    data = await aitoearn.get_earnings(period=period)
    return {"success": True, "data": data}

@router.get("/aitoearn/affiliate-link")
async def aitoearn_affiliate_link(product_name: str = "", product_url: str = ""):
    """Get affiliate link for a product."""
    link = await aitoearn.get_affiliate_link(product_name=product_name, product_url=product_url)
    return {"success": True, "affiliate_link": link}

@router.post("/aitoearn/sync-job/{job_id}")
async def aitoearn_sync_job(job_id: str):
    """Sync a completed pipeline job with AitoEarn."""
    from pipeline_db import get_job, enrich_from_logs
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job = enrich_from_logs(job)
    # Get affiliate link
    product_name = job.get("logs", {}).get("product_title", "")
    link = await aitoearn.get_affiliate_link(product_name=product_name) if product_name else None
    return {"success": True, "job_id": job_id, "sync": {"affiliate_link": link}}


# ═══════════════════════════════════════════════════════════════════════════
# PUBLISHER ROUTES — Post Queue + Scheduler + Calendar
# ═══════════════════════════════════════════════════════════════════════════
