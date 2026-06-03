"""
TikTok UGC Studio — Micro Service
AI UGC Video Script Generator + AI Video Generation
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tiktok-ugc")

app = FastAPI(
    title="TikTok UGC Studio",
    version="0.1.0",
    description="AI UGC Video Script Generator + Video Generation Pipeline",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pydantic Models ───────────────────────────────────────────────────────

class ScriptRequest(BaseModel):
    product_name: str
    customer_problem: str = ""
    main_benefit: str = ""
    target_audience: str = ""
    tone: str = ""
    cta: str = ""
    duration: str = "8s"
    extra_rules: str = ""


class UGCRequest(BaseModel):
    style: str = "ugc_review"  # holding_product, product_usage, ugc_review
    product_name: str
    product_desc: str = ""
    gender: str = "female"
    age: str = "25-35"
    scene: str = "home"


class VideoRequest(BaseModel):
    prompt: str
    provider: str = "kling"
    model_tier: str = "standard"
    duration: int = 8
    aspect_ratio: str = "9:16"
    image_url: Optional[str] = None
    script: Optional[str] = None
    ugc_style: Optional[str] = None


class VideoTaskRequest(BaseModel):
    provider: str
    task_id: str


class QueueVideoRequest(BaseModel):
    prompt: str
    provider: str = "wavespeed"
    model_tier: str = "standard"
    duration: int = 8
    aspect_ratio: str = "9:16"
    image_url: Optional[str] = None
    face_image_url: Optional[str] = None
    webhook_url: Optional[str] = None


class TaskStatusRequest(BaseModel):
    task_id: str


class AffiliateConfig(BaseModel):
    # Platform affiliate link configs
    shopee_url: Optional[str] = None
    lazada_url: Optional[str] = None
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None


class AffiliateScriptRequest(ScriptRequest):
    """Script generation with affiliate links"""
    platforms: list[str] = []  # e.g. ["shopee", "lazada", "facebook", "tiktok"]


class ProductAnalysisRequest(BaseModel):
    product_name: str
    description: str
    category: Optional[str] = ""
    target_audience: Optional[str] = ""
    image_url: Optional[str] = None
    image_base64: Optional[str] = None  # base64-encoded image for vision


# ─── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "tiktok-ugc-studio", "version": "0.1.0"}


# ─── Script Generation Endpoints ──────────────────────────────────────────

@app.post("/scripts/generate")
def generate_script(req: ScriptRequest):
    """Generate TikTok review script using AiBot prompt system"""
    from script_gen import generate_tiktok_review_script
    try:
        result = generate_tiktok_review_script(
            product_name=req.product_name,
            customer_problem=req.customer_problem,
            main_benefit=req.main_benefit,
            target_audience=req.target_audience,
            tone=req.tone,
            cta=req.cta,
            duration=req.duration,
            extra_rules=req.extra_rules,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scripts/ugc")
def generate_ugc_script(req: UGCRequest):
    """Generate UGC video prompt by style"""
    from script_gen import generate_ugc_script
    try:
        result = generate_ugc_script(
            style=req.style,
            product_name=req.product_name,
            gender=req.gender,
            age=req.age,
            scene=req.scene,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scripts/variations")
def script_variations():
    """Get available hook/tone/CTA variations"""
    from script_gen import get_script_variations
    return get_script_variations()


@app.get("/scripts/templates")
def script_templates():
    """List available script templates and UGC styles"""
    from script_gen import SCRIPT_TEMPLATES
    return {
        "durations": ["8s", "16s"],
        "ugc_styles": ["holding_product", "product_usage", "ugc_review"],
        "templates": {
            k: {
                "hook": v["hook"],
                "value": v["value"],
                "cta": v["cta"],
            }
            for k, v in SCRIPT_TEMPLATES.items()
        },
    }


# ─── Video Generation Endpoints ───────────────────────────────────────────

@app.post("/video/generate")
def generate_video(req: VideoRequest):
    """Start video generation task"""
    from video_gen import generate_video, build_video_prompt, VideoProvider

    prompt = req.prompt

    # If script is provided, build a video prompt from it
    if req.script and req.ugc_style:
        prompt = build_video_prompt(req.script, req.ugc_style)

    try:
        provider = VideoProvider(req.provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    try:
        result = generate_video(
            prompt=prompt,
            provider=provider,
            model_tier=req.model_tier,
            duration=req.duration,
            aspect_ratio=req.aspect_ratio,
            image_url=req.image_url,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/video/status")
def video_status(req: VideoTaskRequest):
    """Check video generation status"""
    from video_gen import check_status, VideoProvider

    try:
        provider = VideoProvider(req.provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    try:
        result = check_status(provider, req.task_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/video/providers")
def video_providers():
    """List available and configured video providers"""
    from video_gen import get_available_providers, UGC_PRESETS

    return {
        "providers": get_available_providers(),
        "ugc_styles": list(UGC_PRESETS.keys()),
        "aspect_ratios": ["9:16", "16:9", "1:1"],
        "durations": [5, 8, 10, 15, 30, 60],
    }


# ─── Prompts Management ───────────────────────────────────────────────────

@app.get("/prompts/list")
def list_prompts():
    """List available prompt files in the system"""
    from pathlib import Path
    prompts_dir = Path(__file__).parent / "prompts"

    files = []
    for f in sorted(prompts_dir.rglob("*")):
        if f.is_file() and f.suffix in (".txt", ".json", ".prompt"):
            rel = f.relative_to(prompts_dir)
            files.append({
                "path": str(rel),
                "size": f.stat().st_size,
                "content_preview": f.read_text(encoding="utf-8")[:200],
            })

    return {"total": len(files), "files": files}


@app.get("/prompts/{path:path}")
def get_prompt(path: str):
    """Get a specific prompt file by path"""
    from pathlib import Path
    full_path = (Path(__file__).parent / "prompts" / path).resolve()
    prompts_dir = Path(__file__).parent / "prompts"

    if not str(full_path).startswith(str(prompts_dir.resolve())):
        raise HTTPException(status_code=403, detail="Path outside prompts directory")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Prompt not found")

    return {
        "path": path,
        "size": full_path.stat().st_size,
        "content": full_path.read_text(encoding="utf-8"),
    }


# ─── Affiliate Integration ───────────────────────────────────────────────

AFFILIATE_CONFIG = {
    "shopee": AffiliateConfig(shopee_url=os.environ.get("AFFILIATE_SHOPEE_URL", "https://shopee.co.th")),
    "lazada": AffiliateConfig(lazada_url=os.environ.get("AFFILIATE_LAZADA_URL", "https://lazada.co.th")),
    "facebook": AffiliateConfig(facebook_url=os.environ.get("AFFILIATE_FACEBOOK_URL", "https://facebook.com/marketplace")),
    "tiktok": AffiliateConfig(tiktok_url=os.environ.get("AFFILIATE_TIKTOK_URL", "https://tiktok.com/shop")),
}


@app.post("/scripts/generate-with-affiliate")
def generate_script_with_affiliate(req: AffiliateScriptRequest):
    """Generate TikTok script + affiliate links"""
    from script_gen import generate_tiktok_review_script
    try:
        script = generate_tiktok_review_script(
            product_name=req.product_name,
            customer_problem=req.customer_problem,
            main_benefit=req.main_benefit,
            target_audience=req.target_audience,
            tone=req.tone,
            cta=req.cta or "กดลิงก์ด้านล่าง",
            duration=req.duration,
            extra_rules=req.extra_rules,
        )
        # Build affiliate links for requested platforms
        affiliate_links = {}
        for p in req.platforms:
            if p in AFFILIATE_CONFIG:
                cfg = AFFILIATE_CONFIG[p]
                url = getattr(cfg, f"{p}_url", f"https://{p}.com")
                affiliate_links[p] = url
        
        script["affiliate_links"] = affiliate_links
        if affiliate_links:
            platforms_str = ", ".join(a.title() for a in affiliate_links.keys())
            script["script"] += f"\n\n🛒 สั่งซื้อได้ที่: {platforms_str}"
            script["affiliate_cta"] = f"Check out on {', '.join(affiliate_links.keys())}!"
        return script
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/affiliate/config")
def get_affiliate_config():
    """Get current affiliate link configuration"""
    return {
        k: {"url": getattr(v, f"{k}_url", "")}
        for k, v in AFFILIATE_CONFIG.items()
    }


# ─── Task Queue ────────────────────────────────────────────────────────────

@app.post("/video/queue")
def queue_video(req: QueueVideoRequest):
    """Enqueue video generation task (background), returns task_id immediately"""
    from video_gen import enqueue_video_task
    try:
        task_id = enqueue_video_task(
            prompt=req.prompt,
            provider=req.provider,
            model_tier=req.model_tier,
            duration=req.duration,
            aspect_ratio=req.aspect_ratio,
            image_url=req.image_url,
            face_image_url=req.face_image_url,
        )
        return {"task_id": task_id, "status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/video/queue-status")
def queue_status(req: TaskStatusRequest):
    """Check queued task status"""
    from video_gen import get_task_status
    try:
        result = get_task_status(req.task_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Video with Fallback ───────────────────────────────────────────────────

@app.post("/video/generate-with-fallback")
def generate_video_with_fallback(req: VideoRequest):
    """Generate video with automatic provider fallback chain"""
    from video_gen import generate_video_with_fallback, build_video_prompt
    prompt = req.prompt
    if req.script and req.ugc_style:
        prompt = build_video_prompt(req.script, req.ugc_style)
    try:
        result = generate_video_with_fallback(
            prompt=prompt,
            duration=req.duration,
            aspect_ratio=req.aspect_ratio,
            image_url=req.image_url,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ─── Product Analysis ───────────────────────────────────────────────────────

@app.post("/product/analyze")
def analyze_product(req: ProductAnalysisRequest):
    """Analyze product via Gemini — returns image prompts, video prompt, hooks, copy"""
    from gemini_agent import analyze_product
    try:
        result = analyze_product(
            product_name=req.product_name,
            description=req.description,
            category=req.category or "",
            target_audience=req.target_audience or "",
            image_url=req.image_url,
            image_base64=req.image_base64,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ─── Stats ─────────────────────────────────────────────────────────────────

@app.get("/stats")
def stats():
    return {
        "service": "tiktok-ugc-studio",
        "version": "0.1.0",
        "prompts_loaded": True,
    }
