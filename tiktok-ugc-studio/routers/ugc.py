"""UGC frontend compatibility routes — script/prompt/image/video builders."""
import os
import re
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.staticfiles import StaticFiles

from .deps import logger, PRODUCT_IMAGE_DIR, _proxy

router = APIRouter(tags=["ugc"])
@router.post("/ugc/scripts/generate")
async def ugc_scripts_generate(req: dict):
    """Frontend compatibility endpoint for script generation.
    Maps frontend fields to script generator fields, proxies to video module.
    Parses the returned raw script into hook/value/cta for frontend fields.
    """
    import re
    import urllib.parse

    # Extract product name from URL if no title given
    product_title = req.get("product_title", req.get("product_name", "") or "")
    product_url = req.get("product_url", "") or ""
    if not product_title and product_url:
        # Extract slug/name from URL path
        try:
            parsed = urllib.parse.urlparse(product_url)
            path_parts = [p for p in parsed.path.split("/") if p]
            # For Shopee: use last meaningful path segment
            if "shopee" in parsed.netloc or "shp" in parsed.netloc:
                # Shopee URLs like /product/123456789/ชื่อสินค้า
                if len(path_parts) >= 2:
                    product_title = urllib.parse.unquote(path_parts[-1])
            elif "lazada" in parsed.netloc:
                if len(path_parts) >= 2:
                    product_title = urllib.parse.unquote(path_parts[-1])
            else:
                product_title = urllib.parse.unquote(path_parts[-1]) if path_parts else ""
            product_title = product_title.replace("-", " ").replace("_", " ").strip()
        except Exception:
            product_title = product_url.split("/")[-1] or ""
        # Final fallback: just use a generic name
        if not product_title or len(product_title) < 3:
            product_title = f"สินค้าจาก {product_url[:50]}"
    
    # Map frontend fields → ScriptRequest fields for script_gen
    script_body = {
        "product_name": product_title,
        "customer_problem": req.get("customer_problem", ""),
        "main_benefit": req.get("product_details", req.get("description", "")),
        "target_audience": req.get("target_audience", ""),
        "tone": req.get("tone", ""),
        "cta": req.get("cta", ""),
        "duration": req.get("duration", "8s"),
        "extra_rules": req.get("extra_rules", ""),
        "features": req.get("features", ""),
        "product_appearance": req.get("product_appearance", ""),
        "style": req.get("style", "review"),
        "category": req.get("category", "other"),
    }
    result = await _proxy("POST", "video", "/api/v1/scripts/generate", script_body)
    if not (result.get("ok", False) or result.get("success", False)):
        raise HTTPException(status_code=500, detail=result.get("error", "Script generation failed"))
    
    data = result.get("data", {})
    script_obj = data.get("script", {}) if isinstance(data.get("script"), dict) else {}
    if not script_obj and isinstance(result.get("script"), dict):
        script_obj = result["script"]
    raw_script = script_obj.get("script", "") if isinstance(script_obj, dict) else str(script_obj)
    
    # Parse raw script into hook/value/cta
    hook = ""
    value_proposition = ""
    cta = ""
    
    if raw_script:
        # Try [Hook]/[Value]/[CTA] marker format
        hook_match = re.search(r'\[Hook\]\s*(.*?)(?=\[Value\]|\[CTA\]|$)', raw_script, re.DOTALL)
        value_match = re.search(r'\[Value\]\s*(.*?)(?=\[CTA\]|$)', raw_script, re.DOTALL)
        cta_match = re.search(r'\[CTA\]\s*(.*)', raw_script, re.DOTALL)
        
        if hook_match:
            hook = hook_match.group(1).strip()
        if value_match:
            value_proposition = value_match.group(1).strip()
        if cta_match:
            cta = cta_match.group(1).strip()
        
        # Fallback for [สคริปต์ X วินาที] format or plain text
        if not hook and not value_proposition and not cta:
            lines = [l.strip() for l in raw_script.split('\n') if l.strip() and not l.startswith('[')]
            if len(lines) >= 3:
                hook = lines[0]
                value_proposition = lines[1]
                cta = lines[-1]
            elif len(lines) == 2:
                hook = lines[0]
                cta = lines[-1]
            elif len(lines) == 1:
                hook = lines[0]
        
        # Final fallback: sentence-split single-line scripts into hook/value/cta
        if hook and not value_proposition and not cta:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?。])\s+', hook) if s.strip()]
            if len(sentences) >= 3:
                value_proposition = ' '.join(sentences[1:-1])
                cta = sentences[-1]
                hook = sentences[0]
            elif len(sentences) == 2:
                cta = sentences[-1]
                hook = sentences[0]
    
    # JSON-template PROMPT PIPELINE REMOVED (owner 2026-09-08 "เอา JSON prompt pipeline
    # ออกไปเลย" 14:47): เดิมตรงนี้เรียก prompt-builder /api/v1/build แล้วเอาค่า
    # image_prompt/video_prompt ที่เป็น JSON template ถือขวด/label (ผิดสินค้า เช่น ยีนส์ชาย
    # -> "Thai woman holds product / office persona / label crisp") กลับมาแสดง/คืน frontend
    # เพื่อไปสร้างรูป/วิดีโอ ตรงข้ามกับเส้นทาง /video/generate ที่เป็น Mimo AI-authored อยู่แล้ว
    # การสร้างวิดีโอจริง (ทั้ง one-click startGeneration และ step-wizard) ผ่าน /video/generate
    # = Mimo เขียน prompt ล้วน ไม่ต้องใช้ template นี้.
    # เหลือแฮชแท็ก/ฉาก/เสียงที่ได้จาก script (video module) ไม่ใช้ pb-template อีกต่อไป.
    hashtags = []
    scene = ""
    voice = ""
    mood = ""
    _style_disp = {"holding":"ถือสินค้า", "usage":"ใช้สินค้า", "review":"รีวิว", "unboxing":"แกะกล่อง"}.get(req.get("ugc_style", "holding"), req.get("ugc_style", "holding"))
    scene = f"UGC {_style_disp} หน้ากล้อง ฉากเรียบ"
    voice = f"เสียงไทย{req.get('target_gender', req.get('gender', '')) or 'หญิง'} น้ำเสียง{req.get('tone', 'เป็นกันเอง')}".replace("หญิง ", "หญิง ") if req.get('target_gender') or req.get('gender') else f"เสียงไทย น้ำเสียง{req.get('tone', 'เป็นกันเอง')}"
    mood = f"{req.get('tone', 'เป็นกันเอง')}, สบายๆ, อบอุ่น"

    return {
        "success": True,
        "script": raw_script,
        "hook": hook,
        "value_proposition": value_proposition,
        "cta": cta,
        "uses_llm": script_obj.get("uses_llm", False),
        "duration": script_obj.get("duration", "8s"),
        "product": script_obj.get("product", ""),
        "hashtags": hashtags,
        # JSON-template prompts removed — video/script generation ใช้ /video/generate (Mimo)
        "prompt": "",
        "video_prompt": "",
        "negative_prompt": "",
        "scene": scene,
        "voice": voice,
        "mood": mood,
    }

@router.post("/ugc/images/build-prompt")
async def ugc_images_build_prompt(req: dict):
    """Frontend compatibility endpoint for image prompt generation.
    JSON-template PROMPT PIPELINE REMOVED (owner 2026-09-08): เดิมคืน pb JSON-template
    image_prompt (ถือขวด/label ผิดสินค้า). ตอนนี้ image/video prompt เขียนโดย Mimo ผ่าน
    เส้นทาง /video/generate pipeline เท่านั้น — ตัว build-prompt แบบ editor นี้ออกไปแล้ว.
    """
    # No pb JSON-template authoring here anymore. The video pipeline (analyze_product,
    # Mimo) authors product-correct prompts. Return empty so editor doesn't fire a
    # wrong-product template image.
    raise HTTPException(status_code=410, detail="JSON-template prompt pipeline removed — ใช้เส้นทาง /video/generate (Mimo เขียน prompt เอง) แทน")

@router.post("/ugc/images/generate")
async def ugc_images_generate(req: dict):
    """Frontend compatibility endpoint for image generation.
    JSON-template PROMPT PIPELINE REMOVED (owner 2026-09-08): image_prompt ของ nano-banana
    ต้องมาจาก Mimo ของ video pipeline ไม่ใช่ pb JSON template (ถือขวด/label ผิดสินค้า).
    """
    raise HTTPException(status_code=410, detail="JSON-template image generation removed — ใช้ /video/generate (Mimo เขียน prompt เอง) แทน")

@router.post("/ugc/videos/build-prompt")
async def ugc_videos_build_prompt(req: dict):
    """Build video prompt — JSON-template PROMPT PIPELINE REMOVED (owner 2026-09-08).
    เดิมคืน pb JSON-template video_prompt (ถือขวด/label ผิดสินค้า). ตอนนี้ไม่มีอีกแล้ว:
    video prompt เขียนโดย Mimo ของ video pipeline ผ่าน /video/generate เท่านั้น
    (routes/video.py ส่ง prompt ว่าง -> analyze_product คิดเองด้วย Mimo).
    """
    raise HTTPException(status_code=410, detail="JSON-template video-prompt removed — ใช้ /video/generate (Mimo เขียน prompt เอง) แทน")

from fastapi.staticfiles import StaticFiles

# Mount static file serving for product images
product_images_dir = Path(__file__).resolve().parent.parent / "storage" / "product_images"
os.makedirs(product_images_dir, exist_ok=True)
