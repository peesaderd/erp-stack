"""
TikTok UGC Studio — AI Video Generation Pipeline
Provider-agnostic: Kling, Runway, Pika, Minimax, etc.
"""

import os
import json
import base64
import logging
from typing import Optional
from enum import Enum

import requests

logger = logging.getLogger("tiktok-ugc.video_gen")

# ─── Provider Configuration ────────────────────────────────────────────

class VideoProvider(str, Enum):
    KLING = "kling"
    RUNWAY = "runway"
    PIKA = "pika"
    MINIMAX = "minimax"
    HAIHUO = "haihuo"  # aka Hailuo/Minimax

PROVIDER_CONFIG = {
    VideoProvider.KLING: {
        "key": os.environ.get("KLING_API_KEY", ""),
        "secret": os.environ.get("KLING_API_SECRET", ""),
        "models": {"standard": "kling-v1", "pro": "kling-v1-pro"},
        "default_model": "kling-v1",
        "base_url": "https://api.kling.ai/v1",
    },
    VideoProvider.RUNWAY: {
        "key": os.environ.get("RUNWAY_API_KEY", ""),
        "models": {"standard": "gen3a", "turbo": "gen3a_turbo"},
        "default_model": "gen3a",
        "base_url": "https://api.runwayml.com/v1",
    },
    VideoProvider.PIKA: {
        "key": os.environ.get("PIKA_API_KEY", ""),
        "models": {"standard": "pika-2.0", "turbo": "pika-2.0-turbo"},
        "default_model": "pika-2.0",
        "base_url": "https://api.pika.art/v1",
    },
    VideoProvider.MINIMAX: {
        "key": os.environ.get("MINIMAX_API_KEY", ""),
        "models": {"standard": "video-01"},
        "default_model": "video-01",
        "base_url": "https://api.minimax.chat/v1",
    },
}

# ─── Common generation presets for UGC videos ──────────────────────────

UGC_PRESETS = {
    "holding_product": {
        "duration": 8,
        "aspect_ratio": "9:16",
        "style": "realistic",
        "prompt_suffix": "Ultra-realistic, natural lighting, handheld camera feel, no text, no watermark",
    },
    "product_usage": {
        "duration": 8,
        "aspect_ratio": "9:16",
        "style": "realistic",
        "prompt_suffix": "Demonstration video, natural hand movements, clean background, no text",
    },
    "ugc_review": {
        "duration": 8,
        "aspect_ratio": "9:16",
        "style": "realistic",
        "prompt_suffix": "Casual UGC review style, authentic, handheld, natural lighting, no text, no watermark",
    },
}

# ─── Generate Video ────────────────────────────────────────────────────

def generate_video(
    prompt: str,
    provider: VideoProvider = VideoProvider.KLING,
    model_tier: str = "standard",
    duration: int = 8,
    aspect_ratio: str = "9:16",
    image_url: Optional[str] = None,
    timeout: int = 300,
) -> dict:
    """
    Generate AI video using configured provider.
    Falls back to generation request (async — returns task ID).
    """
    config = PROVIDER_CONFIG.get(provider)
    if not config or not config.get("key"):
        raise ValueError(f"{provider.value} not configured — set {provider.value.upper()}_API_KEY")

    model = config["models"].get(model_tier, config["default_model"])

    logger.info(f"Video gen: {provider.value}/{model} | dur={duration}s | ratio={aspect_ratio}")

    if provider == VideoProvider.KLING:
        return _kling_generate(config, prompt, model, duration, aspect_ratio, image_url, timeout)
    elif provider == VideoProvider.MINIMAX:
        return _minimax_generate(config, prompt, model, duration, aspect_ratio, image_url, timeout)
    else:
        return _generic_generate(config, provider, prompt, model, duration, aspect_ratio, image_url, timeout)


def check_status(provider: VideoProvider, task_id: str, timeout: int = 30) -> dict:
    """Check video generation status"""
    config = PROVIDER_CONFIG.get(provider)
    if not config:
        raise ValueError(f"Unknown provider: {provider}")

    if provider == VideoProvider.KLING:
        return _kling_status(config, task_id)
    else:
        return _generic_status(config, provider, task_id)


# ─── Provider-specific Implementations ─────────────────────────────────

def _kling_generate(config, prompt, model, duration, aspect_ratio, image_url, timeout):
    """Generate via Kling AI API"""
    url = f"{config['base_url']}/images/generations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['key']}",
    }

    payload = {
        "model": model,
        "prompt": prompt,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "num_videos": 1,
    }

    if image_url:
        payload["image_url"] = image_url

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Kling error ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()
    return {
        "provider": "kling",
        "task_id": data.get("data", {}).get("task_id", ""),
        "status": "pending",
        "model": model,
        "estimate_cost": 0.15,  # rough estimate per video
    }


def _kling_status(config, task_id):
    """Check Kling task status"""
    url = f"{config['base_url']}/images/generations/{task_id}"
    headers = {"Authorization": f"Bearer {config['key']}"}

    resp = requests.get(url, headers=headers, timeout=30)
    data = resp.json()
    task_data = data.get("data", {})

    result = {
        "task_id": task_id,
        "provider": "kling",
        "status": task_data.get("status", "unknown"),
    }

    if task_data.get("videos"):
        result["videos"] = task_data["videos"]
        result["video_url"] = task_data["videos"][0].get("url", "")

    return result


def _minimax_generate(config, prompt, model, duration, aspect_ratio, image_url, timeout):
    """Generate via Minimax/Hailuo API"""
    url = f"{config['base_url']}/video/generate"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['key']}",
    }

    payload = {
        "model": model,
        "prompt": prompt,
        "duration": duration,
    }

    if image_url:
        payload["image_url"] = image_url

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Minimax error ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()
    return {
        "provider": "minimax",
        "task_id": data.get("task_id", ""),
        "status": "pending",
        "model": model,
        "estimate_cost": 0.10,
    }


def _generic_generate(config, provider, prompt, model, duration, aspect_ratio, image_url, timeout):
    """Generic video generation for providers with similar API patterns"""
    url = f"{config['base_url']}/generations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['key']}",
    }

    payload = {
        "model": model,
        "prompt": prompt,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
    }

    if image_url:
        payload["image_url"] = image_url

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"{provider.value} error ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()
    return {
        "provider": provider.value,
        "task_id": data.get("id", data.get("task_id", "")),
        "status": "pending",
        "model": model,
    }


def _generic_status(config, provider, task_id):
    """Generic status check"""
    url = f"{config['base_url']}/generations/{task_id}"
    headers = {"Authorization": f"Bearer {config['key']}"}

    resp = requests.get(url, headers=headers, timeout=30)
    data = resp.json()

    return {
        "task_id": task_id,
        "provider": provider.value,
        "status": data.get("status", "unknown"),
        "video_url": data.get("output", {}).get("url", ""),
    }


def get_available_providers() -> dict:
    """List configured providers"""
    providers = {}
    for p in VideoProvider:
        cfg = PROVIDER_CONFIG.get(p)
        if cfg and cfg.get("key"):
            providers[p.value] = {
                "models": list(cfg["models"].keys()),
                "default_model": cfg["default_model"],
            }
    return providers


def build_video_prompt(
    script: str,
    ugc_style: str = "ugc_review",
    additional_context: str = "",
) -> str:
    """Build a video generation prompt from a UGC script + style"""
    preset = UGC_PRESETS.get(ugc_style, UGC_PRESETS["ugc_review"])
    return f"{script}\n\nStyle: {ugc_style}\n{additional_context}\n{preset['prompt_suffix']}".strip()
