"""Scout routes — trend intelligence & competitive analysis."""
from fastapi import APIRouter, HTTPException, Query

from scout import targets as scout_targets_mod
from scout import trends as scout_trends_mod
from scout import templates as scout_templates_mod
from monitor import tracker as monitor_tracker

router = APIRouter(tags=["scout"])
@router.get("/scout/targets")
async def scout_list_targets():
    """List all tracked competitor accounts."""
    return {"targets": await scout_targets_mod.list_targets()}


@router.post("/scout/targets")
async def scout_create_target(req: dict):
    """Add a target account to track."""
    return await scout_targets_mod.create_target(req)


@router.get("/scout/targets/{target_id}")
async def scout_get_target(target_id: int):
    """Get target account details with clips."""
    t = await scout_targets_mod.get_target(target_id)
    if not t:
        raise HTTPException(404, "Target not found")
    return t


@router.post("/scout/targets/{target_id}/delete")
async def scout_delete_target(target_id: int):
    """Delete a target account."""
    await scout_targets_mod.delete_target(target_id)
    return {"success": True}


@router.post("/scout/targets/analyze")
async def scout_analyze_targets(req: dict):
    """Batch analyze multiple targets."""
    target_ids = req.get("target_ids", [])
    return await scout_targets_mod.batch_analyze_targets(target_ids)


@router.post("/scout/targets/{target_id}/clips")
async def scout_add_clip(target_id: int, req: dict):
    """Add a clip to a target account."""
    result = await scout_targets_mod.add_clip(target_id, req)
    if not result:
        raise HTTPException(404, "Target not found")
    return result


@router.post("/scout/targets/{target_id}/clone")
async def scout_clone_target(target_id: int, req: dict):
    """Generate clone script from a target's content."""
    t = await scout_targets_mod.get_target(target_id)
    if not t:
        raise HTTPException(404, "Target not found")
    product_name = req.get("product_name", "สินค้า")
    fill_values = req.get("fill_values", {})
    # Use first target clip as source if available
    if t.get("clips"):
        clip = t["clips"][0]
        return await scout_templates_mod.generate_clone_script(
            source_template_id=clip.get("template_id", "problem_solution"),
            product_name=product_name,
            fill_values=fill_values,
        )
    return await scout_templates_mod.generate_from_template(
        template_id="problem_solution",
        product_name=product_name,
        fill_values=fill_values,
    )


@router.get("/scout/trends")
async def scout_trends(category: str = "", keyword: str = "", limit: int = Query(10, ge=1, le=50)):
    """Discover trending content patterns."""
    return {"trends": await scout_trends_mod.discover_trends(category=category, keyword=keyword, limit=limit)}


@router.get("/scout/templates")
async def scout_templates_list(category: str = ""):
    """List content templates."""
    return {"templates": await scout_templates_mod.get_templates(category=category)}


@router.post("/scout/templates/generate")
async def scout_templates_generate(req: dict):
    """Generate a script from a template."""
    result = await scout_templates_mod.generate_from_template(
        template_id=req.get("template_id", "problem_solution"),
        product_name=req.get("product_name", "สินค้า"),
        price=req.get("price", ""),
        fill_values=req.get("fill_values", {}),
        cta=req.get("cta", "กด link in bio"),
    )
    if not result:
        raise HTTPException(404, "Template not found")
    return result


@router.get("/tiktok/published")
async def tiktok_published(account_id: str = "", limit: int = Query(50, ge=1, le=500)):
    """Get published TikTok videos."""
    return {"videos": await monitor_tracker.get_published_videos(account_id=account_id, limit=limit)}
