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


# ─── Stats ─────────────────────────────────────────────────────────────────

@app.get("/stats")
def stats():
    return {
        "service": "tiktok-ugc-studio",
        "version": "0.1.0",
        "prompts_loaded": True,
    }
