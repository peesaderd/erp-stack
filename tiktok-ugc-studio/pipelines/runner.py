#!/usr/bin/env python3
"""
Pipeline Template Runner
========================
Recipe × UGC Style → Pipeline Config

Usage:
    from pipelines import build_pipeline_config
    
    config = build_pipeline_config(
        recipe={"name": "skincare", "mood": "calm", "duration": 10},
        ugc_style="talking_head",
        product={"title": "Vitamin C Serum", "description": "..."},
    )
    
    # config ready to pass to video generation:
    # config.job_type, config.needs_audio, config.prompts, config.video_params...
"""

import os
import yaml
import json
import random
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

logger = logging.getLogger("pipeline-runner")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
CTA_POOL_PATH = Path(__file__).resolve().parent / "cta_pool.yaml"


# ═══════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════

@dataclass
class PipelineConfig:
    """Result of Recipe × UGC Style → ready for video generation"""
    template_name: str
    ugc_style: str
    job_type: str
    needs_audio: bool
    image_requirement: str
    image_model: str
    negative_prompt: str
    prompts: Dict[str, str]          # {hook, value, cta} → full prompt text
    cta: str                          # selected CTA text
    duration: int
    resolution: str
    ratio: str
    bgm_style: str
    mood: str
    vibe: str = ""
    variations_used: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "template": self.template_name,
            "ugc_style": self.ugc_style,
            "job_type": self.job_type,
            "needs_audio": self.needs_audio,
            "image_requirement": self.image_requirement,
            "image_model": self.image_model,
            "negative_prompt": self.negative_prompt,
            "prompts": self.prompts,
            "cta": self.cta,
            "duration": self.duration,
            "resolution": self.resolution,
            "ratio": self.ratio,
            "bgm_style": self.bgm_style,
            "mood": self.mood,
            "vibe": self.vibe,
            "variations_used": self.variations_used,
        }


# ═══════════════════════════════════════════════════════
# Template Loading
# ═══════════════════════════════════════════════════════

def _load_yaml(path: Path) -> dict:
    """Load YAML file, return dict or empty."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load {path}: {e}")
        return {}


def get_template(ugc_style: str) -> dict:
    """Load a single pipeline template by UGC style name."""
    path = TEMPLATES_DIR / f"{ugc_style}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {ugc_style} (looked in {path})")
    return _load_yaml(path)


def list_templates() -> List[dict]:
    """List all available pipeline templates with metadata."""
    templates = []
    for f in sorted(TEMPLATES_DIR.glob("*.yaml")):
        t = _load_yaml(f)
        templates.append({
            "name": t.get("name", f.stem),
            "emoji": t.get("emoji", ""),
            "label": t.get("label", ""),
            "description": t.get("description", ""),
            "needs_audio": t.get("generation", {}).get("needs_audio", False),
            "image_requirement": t.get("generation", {}).get("image_requirement", ""),
            "durations": t.get("video_params", {}).get("duration", [8]),
        })
    return templates


# ═══════════════════════════════════════════════════════
# Variation Engine
# ═══════════════════════════════════════════════════════

def _pick_variations(template: dict) -> Dict[str, str]:
    """Randomly select 1 option from each variation category."""
    variations = template.get("variations", {})
    picked = {}
    for key, options in variations.items():
        if options:
            picked[key] = random.choice(options)
    logger.debug(f"Variations: {picked}")
    return picked


# ═══════════════════════════════════════════════════════
# CTA Engine
# ═══════════════════════════════════════════════════════

_cta_cache: Optional[dict] = None


def _load_cta_pool() -> dict:
    global _cta_cache
    if _cta_cache is None:
        _cta_cache = _load_yaml(CTA_POOL_PATH)
    return _cta_cache


def _pick_cta(mood: str = "general", lang: str = "th") -> str:
    """Pick a random CTA matching the recipe mood."""
    pool = _load_cta_pool()
    mood_map = pool.get("mood_style_map", {}).get(mood, ["direct", "soft"])
    category = random.choice(mood_map)
    ctas = pool.get(category, {}).get(lang, ["กดตะกร้าเลย! 🛒"])
    return random.choice(ctas)


# ═══════════════════════════════════════════════════════
# Main: Build Pipeline Config
# ═══════════════════════════════════════════════════════

def build_pipeline_config(
    recipe: dict,
    ugc_style: str,
    product: dict,
) -> PipelineConfig:
    """
    Recipe × UGC Style → PipelineConfig
    
    Args:
        recipe: Recipe dict from /api/tiktok/pipeline/recipes
            {name, mood, bgm_style, duration, prompt_context?}
        ugc_style: one of: holding_product, product_usage, ugc_review, talking_head
        product: Product dict
            {title, description, image_url?, price?}
    
    Returns:
        PipelineConfig ready for video generation
    
    Example:
        >>> config = build_pipeline_config(
        ...     recipe={"name": "skincare", "mood": "calm", "bgm_style": "luxury_jazz", "duration": 10},
        ...     ugc_style="talking_head",
        ...     product={"title": "Vitamin C Serum"}
        ... )
        >>> config.needs_audio
        True
        >>> config.job_type
        'wan2-7.img2vid.v1'
    """
    template = get_template(ugc_style)
    
    # 1. Random variations
    vars_used = _pick_variations(template)
    
    # 2. Build scene prompts
    product_name = product.get("title", "this product")
    prompts = {}
    for scene, prompt_tpl in template.get("scene_prompts", {}).items():
        try:
            prompts[scene] = prompt_tpl.format(product=product_name, **vars_used)
        except KeyError as e:
            # Missing variation key → skip formatting that key
            prompts[scene] = prompt_tpl.replace(f"{{{e.args[0]}}}", "")
            prompts[scene] = prompts[scene].format(product=product_name, **{k: v for k, v in vars_used.items() if k != e.args[0]})
    
    # 3. Pick CTA based on recipe mood
    cta = _pick_cta(recipe.get("mood", "general"))
    
    # 4. Select duration — closest to recipe preference
    durations = template.get("video_params", {}).get("duration", [8])
    target = recipe.get("duration", 8)
    duration = min(durations, key=lambda d: abs(d - target))
    
    # 5. Build config
    gen = template.get("generation", {})
    vp = template.get("video_params", {})
    
    return PipelineConfig(
        template_name=template.get("name", ugc_style),
        ugc_style=ugc_style,
        job_type=gen.get("job_type", "wan2-7.img2vid.v1"),
        needs_audio=gen.get("needs_audio", False),
        image_requirement=gen.get("image_requirement", "product_only"),
        image_model=gen.get("image_model", "nano-banana"),
        negative_prompt=gen.get("negative_prompt", ""),
        prompts=prompts,
        cta=cta,
        duration=duration,
        resolution=vp.get("resolution", "720P"),
        ratio=vp.get("ratio", "9:16"),
        bgm_style=recipe.get("bgm_style", "upbeat_pop"),
        mood=recipe.get("mood", "general"),
        vibe=recipe.get("prompt_context", {}).get("vibe", ""),
        variations_used=vars_used,
    )


# ═══════════════════════════════════════════════════════
# CLI Test
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    # Test: list all templates
    print("=" * 50)
    print("Available Pipeline Templates:")
    for t in list_templates():
        audio = "🎤+audio" if t["needs_audio"] else "📷 no audio"
        print(f"  {t['emoji']} {t['name']:20s} {audio:12s} durations={t['durations']}")
    
    # Test: build config
    print("\n" + "=" * 50)
    print("Test: skincare + talking_head")
    
    config = build_pipeline_config(
        recipe={"name": "skincare", "mood": "calm", "bgm_style": "luxury_jazz", "duration": 10},
        ugc_style="talking_head",
        product={"title": "Vitamin C Serum", "description": "Brightening facial serum"},
    )
    
    print(f"  Template:     {config.template_name}")
    print(f"  Job Type:     {config.job_type}")
    print(f"  Needs Audio:  {config.needs_audio}")
    print(f"  Duration:     {config.duration}s")
    print(f"  CTA:          {config.cta}")
    print(f"  Variations:   {config.variations_used}")
    print(f"\n  Hook Prompt:\n    {config.prompts.get('hook', 'N/A')[:120]}...")
    print(f"\n  Value Prompt:\n    {config.prompts.get('value', 'N/A')[:120]}...")
    print(f"\n  CTA Prompt:\n    {config.prompts.get('cta', 'N/A')[:120]}...")
