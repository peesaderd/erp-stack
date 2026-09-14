"""Script generation routes (moved from main.py, Phase B — move-only)."""
from fastapi import APIRouter

from .deps import ScriptRequest, UGCRequest, AffiliateScriptRequest

router = APIRouter(tags=["scripts"])


@router.post("/api/v1/scripts/generate")
async def generate_script(req: ScriptRequest):
    """Generate TikTok UGC review script using AI."""
    from video.script_gen import generate_tiktok_review_script
    result = generate_tiktok_review_script(
        product_name=req.product_name,
        customer_problem=req.customer_problem,
        main_benefit=req.main_benefit,
        target_audience=req.target_audience,
        tone=req.tone,
        cta=req.cta,
        duration=req.duration,
        extra_rules=req.extra_rules,
        features=req.features,
        product_appearance=req.product_appearance,
        style=req.style,
        persona_category=req.category,
    )
    return {"success": True, "script": result}


@router.post("/api/v1/scripts/ugc")
async def generate_ugc_script(req: UGCRequest):
    """Generate UGC-style script."""
    from video.script_gen import generate_ugc_script
    result = generate_ugc_script(
        style=req.style,
        product_name=req.product_name,
        product_desc=req.product_desc,
        gender=req.gender,
        age=req.age,
        scene=req.scene,
    )
    return {"success": True, "script": result, "style": req.style}


@router.get("/api/v1/scripts/variations")
async def get_script_variations():
    """List available script variation templates."""
    from video.script_gen import get_script_variations
    return {"success": True, "variations": get_script_variations()}


@router.get("/api/v1/scripts/templates")
async def list_script_templates():
    """List all available script templates."""
    from video.script_gen import SCRIPT_TEMPLATES
    return {"success": True, "templates": SCRIPT_TEMPLATES}


@router.post("/api/v1/scripts/affiliate")
async def generate_affiliate_script(req: AffiliateScriptRequest):
    """Generate script with affiliate links."""
    from video.script_gen import generate_tiktok_review_script
    script = generate_tiktok_review_script(
        product_name=req.product_name,
        customer_problem=req.customer_problem,
        main_benefit=req.main_benefit,
        target_audience=req.target_audience,
        tone=req.tone,
        cta=req.cta,
        duration=req.duration,
        extra_rules=req.extra_rules + "\nInclude affiliate links",
    )
    return {"success": True, "script": script, "platforms": req.platforms}


@router.get("/api/v1/affiliate/config")
async def get_affiliate_config():
    return {"success": True, "config": {}}
