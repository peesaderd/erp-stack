"""
TikTok UGC Studio — Fal.ai Wan I2V Client (Async Queue)
"""

import os
import json
import time
import uuid
import logging
from typing import Optional
from pathlib import Path

import requests

logger = logging.getLogger("tiktok-ugc.fal_client")

# ─── Defaults ──────────────────────────────────────────────────────────────

FAL_KEY = (
    os.environ.get("FAL_API_KEY", "")
    or os.environ.get("FAL_KEY", "")
)

FAL_BASE_URL = "https://fal.run"
FAL_QUEUE_URL = "https://queue.fal.run"

DEFAULT_MODEL = "fal-ai/wan-i2v"  # Wan I2V image-to-video


import asyncio

async def generate_video_async(
    image_path: str,
    prompt: str,
    duration: int = 10,
    aspect_ratio: str = "9:16",
    model: str = DEFAULT_MODEL,
    fal_key: str = "",
    poll_interval: int = 5,
    timeout: int = 600,
    negative_prompt: Optional[str] = None,
) -> dict:
    """Async wrapper for generate_video. Runs sync call in executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: generate_video(
        image_path=image_path,
        prompt=prompt,
        duration=duration,
        aspect_ratio=aspect_ratio,
        model=model,
        fal_key=fal_key,
        poll_interval=poll_interval,
        timeout=timeout,
        negative_prompt=negative_prompt,
    ))


def generate_video(
    image_path: str,
    prompt: str,
    duration: int = 10,
    aspect_ratio: str = "9:16",
    model: str = DEFAULT_MODEL,
    fal_key: str = "",
    poll_interval: int = 5,
    timeout: int = 600,
    negative_prompt: Optional[str] = None,
) -> dict:
    """
    Generate video from an image using Fal.ai Queue API (Wan I2V).

    This handles the async queue pattern:
      1. Submit request → get status URL
      2. Poll status URL until complete
      3. Return video URL

    Args:
        image_path: Local filesystem path OR public URL of the input image
        prompt: Video prompt text
        duration: Target duration in seconds (default 10)
        aspect_ratio: Output aspect ratio (default "9:16")
        model: Fal.ai model ID (default "fal-ai/wan-i2v")
        fal_key: Fal.ai API key override (falls back to env vars)
        poll_interval: Seconds between status polls (default 5)
        timeout: Max seconds to wait before raising TimeoutError (default 600)
        negative_prompt: Optional negative prompt string

    Returns:
        dict with keys: video_url, task_id, status, elapsed_seconds

    Raises:
        RuntimeError: On API errors, timeouts, or failures
    """
    api_key = fal_key or FAL_KEY
    if not api_key:
        raise RuntimeError(
            "Fal.ai API key not configured. Set FAL_API_KEY or FAL_KEY env var."
        )

    # ── Upload image if local file ──────────────────────────────────────
    image_url = image_path
    if image_path and not image_path.startswith("http://") and not image_path.startswith("https://"):
        image_url = _upload_image(image_path, api_key)
        logger.info(f"Uploaded image to Fal.ai: {image_url}")

    # ── Build request payload ──────────────────────────────────────────
    payload = {
        "image_url": image_url,
        "prompt": prompt,
        "duration": duration,
    }

    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    # ── Submit to queue ────────────────────────────────────────────────
    submit_url = f"{FAL_QUEUE_URL}/{model}"
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }

    logger.info(f"Submitting to Fal.ai queue: {model} (dur={duration}s, ratio={aspect_ratio})")
    submit_resp = requests.post(submit_url, headers=headers, json=payload, timeout=30)

    if submit_resp.status_code != 200:
        raise RuntimeError(
            f"Fal.ai queue submit failed ({submit_resp.status_code}): "
            f"{submit_resp.text[:500]}"
        )

    submit_data = submit_resp.json()
    request_id = submit_data.get("request_id")
    status_url = submit_data.get("status_url", "")

    if not request_id:
        raise RuntimeError(
            f"Fal.ai did not return request_id. Response: {json.dumps(submit_data)[:300]}"
        )

    logger.info(f"Fal.ai queue submitted: request_id={request_id}")

    # ── Poll until completion ──────────────────────────────────────────
    start_time = time.monotonic()
    poll_url = status_url or f"{FAL_QUEUE_URL}/{model}/requests/{request_id}/status"

    while True:
        elapsed = time.monotonic() - start_time
        if elapsed > timeout:
            raise TimeoutError(
                f"Fal.ai queue polling timed out after {timeout}s (request_id={request_id})"
            )

        status_resp = requests.get(poll_url, headers=headers, timeout=30)

        if status_resp.status_code != 200:
            raise RuntimeError(
                f"Fal.ai status poll failed ({status_resp.status_code}): "
                f"{status_resp.text[:300]}"
            )

        status_data = status_resp.json()
        status = status_data.get("status", "UNKNOWN").lower()

        if status == "completed":
            # Fetch result
            result_url = status_url.replace("/status", "/result") if status_url else \
                f"{FAL_QUEUE_URL}/{model}/requests/{request_id}"
            result_resp = requests.get(result_url, headers=headers, timeout=30)
            if result_resp.status_code != 200:
                raise RuntimeError(
                    f"Fal.ai result fetch failed ({result_resp.status_code}): "
                    f"{result_resp.text[:300]}"
                )
            result_data = result_resp.json()
            video_url = (
                result_data.get("video", {}).get("url", "")
                or result_data.get("url", "")
            )

            if not video_url:
                raise RuntimeError(
                    f"Fal.ai completed but no video URL in response. "
                    f"Keys: {list(result_data.keys())}"
                )

            elapsed_total = time.monotonic() - start_time
            logger.info(
                f"Fal.ai video ready: {video_url[:80]}... "
                f"(elapsed={elapsed_total:.1f}s)"
            )

            return {
                "video_url": video_url,
                "request_id": request_id,
                "status": "completed",
                "elapsed_seconds": round(elapsed_total, 1),
            }

        elif status in ("failed", "error"):
            error_detail = status_data.get("error", status_data.get("detail", "Unknown error"))
            raise RuntimeError(
                f"Fal.ai generation failed: {error_detail} "
                f"(request_id={request_id})"
            )

        # Still processing — wait and retry
        logger.debug(f"Fal.ai status: {status} (elapsed={elapsed:.0f}s)")
        time.sleep(poll_interval)


def _upload_image(file_path: str, api_key: str) -> str:
    """
    Upload a local image file to Fal.ai's hosted storage and return a URL.

    Uses Fal.ai's upload endpoint at fal.run.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {file_path}")

    file_size = path.stat().st_size
    if file_size > 32 * 1024 * 1024:
        raise ValueError(
            f"Image file too large: {file_size / 1024 / 1024:.1f} MB "
            "(max 32 MB)"
        )

    # Fal.ai upload via their storage API
    upload_url = f"{FAL_BASE_URL}/storage/upload"
    headers = {
        "Authorization": f"Key {api_key}",
    }

    with open(file_path, "rb") as f:
        upload_resp = requests.post(
            upload_url,
            headers=headers,
            files={"file": (path.name, f, "image/png")},
            timeout=60,
        )

    if upload_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Fal.ai image upload failed ({upload_resp.status_code}): "
            f"{upload_resp.text[:300]}"
        )

    upload_data = upload_resp.json()
    file_url = upload_data.get("url", upload_data.get("file_url", ""))

    if not file_url:
        raise RuntimeError(
            f"Fal.ai upload response missing URL. Response: {json.dumps(upload_data)[:300]}"
        )

    return file_url
