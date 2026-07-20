"""
Pydantic models for TikTok UGC Studio API.
Extracted from main.py for cleaner separation.
"""

from typing import Optional
from pydantic import BaseModel

from config import DEFAULT_VIDEO_DURATION


class ScriptRequest(BaseModel):
    product_name: str = ""
    customer_problem: str = ""
    main_benefit: str = ""
    target_audience: str = ""
    tone: str = ""
    cta: str = ""
    duration: str = f"{DEFAULT_VIDEO_DURATION}s"
    extra_rules: str = ""
    product_url: str = ""
    product_title: str = ""
    product_details: str = ""
    ugc_style: str = ""


class UGCRequest(BaseModel):
    style: str = "ugc_review"
    product_name: str
    product_desc: str = ""
    gender: str = "female"
    age: str = "25-35"
    scene: str = "home"
    negative_prompt: Optional[str] = None


class TTSRequest(BaseModel):
    text: str
    lang: str = "th"
    slow: bool = False


class ScriptTTSRequest(BaseModel):
    hook: str
    value_proposition: str = ""
    cta: str = ""
    lang: str = "th"


class SceneBlock(BaseModel):
    script: str
    duration: int = DEFAULT_VIDEO_DURATION
    mood: str = "energetic"
    sound_style: str = "upbeat_pop"
    style: str = "product_usage"


class VideoRequest(BaseModel):
    product_title: str = ""
    product_url: str = ""
    product_image: str = ""
    product_price: Optional[float] = None
    product_description: Optional[str] = ""
    product_commission: Optional[float] = None
    tags: list[str] = []
    hook: str = ""
    value: str = ""
    cta: str = ""
    content_type: str = "affiliate"
    ugc_style: str = "product_usage"
    aspect_ratio: str = "9:16"
    duration: int = DEFAULT_VIDEO_DURATION
    scenes: list[SceneBlock] = []
    prompt: str = ""
    provider: str = "prodia"
    model_tier: str = "standard"
    image_url: Optional[str] = None
    script: Optional[str] = None
    negative_prompt: Optional[str] = None


class VideoPostRequest(BaseModel):
    job_id: str
    account_id: str
    affiliate_link: str = ""
    caption: str = ""
    schedule_at: Optional[str] = None


class PipelineRequest(BaseModel):
    """New pipeline request using Recipe × UGC Style template system."""
    recipe: str = "skincare"
    ugc_style: str = "talking_head"
    product_title: str = ""
    product_description: str = ""
    product_image: Optional[str] = None
    product_price: Optional[float] = None
    duration: Optional[int] = None  # override recipe default
    platforms: Optional[list] = None
    schedule_time: Optional[str] = "immediate"


class FullPipelineRequest(BaseModel):
    """Legacy pipeline request — kept for backward compat."""
    product_url: Optional[str] = ""
    product_title: Optional[str] = ""
    product_description: Optional[str] = ""
    product_image: Optional[str] = None
    model_image: Optional[str] = None
    ugc_style: str = "holding"
    hook: Optional[str] = ""
    value_proposition: Optional[str] = ""
    cta: Optional[str] = ""
    provider: str = "prodia"
    duration: int = DEFAULT_VIDEO_DURATION
    aspect_ratio: str = "9:16"
    negative_prompt: Optional[str] = ""
    tts_lang: str = "th"
    bg_music: Optional[str] = None
    preset: Optional[str] = None
    recipe: Optional[str] = None
    run_tts: bool = True
    run_video_gen: bool = True
    run_compose: bool = True
    platforms: Optional[list] = None
    schedule_time: Optional[str] = "immediate"


class ScrapeAndGenerateRequest(BaseModel):
    url: str
    duration: str = f"{DEFAULT_VIDEO_DURATION}s"
    tone: str = ""
    cta: str = ""
    ugc_style: str = "ugc_review"
    use_vision: bool = False
