# TikTok UGC Studio — Architecture

> ⚠️ **Read this first** before modifying any code.
> This is a **microservice architecture** — each service has ONE job.
> Do NOT cross service boundaries in code.

---

## Service Map

```
                     ┌──────────┐
                     │  Nginx   │ :443 (openhands.m2igen.com)
                     └────┬─────┘
                          │
        ┌─────────────────┼──────────────────┐
        ↓                 ↓                   ↓
   /tiktok/          /api/tiktok/         /api/auth/
   static files      /api/ (general)      /api/etsy/
        │                 │                   │
        └────────→ ┌──────┴──────┐ ←─────────┘
                   │  main.py    │
                   │  :8105      │  ← API Gateway
                   │  Orchestrator│
                   └──┬───┬───┬──┘
                      │   │   │
          ┌───────────┘   │   └───────────┐
          ↓               ↓               ↓
    ┌──────────┐   ┌──────────┐   ┌──────────────┐
    │ image-gen│   │  video   │   │prompt-builder│
    │ :8110    │   │  :8111   │   │   :8117      │
    └──────────┘   └──────────┘   └──────────────┘
    Nano Banana     Script Gen     Image Prompt
    (img2img)       TTS (Gemini)   Video Prompt
                    Wan 2.7 I2V    Negative Prompt
                    Compose
```

## Service Registry

| Service | Port | Code Location | Job |
|---------|------|---------------|-----|
| **tiktok-ugc-studio** | 8105 | `tiktok-ugc-studio/main.py` | API Gateway, frontend serving, pipeline orchestration |
| **image-gen** | 8110 | `modules/image/` | Image generation (Prodia Nano Banana) |
| **video** | 8111 | `modules/video/` | Script gen, TTS, Wan 2.7 video gen, FFmpeg compose |
| **prompt-builder** | 8117 | `prompt-builder-service/` | Image + Video prompt generation via Gemini |
| **auth** | 8101 | `modules/auth/` | Auth (register, login, OAuth) |
| **etsy-wizard** | 8104 | `etsy-wizard/` | Etsy/POD wizard (separate product) |
| **erp-core** | 54532 | `erp-core/` | ERP backend (POS, inventory, etc.) |

## How Services Talk

```
main.py (8105) → _proxy("POST", "video", ...)
                     → httpx → http://localhost:8111/api/v1/...

main.py (8105) → _proxy("POST", "prompt-builder", ...)
                     → httpx → http://localhost:8117/api/v1/build
```

`_proxy()` is defined in `main.py:50`. It normalizes all responses to `{ok, status, data, error}`.

## Pipeline Flow

```
1. Product Data (from user input / scraper / Google Sheets)
        ↓
2. Script Gen → video:8111 /api/v1/scripts/ugc
        ↓
3. TTS → video:8111 /api/v1/tts/generate
        ↓
4. Prompt Builder → prompt-builder:8117 /api/v1/build
        ↓
5. Image Gen → image-gen:8110 (Nano Banana img2img)
        ↓
6. Video Gen → video:8111 /api/v1/video/generate (Wan 2.7)
        ↓
7. Compose → video:8111 (FFmpeg: video + audio + BGM)
        ↓
8. Output → .mp4 ready for TikTok
```

## Key Files

| File | Role |
|------|------|
| `main.py` | API Gateway + Pipeline Orchestrator (1746 lines → refactored from 4600+) |
| `pipeline_affiliate.py` | Full pipeline: analyze → script → image → video → compose |
| `prodia_client.py` | Shared Prodia API client (global, used by all modules) |
| `recipes/*.json` | Recipe definitions (scene count, duration, style) |
| `frontend/public/index.html` | TikTok Studio Web UI |

## Frontend Serving

```
/tiktok/           → frontend/public/ (static HTML/JS/CSS)
/tiktok/static/    → frontend/public/
/tiktok/storage/   → storage/ (user uploads, generated videos)
```

## ⛔ Cross-Service Rules

1. **main.py** orchestrates — it does NOT generate images, videos, or prompts
2. **image-gen:8110** only generates images — no scripts, no video
3. **video:8111** handles scripts, TTS, video gen, compose — no image gen
4. **prompt-builder:8117** only builds prompts — no generation
5. **Always use `_proxy()`** to call another service, never import directly
