"""
TikTok UGC Studio — AI Video Generation Pipeline
Default: Prodia Wan 2.7 (img2vid+audio, $0.03)
Fallback: WaveSpeed Wan 2.2 ($0.08) -> Fal.ai ($0.10+)
"""

import os
import json
import base64
import time
import logging
from typing import Optional
from enum import Enum

import requests

logger = logging.getLogger("tiktok-ugc.video_gen")

# ─── Provider Configuration ────────────────────────────────────────────

class VideoProvider(str, Enum):
    PRODIA = "prodia"
    WAVESPEED = "wavespeed"
    FAL = "fal"

PROVIDER_CONFIG = {
    VideoProvider.PRODIA: {
        "key": os.environ.get("PRODIA_TOKEN", ""),
        "models": {"standard": "inference.wan2-7.img2vid.v1",
                    "t2v": "inference.wan2-7.txt2vid.v1"},
        "default_model": "inference.wan2-7.img2vid.v1",
        "base_url": "https://inference.prodia.com/v2",
        "image_to_video": True,
        "rate_limit_rps": 5,
        "estimate_cost": 0.03,  # $0.03/gen
    },
    VideoProvider.WAVESPEED: {
        "key": os.environ.get("WAVESPEED_API_KEY", ""),
        "models": {"standard": "wavespeed-ai/wan-2.2/t2v-480p-ultra-fast"},
        "default_model": "wavespeed-ai/wan-2.2/t2v-480p-ultra-fast",
        "base_url": "https://api.wavespeed.ai/api/v3",
        "image_to_video": False,
        "rate_limit_rps": 10,
        "estimate_cost": 0.08,  # ~$0.08 per 8s job
    },
    VideoProvider.FAL: {
        "key": os.environ.get("FAL_API_KEY", "") or os.environ.get("FAL_KEY", ""),
        "models": {
            "standard": "fal-ai/veo2",
            "fast-svd": "fal-ai/fast-svd",
            "kling": "fal-ai/kling-video",
            "minimax": "fal-ai/minimax-video",
            "haiper": "fal-ai/haiper-video",
            "luma": "fal-ai/luma-dream-machine",
        },
        "default_model": "fal-ai/veo2",
        "base_url": "https://fal.run",
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
                    # RuntimeError may not have .response (AttributeError guard)
                    resp = getattr(e, 'response', None)
                    if resp is not None and resp.status_code in retry_statuses:
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
    # Primary — Prodia Wan 2.7 ($0.03, lip sync built-in)
    (VideoProvider.PRODIA, "standard"),
    # Fallback — WaveSpeed Wan 2.2 ($0.08, no lip sync)
    (VideoProvider.WAVESPEED, "standard"),
    # Last resort — Fal.ai ($0.10+)
    (VideoProvider.FAL, "standard"),
    (VideoProvider.FAL, "kling"),
]

def generate_video_with_fallback(prompt, duration=8, aspect_ratio="9:16", image_url=None, face_image_url=None, **kw):
    """DISABLED: Video fallback ปิดอยู่ - ใช้ pipeline_affiliate.py แทน"""
    logger.warning("generate_video_with_fallback DISABLED - ใช้ pipeline_affiliate.py แทน")
    raise RuntimeError("Video fallback chain DISABLED - main pipeline (pipeline_affiliate.py) เท่านั้น")

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
    provider: VideoProvider = VideoProvider.PRODIA,
    model_tier: str = "standard",
    duration: int = 8,
    aspect_ratio: str = "9:16",
    image_url: Optional[str] = None,
    face_image_url: Optional[str] = None,
    timeout: int = 300,
    negative_prompt: Optional[str] = None,
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

    # Delegate to handler — _ws_generate handles 16s (2 scenes + concat) internally
    result = handler(config, prompt, model, duration, aspect_ratio, image_url, face_image_url, timeout, negative_prompt)
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
def _ws_generate(config, prompt, model, duration, aspect_ratio, image_url, face_image_url, timeout, negative_prompt=None):
    """WaveSpeed API v3 — Wan 2.2 T2V Ultra Fast.
    For 16s: generates 2 scenes, downloads immediately (CDN URLs expire!), concats via FFmpeg.
    """
    import uuid, subprocess, shutil, tempfile
    from pathlib import Path
    
    url = f"{config['base_url']}/wavespeed-ai/wan-2.2/t2v-480p-ultra-fast"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config['key']}"}
    
    scene_count = max(1, min(2, (duration + 7) // 8))  # 8s→1, 16s→2
    run_id = uuid.uuid4().hex[:8]
    tmp_dir = Path(tempfile.gettempdir()) / f"ws_scenes_{run_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    
    def _submit_scene(scene_prompt):
        """Submit one scene and poll until done, return video URL"""
        payload = {
            "prompt": scene_prompt,
            "size": "832*480",
            "duration": 8,
            "seed": -1,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if image_url:
            payload["reference_images"] = [image_url]
        
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"WaveSpeed error ({resp.status_code}): {resp.text[:500]}")
        data = resp.json()
        if data.get("code") != 200:
            raise RuntimeError(f"WaveSpeed submit failed: {data}")
        inner = data.get("data", {})
        prediction_id = inner.get("id", "")
        status_url = inner.get("urls", {}).get("get", "")
        if not status_url:
            raise RuntimeError(f"WaveSpeed: no status URL: {data}")
        
        # Poll
        for _ in range(60):
            time.sleep(5)
            sresp = requests.get(status_url, headers=headers, timeout=10)
            sdata = sresp.json()
            idata = sdata.get("data", {}) if sdata.get("code") == 200 else sdata
            st = idata.get("status", "")
            outs = idata.get("outputs", [])
            if st == "completed" and outs:
                return outs[0]
            elif st in ("failed", "error"):
                raise RuntimeError(f"WaveSpeed scene failed: {sdata}")
        raise TimeoutError("WaveSpeed scene timed out")
    
    def _download(url, path):
        """Download immediately — CDN URLs are temporary!"""
        r = requests.get(url, timeout=120)
        path.write_bytes(r.content)
        return path
    
    scene_prompts = [
        f"{prompt} [Scene 1: product showcase, establishing shot]",
        f"{prompt} [Scene 2: product usage, close-up details, action shot]",
    ]
    
    video_paths = []
    task_id = run_id
    
    for i in range(scene_count):
        logger.info(f"WaveSpeed scene {i+1}/{scene_count}...")
        video_url = _submit_scene(scene_prompts[i])
        logger.info(f"Scene {i+1} done, downloading...")
        vpath = tmp_dir / f"scene_{i}.mp4"
        _download(video_url, vpath)
        video_paths.append(str(vpath))
    
    final_url = ""
    storage_dir = Path(__file__).parent / "storage" / "videos"
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    if scene_count == 1:
        # Single scene — copy to persistent storage
        local_path = storage_dir / f"video_{run_id}.mp4"
        shutil.copy2(video_paths[0], local_path)
        final_url = f"/static/videos/video_{run_id}.mp4"
    else:
        # Concat 2 scenes via FFmpeg re-encode
        output_path = storage_dir / f"concat_{run_id}.mp4"
        
        list_file = tmp_dir / "concat.txt"
        with open(list_file, "w") as f:
            for vp in video_paths:
                f.write(f"file '{vp}'\n")
        
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        
        final_url = f"/static/videos/concat_{run_id}.mp4"
    
    # Cleanup temp
    shutil.rmtree(tmp_dir, ignore_errors=True)
    
    return {
        "task_id": task_id,
        "status": "completed",
        "video_url": final_url,
        "scene_count": scene_count,
        "duration": scene_count * 8,
    }


def _ws_status(config, task_id):
    """WaveSpeed API v3 — poll task result"""
    url = f"{config['base_url']}/predictions/{task_id}/result"
    headers = {"Authorization": f"Bearer {config['key']}"}
    resp = requests.get(url, headers=headers, timeout=30)
    body = resp.json()
    data = body.get("data", {}) or {}
    video_url = ""
    # v3 response shapes (all possible WaveSpeed formats):
    #   data.outputs[0]
    #   body.outputs[0]
    #   data.output.video_url or data.video_url
    #   data.output.video.url
    outputs = data.get("outputs", body.get("outputs", []))
    if outputs:
        video_url = outputs[0]
    if not video_url:
        output = data.get("output", {}) or {}
        video_url = output.get("video_url", "") or output.get("video", {}).get("url", "") or data.get("video_url", "")
    return {
        "task_id": task_id,
        "status": data.get("status", body.get("status", "unknown")),
        "video_url": video_url,
        "progress": 100 if data.get("status") == "completed" else 50 if data.get("status") == "processing" else None,
    }


@retryable(max_retries=3)
def _fal_generate(config, prompt, model, duration, aspect_ratio, image_url, face_image_url, timeout, negative_prompt=None):
    """Generate via fal.ai unified API

    fal.ai supports many backends: veo2, kling, minimax, haiper, luma, fast-svd
    All go through the same endpoint at fal.run.
    """
    url = f"{config['base_url']}/{model}"
    headers = {
        "Authorization": f"Key {config['key']}",
        "Content-Type": "application/json",
    }
    payload = {"prompt": prompt}
    if image_url:
        payload["image_url"] = image_url
    if duration:
        payload["duration"] = duration

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"fal.ai error ({resp.status_code}): {resp.text[:500]}")
    data = resp.json()
    # fal.ai returns immediate sync with video_url or async with request_id
    video_url = data.get("video", {}).get("url", "") or data.get("url", "")
    task_id = data.get("request_id", "") or data.get("id", "")
    return {
        "task_id": task_id,
        "status": "completed" if video_url else "pending",
        "video_url": video_url,
    }


@retryable(max_retries=3)
def _fal_status(config, task_id):
    """Check fal.ai async task status"""
    # fal.ai status endpoint — infer model from request ID lookup
    url = f"https://fal.ai/requests/{task_id}/status"
    headers = {"Authorization": f"Key {config['key']}"}
    resp = requests.get(url, headers=headers, timeout=30)
    data = resp.json()
    video_url = data.get("video", {}).get("url", "") or data.get("url", "")
    return {
        "task_id": task_id,
        "status": data.get("status", "unknown"),
        "video_url": video_url,
    }


# ─── Provider Dispatch Tables ─────────────────────────────────────────

_PROVIDER_HANDLERS = {
    VideoProvider.PRODIA: _ws_generate,  # Prodia uses same shape
    VideoProvider.WAVESPEED: _ws_generate,
    VideoProvider.FAL: _fal_generate,
}

_STATUS_HANDLERS = {
    VideoProvider.PRODIA: _ws_status,
    VideoProvider.WAVESPEED: _ws_status,
    VideoProvider.FAL: _fal_status,
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
    
    def enqueue_dummy(self, prompt: str, provider: str = "prodia", model_tier: str = "standard",
                      duration: int = 8, aspect_ratio: str = "9:16",
                      image_url: str = None, face_image_url: str = None) -> str:
        """Return fake completed task - video gen DISABLED"""
        import uuid
        tid = f"vt-{uuid.uuid4().hex[:8]}"
        self.tasks[tid] = {
            "id": tid, "status": "completed",
            "error": f"DISABLED: {provider}/{model_tier} ถูกปิด ใช้ pipeline_affiliate.py",
            "created_at": time.time(), "completed_at": time.time(),
        }
        return tid

    def enqueue(self, prompt: str, provider: str = "prodia", model_tier: str = "standard",
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
                self._update_task(task["task_id"], status="completed", result=json.dumps(result, default=str))
                logger.info(f"Task {task['task_id']} completed")
            except Exception as e:
                error_msg = str(e)[:500]
                self._update_task(task["task_id"], status="failed", error=error_msg)
                logger.error(f"Task {task['task_id']} failed: {e}")


# Global singleton
task_queue = TaskQueue()

def enqueue_video_task(prompt, provider="prodia", model_tier="standard", duration=8,
                       aspect_ratio="9:16", image_url=None, face_image_url=None) -> str:
    """DISABLED: Video queue ปิดอยู่ - ใช้ pipeline_affiliate.py แทน"""
    logger.warning("enqueue_video_task DISABLED - ใช้ pipeline_affiliate.py แทน")
    return task_queue.enqueue_dummy(prompt, provider, model_tier, duration, aspect_ratio, image_url, face_image_url)


def get_task_status(task_id: str) -> dict:
    """Get task status from queue"""
    return task_queue.get_status(task_id)
