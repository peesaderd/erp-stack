"""Product analysis route (moved from main.py, Phase B — move-only)."""
from fastapi import APIRouter

router = APIRouter(tags=["product"])


@router.post("/api/v1/product/analyze")
async def analyze_product(req: dict):
    """Analyze product using AI (Gemini/Mistral). Forward to pipeline service."""
    from video.gemini_agent import analyze_product
    result = analyze_product(
        product_name=req.get("product_name", ""),
        description=req.get("description", ""),
        category=req.get("category", ""),
        target_audience=req.get("target_audience", ""),
        age_group=req.get("age_group") or req.get("age", "") or None,
        gender=req.get("gender", ""),
        image_url=req.get("image_url", ""),
        image_base64=req.get("image_base64", ""),
    )
    return {"success": True, "analysis": result}
