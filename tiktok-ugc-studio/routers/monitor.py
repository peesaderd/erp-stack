"""Monitor routes — performance tracking & strategy."""
from fastapi import APIRouter, Query

from monitor import tracker as monitor_tracker
from monitor import optimizer as monitor_optimizer

router = APIRouter(tags=["monitor"])
@router.get("/monitor/performance")
async def monitor_performance(hours: int = Query(168, ge=1, le=8760), account_id: str = ""):
    """Get performance summary for a time window."""
    return await monitor_tracker.compute_performance_summary(account_id=account_id, hours=hours)


@router.get("/monitor/videos")
async def monitor_videos(account_id: str = "", limit: int = Query(50, ge=1, le=500)):
    """Get published videos list."""
    return {"videos": await monitor_tracker.get_published_videos(account_id=account_id, limit=limit)}


@router.get("/monitor/strategy")
async def monitor_get_strategy():
    """Get current content strategy."""
    return {"strategy": await monitor_optimizer.get_strategy()}


@router.post("/monitor/optimize")
async def monitor_optimize(req: dict):
    """Analyze performance and optimize strategy."""
    hours = req.get("hours", 168)
    perf = await monitor_tracker.compute_performance_summary(hours=hours)
    return await monitor_optimizer.analyze_and_optimize({"summary": perf})


@router.post("/monitor/strategy/reset")
async def monitor_reset_strategy():
    """Reset strategy to defaults."""
    return {"strategy": await monitor_optimizer.reset_strategy()}


# ═══════════════════════════════════════════════════════════════════════════
# SCOUT ROUTES — Trend intelligence & competitive analysis
# ═══════════════════════════════════════════════════════════════════════════

from scout import targets as scout_targets_mod
from scout import trends as scout_trends_mod
from scout import templates as scout_templates_mod

