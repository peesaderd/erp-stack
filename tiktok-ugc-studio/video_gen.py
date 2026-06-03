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
    WAVESPEED = "wavespeed"
    KLING = "kling"
    RUNWAY = "runway"
    PIKA = "pika"
    MINIMAX = "minimax"

PROVIDER_CONFIG = {
    VideoProvider.WAVESPEED: {
        "key": os.environ.get("WAVESPEED_API_KEY", ""),
        "models": {"standard": "wavespeed-ai/short-video-generator"},
        "default_model": "wavespeed-ai/short-video-generator",
        "base_url": "https://api.wavespeed.ai/api/v3",
        "image_to_video": True,
        "rate_limit_rps": 10,
        "estimate_cost": 0.05,
    },
    VideoProvider.KLING: {
        "key": os.environ.get("KLING_API_KEY", ""),
        "secret": os.environ.get("KLING_API_SECRET", ""),
        "models": {"standard": "kling-v1", "pro": "kling-v1-pro"},
        "default_model": "kling-v1",
        "base_url": "https://api.kling.ai/v1",
        "image_to_video": True,
        "rate_limit_rps": 5,
        "estimate_cost": 0.60,
    },
    VideoProvider.RUNWAY: {
        "key": os.environ.get("RUNWAY_API_KEY", ""),
        "models": {"standard": "gen3a", "turbo": "gen3a_turbo"},
        "default_model": "gen3a",
        "base_url": "https://api.runwayml.com/v1",
        "image_to_video": True,
        "rate_limit_rps": 10,
        "estimate_cost": 0.40,
    },
    VideoProvider.PIKA: {
        "key": os.environ.get("PIKA_API_KEY", ""),
        "models": {"standard": "pika-2.0", "turbo": "pika-2.0-turbo"},
        "default_model": "pika-2.0",
        "base_url": "https://api.pika.art/v1",
        "image_to_video": True,
        "rate_limit_rps": 20,
        "estimate_cost": 0.30,
    },
    VideoProvider.MINIMAX: {
        "key": os.environ.get("MINIMAX_API_KEY", ""),
        "models": {"standard": "video-01"},
        "default_model": "video-01",
        "base_url": "https://api.minimax.chat/v1",
        "image_to_video": True,
        "rate_limit_rps": 10,
        "estimate_cost": 0.10,
    },
}

# ─── Rate Limiter ──────────────────────────────────────────────────────

import time as _time
from collections import defaultdict

_rate_limit_tracker = defaultdict(lambda: {"tokens": 0, "last_refill": _time.monotonic()})

def _check_rate_limit(provider: VideoProvider):
    cfg = PROVIDER_CONFIG.get(provider)
    if not cfg or "rate_limit_rps" not in cfg:
        return
    rps = cfg["rate_limit_rps"]
    key = provider.value
    state = _rate_limit_tracker[key]
    now = _time.monotonic()
    elapsed = now - state["last_refill"]
    state["tokens"] = min(state["tokens"] + elapsed * rps, rps)
    state["last_refill"] = now
    if state["tokens"] < 1:
        wait = (1 - state["tokens"]) / rps
        logger.info(f"Rate limit {key}: waiting {wait:.2f}s")
        _time.sleep(wait)
        state["tokens"] = 1
    state["tokens"] -= 1


# ─── Retry Logic ───────────────────────────────────────────────────────

import random as _random
from functools import wraps

def retryable(max_retries=3, base_delay=1.0, backoff=2.0, retry_statuses=(429, 502, 503, 504)):
    """Retry with exponential backoff on transient HTTP errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.HTTPError, RuntimeError) as e:
                    last_err = e
                    if e.response and e.response.status_code in retry_statuses:
                        delay = base_delay * (backoff ** attempt) + _random.uniform(0, 0.5)
                        logger.warning(f"Retry {attempt+1}/{max_retries} after {delay:.1f}s: {e}")
                        _time.sleep(delay)
                        continue
                    raise
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    last_err = e
                    delay = base_delay * (backoff ** attempt) + _random.uniform(0, 0.5)
                    logger.warning(f"Retry {attempt+1}/{max_retries} net after {delay:.1f}s: {e}")
                    _time.sleep(delay)
                    continue
            raise last_err or RuntimeError("Max retries exceeded")
        return wrapper
    return decorator


# ─── Provider Fallback Chain ───────────────────────────────────────────

PROVIDER_FALLBACK_CHAIN = [
    (VideoProvider.WAVESPEED, "standard"),
    (VideoProvider.MINIMAX, "standard"),
    (VideoProvider.PIKA, "standard"),
    (VideoProvider.RUNWAY, "standard"),
    (VideoProvider.KLING, "standard"),
]

def generate_video_with_fallback(prompt, duration=8, aspect_ratio="9:16", image_url=None, face_image_url=None, **kw):
    """Try providers in priority order until one succeeds"""
    errors = []
    for provider, tier in PROVIDER_FALLBACK_CHAIN:
        cfg = PROVIDER_CONFIG.get(provider)
        if not cfg or not cfg.get("key"):
            errors.append(f"{provider.value}: no key")
            continue
        try:
            logger.info(f"Fallback attempt: {provider.value}/{tier}")
            result = generate_video(
                prompt=prompt, provider=provider, model_tier=tier,
                duration=duration, aspect_ratio=aspect_ratio,
                image_url=image_url, face_image_url=face_image_url, **kw,
            )
            result["fallback_attempted"] = errors
            return result
        except Exception as e:
            errors.append(f"{provider.value}: {str(e)[:100]}")
            logger.warning(f"{provider.value} failed: {e}, trying next")
            continue
    raise RuntimeError(f"All providers failed: {'; '.join(errors)}")

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
    provider: VideoProvider = VideoProvider.WAVESPEED,
    model_tier: str = "standard",
    duration: int = 8,
    aspect_ratio: str = "9:16",
    image_url: Optional[str] = None,
    face_image_url: Optional[str] = None,
    timeout: int = 300,
) -> dict:
    """Generate AI video via chosen provider. Supports image-to-video."""
    config = PROVIDER_CONFIG.get(provider)
    if not config or not config.get("key"):
        raise ValueError(f"{provider.value} not configured — set {provider.value.upper()}_API_KEY")

    model = config["models"].get(model_tier, config["default_model"])
    mode = "image_to_video" if image_url else "text_to_video"

    _check_rate_limit(provider)
    logger.info(f"Video gen: {provider.value}/{model} | mode={mode} | dur={duration}s | ratio={aspect_ratio} | face_ref={bool(face_image_url)}")

    handler = _PROVIDER_HANDLERS.get(provider)
    if not handler:
        raise ValueError(f"No handler for {provider.value}")

    result = handler(config, prompt, model, duration, aspect_ratio, image_url, face_image_url, timeout)
    result.update({
        "provider": provider.value,
        "model": model,
        "mode": mode,
        "estimate_cost": config.get("estimate_cost", 0),
    })
    return result


def check_status(provider: VideoProvider, task_id: str) -> dict:
    """Check video generation status"""
    config = PROVIDER_CONFIG.get(provider)
    if not config:
        raise ValueError(f"Unknown provider: {provider}")
    handler = _STATUS_HANDLERS.get(provider)
    if not handler:
        raise ValueError(f"No status handler for {provider.value}")
    return handler(config, task_id)


# ─── Provider-specific Implementations ─────────────────────────────────

@retryable(max_retries=3)
def _ws_generate(config, prompt, model, duration, aspect_ratio, image_url, face_image_url, timeout):
    """WaveSpeed API v3 — unified endpoint for all models"""
    url = f"{config['base_url']}/predictions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config['key']}"}
    payload = {
        "prompt": prompt, "width": 1080, "height": 1920,
    }
    if duration:
        # WaveSpeed shorts only allow 5, 10, or 15 seconds
        allowed = [5, 10, 15]
        payload["duration"] = min(allowed, key=lambda x: abs(x - duration))
    if aspect_ratio == "16:9":
        payload["width"], payload["height"] = 1920, 1080
    elif aspect_ratio == "1:1":
        payload["width"], payload["height"] = 1024, 1024
    if image_url:
        payload["image_url"] = image_url
    if face_image_url:
        payload["face_image_url"] = face_image_url
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"WaveSpeed error ({resp.status_code}): {resp.text[:500]}")
    data = resp.json().get("data", {})
    return {"task_id": data.get("id", ""), "status": data.get("status", "created")}


def _ws_status(config, task_id):
    """WaveSpeed API v3 — poll task result"""
    url = f"{config['base_url']}/predictions/{task_id}/result"
    headers = {"Authorization": f"Bearer {config['key']}"}
    resp = requests.get(url, headers=headers, timeout=30)
    data = resp.json().get("data", {})
    video_url = ""
    outputs = data.get("outputs", [])
    if outputs:
        video_url = outputs[0]
    return {
        "task_id": task_id,
        "status": data.get("status", "unknown"),
        "video_url": video_url,
        "progress": 100 if data.get("status") == "completed" else 50 if data.get("status") == "processing" else None,
    }


@retryable(max_retries=3)
def _kling_generate(config, prompt, model, duration, aspect_ratio, image_url, face_image_url, timeout):
    """Generate via Kling AI API"""
    url = f"{config['base_url']}/images/generations"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config['key']}"}
    payload = {"model": model, "prompt": prompt, "duration": duration, "aspect_ratio": aspect_ratio}
    if image_url:
        payload["image_url"] = image_url
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Kling error ({resp.status_code}): {resp.text[:500]}")
    data = resp.json()
    return {"task_id": data.get("data", {}).get("task_id", ""), "status": "pending"}


def _kling_status(config, task_id):
    """Kling task status"""
    url = f"{config['base_url']}/images/generations/{task_id}"
    headers = {"Authorization": f"Bearer {config['key']}"}
    resp = requests.get(url, headers=headers, timeout=30)
    data = resp.json()
    task_data = data.get("data", {})
    result = {"task_id": task_id, "status": task_data.get("status", "unknown")}
    if task_data.get("videos"):
        result["videos"] = task_data["videos"]
        result["video_url"] = task_data["videos"][0].get("url", "")
    return result


@retryable(max_retries=3)
def _minimax_generate(config, prompt, model, duration, aspect_ratio, image_url, face_image_url, timeout):
    """Generate via Minimax/Hailuo API"""
    url = f"{config['base_url']}/video/generate"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config['key']}"}
    payload = {"model": model, "prompt": prompt, "duration": duration}
    if image_url:
        payload["image_url"] = image_url
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Minimax error ({resp.status_code}): {resp.text[:500]}")
    return {"task_id": resp.json().get("task_id", ""), "status": "pending"}


def _minimax_status(config, task_id):
    """Minimax task status"""
    url = f"{config['base_url']}/video/status/{task_id}"
    headers = {"Authorization": f"Bearer {config['key']}"}
    resp = requests.get(url, headers=headers, timeout=30)
    data = resp.json()
    return {"task_id": task_id, "status": data.get("status", "unknown"), "video_url": (data.get("output", {}) or {}).get("url", "")}


@retryable(max_retries=3)
def _generic_generate(config, prompt, model, duration, aspect_ratio, image_url, face_image_url, timeout):
    """Generic for Runway/Pika-like APIs"""
    url = f"{config['base_url']}/generations"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config['key']}"}
    payload = {"model": model, "prompt": prompt}
    if image_url:
        payload["image_url"] = image_url
    pname = next((k.value for k, v in PROVIDER_CONFIG.items() if v == config), "?")
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"{pname} error ({resp.status_code}): {resp.text[:500]}")
    data = resp.json()
    return {"task_id": data.get("id", data.get("task_id", "")), "status": "pending"}


def _generic_status(config, task_id):
    """Generic status check for Runway/Pika"""
    url = f"{config['base_url']}/generations/{task_id}"
    headers = {"Authorization": f"Bearer {config['key']}"}
    resp = requests.get(url, headers=headers, timeout=30)
    data = resp.json()
    return {"task_id": task_id, "status": data.get("status", "unknown"), "video_url": (data.get("output", {}) or {}).get("url", "")}


# ─── Provider Dispatch Tables ─────────────────────────────────────────

_PROVIDER_HANDLERS = {
    VideoProvider.WAVESPEED: _ws_generate,
    VideoProvider.KLING: _kling_generate,
    VideoProvider.MINIMAX: _minimax_generate,
    VideoProvider.RUNWAY: _generic_generate,
    VideoProvider.PIKA: _generic_generate,
}

_STATUS_HANDLERS = {
    VideoProvider.WAVESPEED: _ws_status,
    VideoProvider.KLING: _kling_status,
    VideoProvider.MINIMAX: _minimax_status,
    VideoProvider.RUNWAY: _generic_status,
    VideoProvider.PIKA: _generic_status,
}


def get_available_providers() -> dict:
    """List configured providers with pricing"""
    providers = {}
    for p in VideoProvider:
        cfg = PROVIDER_CONFIG.get(p)
        if cfg and cfg.get("key"):
            providers[p.value] = {
                "models": list(cfg["models"].keys()),
                "default_model": cfg["default_model"],
                "image_to_video": cfg.get("image_to_video", False),
                "rate_limit_rps": cfg.get("rate_limit_rps", 0),
                "estimate_cost": cfg.get("estimate_cost", 0),
            }
    return providers


def build_video_prompt(script: str, ugc_style: str = "ugc_review", additional_context: str = "") -> str:
    """Build a video generation prompt from a UGC script + style"""
    preset = UGC_PRESETS.get(ugc_style, UGC_PRESETS["ugc_review"])
    return f"{script}\n\nStyle: {ugc_style}\n{additional_context}\n{preset['prompt_suffix']}".strip()


# ─── Task Queue (Background Video Processing) ─────────────────────────

# ─── Redis Queue (optional, fallback to in-process SQLite) ────────────

REDIS_AVAILABLE = False
try:
    import redis as _redis_module
    REDIS_AVAILABLE = True
except ImportError:
    pass

TASK_MAX_WORKERS = 3

import threading

class TaskQueue:
    """Simple in-process background task queue for video generation.
    In production, swap for Redis/Bull via the same interface."""
    
    def __init__(self, max_workers=TASK_MAX_WORKERS):
        self._queue = []
        self._results = {}
        self._lock = threading.Lock()
        self._workers = []
        self._max_workers = max_workers
        self._running = False
        self._sqlite_path = os.environ.get("TASK_DB_PATH", "/tmp/tiktok_tasks.db")
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite task store"""
        try:
            import sqlite3
            conn = sqlite3.connect(self._sqlite_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS video_tasks (
                    task_id TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'pending',
                    prompt TEXT,
                    provider TEXT,
                    model TEXT,
                    duration INTEGER,
                    aspect_ratio TEXT,
                    image_url TEXT,
                    face_image_url TEXT,
                    result TEXT,
                    error TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"SQLite task DB init failed: {e}")
    
    def enqueue(self, prompt: str, provider: str = "wavespeed", model_tier: str = "standard",
                duration: int = 8, aspect_ratio: str = "9:16",
                image_url: str = None, face_image_url: str = None) -> str:
        """Add task to queue, returns task_id"""
        import uuid
        task_id = f"vid_{uuid.uuid4().hex[:12]}"
        task = {
            "task_id": task_id, "status": "queued",
            "prompt": prompt, "provider": provider, "model": model_tier,
            "duration": duration, "aspect_ratio": aspect_ratio,
            "image_url": image_url, "face_image_url": face_image_url,
        }
        with self._lock:
            self._queue.append(task)
            self._save_task(task)
            self._maybe_spawn_worker()
        logger.info(f"Task {task_id} queued ({len(self._queue)} pending)")
        return task_id
    
    def get_status(self, task_id: str) -> dict:
        """Get task status from SQLite"""
        with self._lock:
            if task_id in self._results:
                return self._results[task_id]
        try:
            import sqlite3
            conn = sqlite3.connect(self._sqlite_path)
            row = conn.execute("SELECT * FROM video_tasks WHERE task_id=?", (task_id,)).fetchone()
            conn.close()
            if row:
                cols = [d[0] for d in conn.execute("PRAGMA table_info(video_tasks)")]
                return dict(zip(cols, row))
        except:
            pass
        return {"task_id": task_id, "status": "unknown"}
    
    def _save_task(self, task):
        try:
            import sqlite3
            conn = sqlite3.connect(self._sqlite_path)
            conn.execute(
                "INSERT OR REPLACE INTO video_tasks (task_id, status, prompt, provider, model, duration, aspect_ratio, image_url, face_image_url) VALUES (?,?,?,?,?,?,?,?,?)",
                (task["task_id"], task["status"], task.get("prompt"), task.get("provider"),
                 task.get("model"), task.get("duration"), task.get("aspect_ratio"),
                 task.get("image_url"), task.get("face_image_url")),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Save task failed: {e}")
    
    def _update_task(self, task_id, **kw):
        with self._lock:
            self._results[task_id] = kw
        try:
            import sqlite3
            conn = sqlite3.connect(self._sqlite_path)
            sets = ", ".join(f"{k}=?" for k in kw)
            vals = list(kw.values()) + [task_id]
            conn.execute(f"UPDATE video_tasks SET {sets}, updated_at=datetime('now') WHERE task_id=?", vals)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Update task failed: {e}")
    
    def _maybe_spawn_worker(self):
        active = sum(1 for w in self._workers if w.is_alive())
        if active < self._max_workers and self._queue:
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()
            self._workers.append(t)
    
    def _worker_loop(self):
        while True:
            task = None
            with self._lock:
                if not self._queue:
                    break
                task = self._queue.pop(0)
            if not task:
                break
            try:
                self._update_task(task["task_id"], status="processing")
                provider_enum = VideoProvider(task["provider"])
                result = generate_video_with_fallback(
                    prompt=task["prompt"],
                    duration=task["duration"],
                    aspect_ratio=task["aspect_ratio"],
                    image_url=task.get("image_url"),
                    face_image_url=task.get("face_image_url"),
                )
                self._update_task(task["task_id"], status="completed", result=str(result))
                logger.info(f"Task {task['task_id']} completed")
            except Exception as e:
                error_msg = str(e)[:500]
                self._update_task(task["task_id"], status="failed", error=error_msg)
                logger.error(f"Task {task['task_id']} failed: {e}")


# Global singleton
task_queue = TaskQueue()

def enqueue_video_task(prompt, provider="wavespeed", model_tier="standard", duration=8,
                       aspect_ratio="9:16", image_url=None, face_image_url=None) -> str:
    """Enqueue video generation and return task_id immediately"""
    return task_queue.enqueue(prompt, provider, model_tier, duration, aspect_ratio, image_url, face_image_url)


def get_task_status(task_id: str) -> dict:
    """Get task status from queue"""
    return task_queue.get_status(task_id)
