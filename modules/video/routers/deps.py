"""Shared dependencies for modules/video routers — paths, models, helpers.

Extracted from main.py (Phase B refactor, move-only) so each router stays lean.
Follows the tiktok-ugc-studio/routers/deps.py pattern.
"""
import os
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator

# ─── Path setup (idempotent — main.py also does this) ─────────────────
_module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # modules/video
_modules_dir = os.path.dirname(_module_dir)                                # modules
if _modules_dir not in sys.path:
    sys.path.insert(0, _modules_dir)
if _module_dir not in sys.path:
    sys.path.insert(0, _module_dir)

# ─── Storage ──────────────────────────────────────────────────────────
STORAGE_DIR = Path(_module_dir) / "storage"
TTS_DIR = STORAGE_DIR / "tts"
VIDEOS_DIR = STORAGE_DIR / "videos"
COMPOSED_DIR = STORAGE_DIR / "composed"

# Config ควบคุมค่า default — แก้ที่ config.py ที่เดียว
from config import DEFAULT_DURATION

# ─── Schema Engine UGC Style Client (validate_ugc_style) ──────────────
_ugc_client_dir = os.path.join(os.path.dirname(_modules_dir), "prompt-builder-service")
if _ugc_client_dir not in sys.path:
    sys.path.insert(0, _ugc_client_dir)
from ugc_schema_client import validate_ugc_style


# ─── Age Guard: pick LOWEST age from target_age range (owner 2026-09-08) ──
import re as _re


def _resolve_age(target_age: str) -> str:
    """Guard: convert a target_age range (e.g. "25-40") to the SINGLE lowest
    age so the on-camera creator reads as the youngest/most youthful target.
    Rules:
      - has a range "A-B" -> pick A (lowest bound)
      - single int "30" -> use 30
      - whitespace/variants ("25 ~ 40", "25-40 ปี") -> parse first integer as lowest
      - empty / unparsable -> default 20
    Handles Thai suffix text and multiple number tokens by taking the smallest integer found.
    """
    if not target_age:
        return "20"
    s = str(target_age).strip()
    # Find every integer token (including negatives avoided):
    nums = _re.findall(r"\d+", s)
    if not nums:
        return "20"
    # Data is a range/lowest-bound intent -> use the MINIMUM (youngest) token
    return str(min(int(n) for n in nums))


# ─── Pydantic Models (moved from main.py, move-only) ──────────────────

class ScriptRequest(BaseModel):
    product_name: str
    customer_problem: str = ""
    main_benefit: str = ""
    target_audience: str = ""
    tone: str = ""
    cta: str = ""
    duration: str = f"{DEFAULT_DURATION}s"
    extra_rules: str = ""
    features: str = ""
    product_appearance: str = ""
    style: str = "review"
    category: str = "other"

class UGCRequest(BaseModel):
    style: str = "ugc_review"
    product_name: str
    product_desc: str = ""
    gender: str = ""
    age: str = ""
    scene: str = "home"
    negative_prompt: Optional[str] = None

class ConcatRequest(BaseModel):
    video_urls: list[str]
    output_duration: int = 16

class SceneBlock(BaseModel):
    script: str = ""
    duration: int = DEFAULT_DURATION
    mood: str = "energetic"
    sound_style: str = "upbeat_pop"
    style: str = "product_usage"

class VideoRequest(BaseModel):
    product_title: str = ""
    product_name: Optional[str] = None
    product_url: str = ""
    product_image: str = ""
    # owner 2026-09-12: ALL variant images (multi-flavour/colour) so Mimo vision sees the full set
    product_images: list[str] = []
    product_price: Optional[float] = None
    product_commission: Optional[float] = None
    gender: str = ""
    age: str = ""
    tags: list[str] = []
    hook: str = ""
    value: str = ""
    cta: str = ""
    content_type: str = "affiliate"
    ugc_style: str = "holding"
    aspect_ratio: str = "9:16"
    duration: int = DEFAULT_DURATION
    scenes: list[SceneBlock] = []
    prompt: str = ""
    provider: str = "prodia"
    model_tier: str = "standard"
    image_url: Optional[str] = None
    script: Optional[str] = None
    voice: Optional[str] = None
    negative_prompt: Optional[str] = None
    bgm_style: Optional[str] = None
    product_description: Optional[str] = None
    features: str = ""
    recipe: Optional[str] = None
    job_id: Optional[str] = None  # external job_id from caller — used to keep pipeline_logs.db in sync
    image_prompt: str = ""
    video_prompt: str = ""
    video_prompts: list[str] = []
    # ── First/Reference/Last frame + Thai script (Wan พูดเอง) ──
    first_frame: Optional[str] = None
    reference_image: Optional[str] = None
    last_frame: Optional[str] = None
    thai_script: Optional[str] = None
    use_tus_voice: bool = True
    # 🔴 prompt_extend DEFAULT = False (fixed 2026-09-09). ก่อนหน้านี้ค่า default เป็น True และ
    # main.py ส่ง prompt_extend=req.prompt_extend ตรง ๆ → ทุก job ที่ยิงผ่าน /video/generate
    # (โดยไม่ส่ง prompt_extend=false) จะได้ prompt_extend=True เข้า Prodia → Wan 2.7 ได้รับคำสั่ง
    # ให้ EXTEND/เติมฉากเองจนครบ 15s → สร้างเสียง/ขยับปาก/มั่วแถมท้าย 2-3 วิ + พูดเนิบเพื่อยืดเวลา
    # (ตรง studio template ปิด prompt_extend=false ไว้นานแล้ว physical เพี้ยนเมื่อเปิด เจอ validated
    #  08:02 — แต่ path API นี้เคย default True => หลุดเปิดอยู่). Wan พูด thai_script เองในโหมด
    # Voice-A ต้องให้ model หยุดพูดเมื่อจบบท ไม่ใช่ถูกสั่งให้เติมจนเต็มเวลา.
    prompt_extend: bool = False
    # ── FL2V+Audio (Wan 2.7 start-end interpolation + 16kHz mono WAV lip-sync) ──
    audio: Optional[str] = None  # path/URL ของไฟล์เสียง 16kHz mono WAV (Prodia lip-sync)
    # ── SSOT deep-analysis fields (จาก Product Analyzer 8106 → ส่งเข้า prompt-builder) ──
    body_part: str = ""
    special_target: str = ""
    usage_howto: str = ""
    ingredient_highlight: str = ""
    # ── SSOT subcategory (cat → subcat → style ใน prompt_sources.json) ──
    category: str = ""
    subcategory: str = ""
    # target_gender จาก product analyzer (สินค้าผู้หญิง→female) — override gender param
    target_gender: str = ""
    # target_age จาก product analyzer / studio (ช่วงอายุ target) — override age param
    target_age: str = ""

    @field_validator("duration")
    @classmethod
    def _duration_must_be_allowed(cls, v: int) -> int:
        from config import ALLOWED_DURATIONS, MAX_WAN_DURATION
        if v <= 0:
            return DEFAULT_DURATION
        if v not in ALLOWED_DURATIONS:
            raise ValueError(f"duration ต้องเป็น {ALLOWED_DURATIONS} เท่านั้น (ส่ง {v})")
        return v

class AffiliateScriptRequest(ScriptRequest):
    platforms: list[str] = []
