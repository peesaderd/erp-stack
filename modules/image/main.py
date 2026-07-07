"""
Image Generation Module — Microservice
=======================================
Nano Banana img2img + Mistral Pixtral Vision สำหรับวิเคราะห์รูปสินค้า
Part of Business OS, registered with ERP Modular.

Port: 8110
"""

import os
import sys
import json
import uuid
import time
import logging
import requests
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn

# Add erp-stack to path for shared_config
_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from shared_config import PRODIA_TOKEN, MISTRAL_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("image-module")

# ─── Config ────────────────────────────────────────────────

STORAGE_DIR = Path(__file__).parent / "storage" / "images"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

PRODIA_BASE = "https://inference.prodia.com/v2"
PORT = int(os.environ.get("PORT", "8110"))

app = FastAPI(
    title="Image Generation Module",
    version="3.0.0",
    description="Nano Banana img2img + Mistral Pixtral Vision สำหรับวิเคราะห์รูปสินค้า"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ──────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str = ""
    negative_prompt: Optional[str] = None
    aspectRatio: Optional[str] = "9:16"
    modelTier: Optional[str] = "nano.banana"  # ใช้ Nano Banana เป็นหลัก
    provider: Optional[str] = "prodia"
    count: Optional[int] = 1
    thaiModel: Optional[bool] = True
    inputImage: Optional[str] = ""  # URL หรือ path ของรูปสินค้า
    image_url: Optional[str] = ""
    width: Optional[int] = 512
    height: Optional[int] = 896
    upscale: Optional[bool] = False


# ─── Helpers ────────────────────────────────────────────────

ASPECT_MAP = {
    "1:1": (1024, 1024),
    "9:16": (512, 896),
    "16:9": (896, 512),
    "4:5": (800, 960),
    "3:4": (768, 1024),
    "4:3": (1024, 768),
}


def _save_image(image_data: bytes, prefix: str = "prodia") -> str:
    ext = "png"
    filename = f"{prefix}_{uuid.uuid4().hex[:12]}.{ext}"
    filepath = STORAGE_DIR / filename
    with open(filepath, "wb") as f:
        f.write(image_data)
    logger.info(f"Saved: {filepath}")
    return f"/storage/images/{filename}"


def _prodia_headers():
    return {"Authorization": f"Bearer {PRODIA_TOKEN()}"}


def _download_image(url_or_path: str) -> bytes:
    """ดาวน์โหลดรูปจาก URL หรืออ่านจาก path"""
    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        resp = requests.get(url_or_path, timeout=30)
        resp.raise_for_status()
        return resp.content
    else:
        with open(url_or_path, "rb") as f:
            return f.read()


def _poll_job(job_url: str, max_polls: int = 60, sleep_s: int = 2) -> dict:
    """Poll a Prodia v2 job URL until completed."""
    for attempt in range(max_polls):
        time.sleep(sleep_s)
        try:
            resp = requests.get(job_url, headers=_prodia_headers(), timeout=30)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception as e:
            logger.debug(f"Poll attempt {attempt}: {e}")
            continue

        status = data.get("status", "")

        if status in ("completed", "success"):
            return data
        elif status in ("failed", "error"):
            raise RuntimeError(f"Prodia job failed: {data}")
        # else: "processing", "queued" — keep polling

    raise TimeoutError("Prodia job timed out after 120s")


def _extract_output_urls(data: dict) -> list:
    """Extract image URLs from Prodia job result in various formats."""
    urls = []
    output = data.get("output", [])
    if isinstance(output, list):
        urls.extend(output)
    elif isinstance(output, str):
        urls.append(output)

    for key in ("imageUrl", "result", "image_url", "url"):
        val = data.get(key)
        if val and isinstance(val, str):
            urls.append(val)

    return urls


# ─── Prodia v2 API — Nano Banana img2img ─────────────────────

def prodia_generate_img2img(
    prompt: str,
    input_image: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 896,
) -> dict:
    """
    Generate image via Nano Banana img2img (Prodia v2 API).
    ใช้รูปสินค้าเป็น input เพื่อสร้างรูป UGC ที่ตรงตามสินค้า
    
    Note: img2img ใช้เวลานานกว่า txt2img (3-5 นาที)
    """
    job_type = "inference.nano-banana.img2img.v1"

    # ดาวน์โหลดรูปสินค้า
    image_data = _download_image(input_image)

    config = {
        "type": job_type,
        "config": {
            "prompt": prompt,
            "negative_prompt": negative_prompt[:500],
            "width": width,
            "height": height,
        }
    }

    files = [
        ("job", ("job.json", json.dumps(config), "application/json")),
        ("input", ("image.png", image_data, "image/png")),
    ]

    logger.info(f"Nano Banana img2img | {prompt[:60]}... | {width}x{height}")
    logger.info(f"  Input image: {input_image[:60]}...")

    resp = requests.post(
        f"{PRODIA_BASE}/job",
        files=files,
        headers=_prodia_headers(),
        timeout=120
    )

    # Prodia v2 API returns 400 with JSON body for queued jobs (not 200!)
    data = {}
    job_id = None
    
    if resp.status_code == 200:
        # Direct image response
        ct = resp.headers.get("content-type", "")
        if "image" in ct:
            path = _save_image(resp.content)
            return {"ok": True, "images": [{"url": path, "full_url": f"http://localhost:{PORT}{path}"}], "provider": "prodia"}
        data = resp.json() if resp.text.strip() else {}
    elif resp.status_code == 400:
        try:
            data = resp.json()
        except:
            logger.error(f"Prodia non-JSON 400: {resp.text[:200]}")
            raise HTTPException(status_code=502, detail=f"Prodia error: {resp.text[:200]}")
    else:
        logger.error(f"Prodia submit error {resp.status_code}: {resp.text[:200]}")
        raise HTTPException(status_code=502, detail=f"Prodia submit error: {resp.text[:200]}")

    job_id = data.get("id") or data.get("job")
    if not job_id:
        logger.error(f"No job_id. Data: {json.dumps(data)[:200]}")
        raise HTTPException(status_code=502, detail=f"No job_id in response")

    logger.info(f"Job submitted: {job_id}")

    # Poll for completion (เพิ่ม timeout เป็น 5 นาทีสำหรับ img2img)
    status_url = f"{PRODIA_BASE}/job/{job_id}"
    try:
        result_data = _poll_job(status_url, max_polls=150, sleep_s=2)  # 5 นาที
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))

    # Get images
    image_urls = _extract_output_urls(result_data)
    logger.info(f"Job {job_id}: {len(image_urls)} output images")

    results = []
    for img_url in image_urls:
        try:
            img_resp = requests.get(img_url, timeout=30)
            if img_resp.status_code == 200:
                path = _save_image(img_resp.content)
                results.append({
                    "url": path,
                    "full_url": f"http://localhost:{PORT}{path}",
                })
        except Exception as e:
            logger.warning(f"Failed to download {img_url}: {e}")

    return {
        "ok": True,
        "images": results,
        "job_id": job_id,
        "provider": "prodia",
        "model": "nano.banana",
    }


def prodia_generate_txt2img(
    prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 896,
) -> dict:
    """
    Generate image via txt2img (ไม่มี input image).
    ใช้เมื่อไม่มีรูปสินค้าให้
    """
    job_type = "inference.flux-2.dev.txt2img.v1"

    config = {
        "type": job_type,
        "config": {
            "prompt": prompt,
            "negative_prompt": negative_prompt[:500],
            "width": width,
            "height": height,
        }
    }

    files = {
        "job": ("job.json", json.dumps(config), "application/json"),
    }

    logger.info(f"FLUX txt2img | {prompt[:60]}... | {width}x{height}")

    resp = requests.post(
        f"{PRODIA_BASE}/job",
        files=files,
        headers=_prodia_headers(),
        timeout=30
    )

    data = {}
    job_id = None
    
    if resp.status_code == 200:
        ct = resp.headers.get("content-type", "")
        if "image" in ct:
            path = _save_image(resp.content)
            return {"ok": True, "images": [{"url": path, "full_url": f"http://localhost:{PORT}{path}"}], "provider": "prodia"}
        data = resp.json() if resp.text.strip() else {}
    elif resp.status_code == 400:
        try:
            data = resp.json()
        except:
            logger.error(f"Prodia non-JSON 400: {resp.text[:200]}")
            raise HTTPException(status_code=502, detail=f"Prodia error: {resp.text[:200]}")
    else:
        logger.error(f"Prodia submit error {resp.status_code}: {resp.text[:200]}")
        raise HTTPException(status_code=502, detail=f"Prodia submit error: {resp.text[:200]}")

    job_id = data.get("id") or data.get("job")
    if not job_id:
        logger.error(f"No job_id. Data: {json.dumps(data)[:200]}")
        raise HTTPException(status_code=502, detail=f"No job_id in response")

    logger.info(f"Job submitted: {job_id}")

    # Poll for completion
    status_url = f"{PRODIA_BASE}/job/{job_id}"
    try:
        result_data = _poll_job(status_url)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))

    # Get images
    image_urls = _extract_output_urls(result_data)
    logger.info(f"Job {job_id}: {len(image_urls)} output images")

    results = []
    for img_url in image_urls:
        try:
            img_resp = requests.get(img_url, timeout=30)
            if img_resp.status_code == 200:
                path = _save_image(img_resp.content)
                results.append({
                    "url": path,
                    "full_url": f"http://localhost:{PORT}{path}",
                })
        except Exception as e:
            logger.warning(f"Failed to download {img_url}: {e}")

    return {
        "ok": True,
        "images": results,
        "job_id": job_id,
        "provider": "prodia",
        "model": "flux-2.dev",
    }


# ─── Mistral Pixtral Vision — วิเคราะห์รูปสินค้า ──────────────

def analyze_product_image(image_url: str) -> Dict[str, Any]:
    """
    ใช้ Mistral Pixtral (pixtral-large-2501) วิเคราะห์รูปสินค้า
    แทน Gemini Vision ที่มีปัญหา 401 error จาก API key format 'AQ.Ab8...'
    คืนค่า: product_name, category, description, features, colors, style, best_for
    """
    api_key = MISTRAL_API_KEY()
    if not api_key:
        raise ValueError("MISTRAL_API_KEY not set")

    prompt = """Analyze this product image. Return ONLY valid JSON in this exact structure (no markdown):
{
  "product_name": "product name in Thai if known",
  "category": "product category",
  "description": "brief 1-2 sentence description",
  "features": ["feature1", "feature2"],
  "colors": ["color1", "color2"],
  "style": "style/mood of product",
  "best_for": "target audience or usage"
}"""

    payload = {
        "model": "pixtral-large-2501",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": image_url}
            ]
        }],
        "temperature": 0.1,
        "max_tokens": 1024,
    }

    logger.info(f"Mistral Pixtral analyzing: {image_url[:60]}...")

    try:
        resp = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        text = data["choices"][0]["message"]["content"]

        # Parse JSON จากข้อความ (strip markdown code block ถ้ามี)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end+1]

        analysis = json.loads(text)
        logger.info(f"Analysis complete: {analysis.get('category', 'unknown')}")
        return analysis

    except Exception as e:
        logger.error(f"Mistral Pixtral analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")


# ─── Endpoints ────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "image-module",
        "version": "3.0.0",
        "provider": "prodia",
        "models": ["nano.banana (img2img)", "flux-2.dev (txt2img)"],
        "mistral_vision": True,
    }


@app.post("/api/v1/image/generate")
async def generate_image(req: GenerateRequest):
    """
    Generate image (หลัก: Nano Banana img2img, fallback: FLUX txt2img)
    
    ถ้ามี inputImage → ใช้ Nano Banana img2img (สร้างรูปจากสินค้า)
    ถ้าไม่มี inputImage → ใช้ FLUX txt2img (สร้างรูปจากข้อความอย่างเดียว)
    """
    w, h = req.width, req.height
    if not w or not h:
        ar = req.aspectRatio or "9:16"
        w, h = ASPECT_MAP.get(ar, (512, 896))

    prompt = req.prompt or ""
    neg = req.negative_prompt or "blurry, low quality, deformed, ugly, text, watermark"

    # ถ้ามี inputImage ให้ใช้ Nano Banana img2img
    if req.inputImage:
        try:
            result = prodia_generate_img2img(
                prompt=prompt,
                input_image=req.inputImage,
                negative_prompt=neg,
                width=w,
                height=h,
            )
            return result
        except Exception as e:
            logger.error(f"Nano Banana img2img failed: {e}")
            logger.info("Falling back to FLUX txt2img...")

    # ไม่มี inputImage หรือ img2img ล้มเหลว → ใช้ txt2img
    result = prodia_generate_txt2img(
        prompt=prompt,
        negative_prompt=neg,
        width=w,
        height=h,
    )
    return result


@app.post("/api/v1/image/analyze")
async def analyze_image(image_url: str):
    """
    วิเคราะห์รูปสินค้าด้วย Mistral Pixtral Vision
    คืนค่า: product_name, category, description, features, colors, style, best_for
    """
    if not image_url:
        raise HTTPException(400, "image_url required")
    
    analysis = analyze_product_image(image_url)
    return {"ok": True, "analysis": analysis}


@app.post("/api/v1/image/remove-bg")
async def remove_bg(image_url: str = ""):
    if not image_url:
        raise HTTPException(400, "image_url required")
    return {"ok": True, "image_url": image_url, "note": "bg-removal via Prodia not available, returning original"}


@app.post("/api/v1/image/edit")
async def edit_image(prompt: str = "", image_url: str = ""):
    if not image_url and not prompt:
        raise HTTPException(400, "prompt or image_url required")
    result = prodia_generate_txt2img(prompt=prompt or "edit")
    return result


@app.post("/api/v1/image/upscale")
async def upscale_image(image_url: str = ""):
    if not image_url:
        raise HTTPException(400, "image_url required")
    return {"ok": True, "image_url": image_url, "note": "upscale via Prodia not available, returning original"}


@app.get("/api/v1/image/templates")
async def list_templates():
    return {"ok": True, "templates": []}


@app.post("/api/v1/image/product/generate")
async def generate_product_image(productName: str = "", description: str = "", category: str = ""):
    prompt = f"Product photography of {productName}, {description}, clean white background, studio lighting"
    result = prodia_generate_txt2img(prompt=prompt)
    return result


@app.post("/api/v1/image/ugc/generate-frames")
async def ugc_generate_frames():
    return {"ok": False, "error": "ugc/generate-frames not available on image module"}


@app.get("/storage/images/{filename}")
async def serve_image(filename: str):
    filepath = STORAGE_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(filepath)


# ─── Entry Point ──────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(f"Starting Image Generation Module v3.0.0 on port {PORT}")
    logger.info(f"Storage: {STORAGE_DIR}")
    logger.info(f"Models: Nano Banana (img2img), FLUX-2.dev (txt2img)")
    logger.info(f"Mistral Pixtral Vision: enabled")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
