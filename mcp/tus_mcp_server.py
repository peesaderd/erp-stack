"""
TikTok UGC Studio (TUS) MCP Server — stdio mode for AI Agent access
====================================================================
ให้ AI Agents (OpenClaw) สามารถสร้างและจัดการ TUS video generation jobs
ผ่าน MCP Protocol

TUS API runs on port 8105 (tiktok-ugc-studio).

Usage:
  python3 tus_mcp_server.py          # stdio mode
  python3 tus_mcp_server.py --http   # SSE mode

For OpenClaw config (mcp.servers):
  "tus": {
    "command": "python3",
    "args": ["/home/openhands/erp-stack/mcp/tus_mcp_server.py"]
  }
"""

import json, os, sys, logging, uuid, asyncio
from typing import Optional
from contextlib import asynccontextmanager

import httpx

# ═══════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════

TUS_URL = "http://localhost:8105"
DEFAULT_TIMEOUT = 300  # TUS pipeline can take minutes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tus-mcp")

# ═══════════════════════════════════════════════════════════════
# FastMCP Server
# ═══════════════════════════════════════════════════════════════

from mcp.server import FastMCP

mcp = FastMCP(
    "TikTok UGC Studio (TUS) MCP",
    instructions="""TikTok UGC Studio MCP Server — ให้ AI Agent สร้างวิดีโอ UGC ผ่าน TUS

Tools ที่มี:
  1. tus_create_video — สร้างวิดีโอสั้น (product_url + style)
  2. tus_create_full_pipeline — Full pipeline (prompt-builder + image + video + TTS + compose)
  3. tus_get_job — ดูรายละเอียดงานตาม job_id
  4. tus_list_jobs — ดูรายการ pipeline jobs ทั้งหมด
  5. tus_health — เช็คสถานะ TUS service
""",
)


# ═══════════════════════════════════════════════════════════════
# HTTP Helper
# ═══════════════════════════════════════════════════════════════

async def _tus_call(method: str, path: str, json_body: dict = None, timeout: float = 30.0) -> dict:
    """Make HTTP call to TUS API with error handling."""
    url = f"{TUS_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout), verify=False) as client:
            resp = await client.request(method, url, json=json_body)
            try:
                data = resp.json()
            except (json.JSONDecodeError, Exception):
                data = {"raw": resp.text, "status": resp.status_code}
            data["_http_status"] = resp.status_code
            return data
    except httpx.TimeoutException:
        return {"error": f"Request timed out after {timeout}s", "path": path, "_http_status": 0}
    except Exception as e:
        return {"error": str(e), "path": path, "_http_status": 0}


# ═══════════════════════════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def tus_create_video(
    product_url: str = "",
    product_title: str = "",
    product_image: str = "",
    ugc_style: str = "holding",
    duration: int = 15,
    aspect_ratio: str = "9:16",
    content_type: str = "affiliate",
    hook: str = "",
    value: str = "",
    cta: str = "",
    bgm_style: str = "",
    script: str = "",
) -> dict:
    """
    สร้างวิดีโอ UGC ผ่าน TUS (video/generate endpoint).
    
    Args:
        product_url: TikTok Shop product URL
        product_title: Product name (ถ้าไม่มี product_url)
        product_image: Product image URL
        ugc_style: รูปแบบ UGC — holding, unbox, review, talking_head, comparison
        duration: ความยาววิดีโอ (วินาที, default 15)
        aspect_ratio: 9:16, 1:1, 16:9
        content_type: affiliate, ugc, review
        hook: ข้อความ Hook
        value: ข้อความ Value proposition
        cta: ข้อความ Call-to-action
        bgm_style: chill_loft, informative_jazz, energetic_edm, upbeat_pop
        script: Script เนื้อหา (ไม่ต้องระบุให้ TUS gen ให้)
    """
    if not product_url and not product_title:
        return {"error": "ต้องระบุ product_url หรือ product_title อย่างใดอย่างหนึ่ง"}
    
    body = {
        "product_url": product_url,
        "product_title": product_title,
        "product_image": product_image,
        "ugc_style": ugc_style,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "content_type": content_type,
        "hook": hook,
        "value": value,
        "cta": cta,
        "bgm_style": bgm_style or None,
        "script": script or None,
    }
    
    logger.info(f"tus_create_video: product={product_title or product_url} style={ugc_style}")
    result = await _tus_call("POST", "/video/generate", json_body=body, timeout=DEFAULT_TIMEOUT)
    
    if result.get("_http_status") in (200, 201, 202):
        return {
            "ok": True,
            "job_id": result.get("job_id", ""),
            "status": result.get("status", "pending"),
            "message": f"สร้างวิดีโอสำเร็จ! Job ID: {result.get('job_id', '')}",
        }
    else:
        return {
            "ok": False,
            "error": result.get("detail", result.get("error", str(result))),
            "job_id": result.get("job_id", ""),
        }


@mcp.tool()
async def tus_create_full_pipeline(
    product_url: str = "",
    product_title: str = "",
    product_description: str = "",
    product_image: str = "",
    model_image: str = "",
    ugc_style: str = "holding",
    hook: str = "",
    value_proposition: str = "",
    cta: str = "",
    duration: int = 15,
    aspect_ratio: str = "9:16",
    provider: str = "prodia",
    negative_prompt: str = "",
    tts_lang: str = "th",
    bg_music: str = "",
    recipe: str = "tus",
    run_tts: bool = True,
    run_video_gen: bool = True,
    run_compose: bool = True,
) -> dict:
    """
    สร้างวิดีโอ UGC แบบ Full Pipeline (prompt-builder + image gen + video gen + TTS + compose).
    
    Args:
        product_url: TikTok Shop product URL
        product_title: Product name
        product_description: Product description
        product_image: Product image URL
        model_image: Model reference image URL
        ugc_style: รูปแบบ UGC (holding, unbox, review, talking_head, comparison)
        hook: ข้อความ Hook
        value_proposition: ข้อความ Value proposition
        cta: ข้อความ Call-to-action
        duration: ความยาววิดีโอ (วินาที)
        aspect_ratio: 9:16, 1:1, 16:9
        provider: prodia
        negative_prompt: คำสั่งลบสำหรับ image gen
        tts_lang: ภาษา th/en
        bg_music: แนวเพลงพื้นหลัง
        recipe: tus, tus_novoice
        run_tts: สร้างเสียงพากย์หรือไม่
        run_video_gen: สร้างวิดีโอหรือไม่
        run_compose: รวมคลิปหรือไม่
    """
    body = {
        "product_url": product_url or None,
        "product_title": product_title or None,
        "product_description": product_description or None,
        "product_image": product_image or None,
        "model_image": model_image or None,
        "ugc_style": ugc_style,
        "hook": hook or None,
        "value_proposition": value_proposition or None,
        "cta": cta or None,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "provider": provider,
        "negative_prompt": negative_prompt or None,
        "tts_lang": tts_lang,
        "bg_music": bg_music or None,
        "recipe": recipe or None,
        "run_tts": run_tts,
        "run_video_gen": run_video_gen,
        "run_compose": run_compose,
    }
    
    logger.info(f"tus_create_full_pipeline: product={product_title or product_url} style={ugc_style}")
    result = await _tus_call("POST", "/pipeline/run", json_body=body, timeout=DEFAULT_TIMEOUT)
    
    if result.get("_http_status") in (200, 201, 202):
        return {
            "ok": True,
            "job_id": result.get("job_id", ""),
            "status": result.get("status", "pending"),
            "message": f"Pipeline started! Job ID: {result.get('job_id', '')}",
        }
    else:
        return {
            "ok": False,
            "error": result.get("detail", result.get("error", str(result))),
        }


@mcp.tool()
async def tus_get_job(job_id: str) -> dict:
    """
    ดูรายละเอียดของ pipeline job.
    
    Args:
        job_id: Job ID (เช่น vid_e06f76da)
    """
    result = await _tus_call("GET", f"/pipeline/detail/{job_id}")
    
    job = result.get("job", result)
    return {
        "job_id": job_id,
        "status": job.get("status", "unknown"),
        "product_title": job.get("product_title", ""),
        "video_url": job.get("video_url", ""),
        "video_web_url": job.get("logs", {}).get("video_web_url", ""),
        "error_message": job.get("logs", {}).get("error_message", ""),
        "steps": {
            name: s.get("status", "?")
            for name, s in job.get("steps", {}).items()
        },
        "created_at": job.get("created_at", ""),
        "updated_at": job.get("updated_at", ""),
    }


@mcp.tool()
async def tus_list_jobs(limit: int = 20) -> dict:
    """
    ดูรายการ pipeline jobs ทั้งหมด.
    
    Args:
        limit: จำนวนงานที่ต้องการดู (default 20)
    """
    result = await _tus_call("GET", f"/pipeline/list?limit={limit}")
    
    jobs = result.get("jobs", [])
    summary = []
    for j in jobs:
        summary.append({
            "job_id": j.get("job_id", ""),
            "status": j.get("status", "?"),
            "product_title": j.get("product_title", "")[:60],
            "created_at": j.get("created_at", ""),
        })
    
    return {
        "ok": True,
        "count": len(summary),
        "jobs": summary,
    }


@mcp.tool()
async def tus_health() -> dict:
    """
    เช็คสถานะ TUS service ว่าทำงานอยู่หรือไม่.
    """
    result = await _tus_call("GET", "/health")
    return {
        "ok": result.get("status") == "ok" or result.get("ok") or result.get("_http_status") == 200,
        "service": "tiktok-ugc-studio",
        "status": result.get("status", "unknown"),
        "version": result.get("version", ""),
    }


# ═══════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--http" in sys.argv:
        port = int(sys.argv[sys.argv.index("--http") + 1]) if "--http" in sys.argv and sys.argv.index("--http") + 1 < len(sys.argv) else 8201
        logger.info(f"Starting TUS MCP Server (HTTP/SSE) on port {port}...")
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        logger.info("Starting TUS MCP Server (stdio)...")
        mcp.run(transport="stdio")
