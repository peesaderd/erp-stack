# TikTok UGC Studio (TUS) — Agent Operations Manual

> **⚠️ CRITICAL: Read this before ANY modification or generation**
> เวลาที่เสียไปแล้วเพราะ Agent ไม่เข้าใจระบบ = วันๆ
> อย่าให้ประวัติศาสตร์ซ้ำรอย

---

## 📋 Table of Contents
1. System Overview
2. Architecture
3. Pipeline Flow (v4.6)
4. 🔴 RED LINES (DO NOT)
5. ✅ DOs
6. All API Endpoints
7. Frontend (Web UI)
8. BGM System
9. TTS System
10. Image Prompt System
11. Script Generator
12. Scout (Trend Analysis)
13. Monitor (Performance Optimization)
14. Cost Breakdown
15. File Reference
16. Git History
17. Configuration
18. Deployment
19. Testing
20. Next Steps

---

## 1. System Overview

TikTok UGC Studio (TUS) = Web UI + API Backend + Pipeline สำหรับสร้างวิดีโอ UGC Affiliate อัตโนมัติ

**Production URLs:**
- Web UI: https://openhands.m2igen.com/tiktok/
- Static Images: https://openhands.m2igen.com/api/tiktok/ugc/static/images/
- Static Videos: https://openhands.m2igen.com/api/tiktok/ugc/static/videos/
- TUS API: http://localhost:8105

**Backend Services (PM2):**
| ID | Name | Port | Description |
|---|---|---|---|
| 5 | tiktok-ugc-studio | 8105 | 🎯 Main API + Pipeline backend |
| 0 | image-gen | 8110 | Image generation (Prodia, Klein 9B) |
| 3 | tiktok-frontend | 8120 | Web UI frontend |
| 4 | product-scraper | 8106 | Scrape product URLs |
| 6 | modules-auth | - | Authentication |
| 7 | modules-media | - | Media storage |
| 8 | modules-product | - | Product data |
| 9 | **scheduler** | **8130** | 🆕 Auto-post scheduler + background worker |
| 10 | **drive-service** | **8132** | 🆕 Google Drive + Sheets media uploader |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Web UI (tiktok-frontend :8120)                              │
│  - React app (993 files)                                    │
│  - Content Wizard (4 steps: Product → Script → Style → Gen) │
└──────────────────────┬──────────────────────────────────────┘
                       │ POST /video/generate
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ tiktok-ugc-studio (:8105)                                    │
│  main.py - FastAPI backend (126+ endpoints)                  │
│    ↓ spawns background thread                                │
│  pipeline_affiliate.py - Core pipeline                        │
│    ├── sam3_client.py - SAM3 image analysis                   │
│    ├── image_prompt_builder.py - Dynamic prompt generation    │
│    ├── bgm_fetcher.py - Auto-download BGM                     │
│    ├── script_gen.py - AI script generation                   │
│    ├── tts_gen.py - Text-to-speech (gTTS)                     │
│    └── fal_client.py - Fal.ai API client                      │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ image-gen (:8110) - Prodia/Klein 9B image generation         │
│ Fal.ai API - Wan 2.7 video, MiniMax TTS                     │
│ Prodia API - SAM3, FLUX, Klein 9B                            │
└─────────────────────────────────────────────────────────────┘
```

**External Services:**
- **Prodia** — SAM3 (image analysis), FLUX (txt2img), Klein 9B (img2img), Wan 2.7 (img2vid)
- **Fal.ai** — Wan 2.7 (img2vid), MiniMax Speech 2.8 HD (TTS)
- **Mixkit CDN** (free) — BGM background music
- **DeepSeek** (optional, via LLM_API_KEY) — AI script generation
- **Google Drive API** — Upload composed videos + generated images
- **Google Sheets API** — Media log tracking

---

## 3. Pipeline Flow (v4.6)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PIPELINE v4.6                                 │
│ Cost: ~$0.09/clip (8s, 1 scene)                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Step 0: SAM3 Analyze Product Image ($0.0011)                       │
│    ↓ วิเคราะห์ object detection, safe zones, prompt insights          │
│  Step 1: Klein 9B Img2Img ($0.005)                                   │
│    ↓ สร้างรูป UGC จากสินค้า (img2img = product เป็น reference)       │
│  Step 1b: SAM3 Analyze UGC Image ($0.0011)                          │
│    ↓ วิเคราะห์รูปที่สร้าง ตรวจสอบ objects ถูกต้อง                    │
│  Step 2: MiniMax 2.8 HD TTS (~$0.054)                               │
│    ↓ voice_id=lovely_girl, language_boost=Thai                       │
│  Step 3: Wan 2.7 img2vid ($0.03)                                     │
│    ↓ silent video, "mouth closed, not speaking" prompt                │
│  Voice Merge: FFmpeg mix voice audio into video                      │
│  Step 5: BGM (Mixkit free, volume=0.50)                              │
│    ↓ bgm_fetcher auto-downloads if missing                           │
│  RESULT: ~8s MP4 with voice + BGM                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Pipeline Entry Point:**
1. User clicks "🚀 Generate Video" in Web UI Content Wizard (Step 4)
2. Frontend → `POST /video/generate` (in `main.py` line 1106)
3. Spawns background thread → calls `pipeline_affiliate.run_pipeline()`
4. Frontend polls `GET /video/status/{job_id}` for completion

**Pipeline Code:** `tiktok-ugc-studio/pipeline_affiliate.py`
- `run_pipeline()` — main orchestrator (line 460+)
- `sam3_analyze_image()` — SAM3 analysis (line 125+)
- `generate_image()` — Image generation via image-gen service (line 220+)
- `generate_voice()` — MiniMax TTS via Fal.ai (line 270+)
- `generate_video()` — Wan 2.7 img2vid (line 305+)

---

## 4. 🔴 RED LINES — DO NOT

| # | Rule | Why |
|---|---|---|
| 1 | **DO NOT hardcode image prompts** | System has `image_prompt_builder.py` that generates dynamic prompts by product category. Always use `scene_prompts` from Web UI or call `build_prompt()`. |
| 2 | **DO NOT bypass Web UI** | No curl/API direct calls for testing. Web UI Content Wizard only. |
| 3 | **DO NOT fabricate features** | Check code before claiming a feature exists. Never guess voice IDs, API endpoints, or configuration values. |
| 4 | **DO NOT generate without user permission** | Always ask before clicking "Generate Video". |
| 5 | **DO NOT send output without inspecting** | Check generated images and videos before presenting results to user. |
| 6 | **DO NOT pay unnecessarily** | Free sources first (Mixkit for music, Pixabay for images). Fal.ai and Prodia have costs. |
| 7 | **DO NOT modify existing systems without reading them first** | Read AGENT_OPS.md, then `image_prompt_builder.py`, `script_gen.py`, `bgm_fetcher.py` before writing new code. |
| 8 | **DO NOT add BGM in two places** | Pipeline already handles BGM in Step 5. main.py must NOT add BGM again. |
| 9 | **DO NOT use Edge TTS** | User rejected it. Current TTS = MiniMax 2.8 HD with `lovely_girl` + `language_boost=Thai`. |
| 10 | **DO NOT assume file existence** | BGM files are at `bgm/` directory (git tracked). Static storage is at `storage/` (gitignored). |
| 11 | **DO NOT test without user's explicit go-ahead** | User has been angry about unauthorized generations. Always wait for explicit approval. |

---

## 5. ✅ DOs

| # | Rule |
|---|---|
| 1 | Use Web UI for all pipeline testing |
| 2 | Read AGENT_OPS.md before any modification |
| 3 | Check `image_prompt_builder.py` before writing custom prompts |
| 4 | Use `scene_prompts` from Web UI as image/video prompts |
| 5 | Inspect image + video output before showing to user |
| 6 | Verify cost impact before running pipeline |
| 7 | Pass `bgm_style` to `affiliate_run()` for pipeline-managed BGM |
| 8 | Use `bgm_fetcher.fetch_bgm()` for auto-download if BGM missing |
| 9 | Commit + push + pm2 restart after every change |
| 10 | Check `storage/` is .gitignored — put persistent data elsewhere |

---

## 6. All API Endpoints

### Script Generation
| Method | Path | Description |
|---|---|---|
| POST | `/scripts/generate` | Generate TikTok review script (AI or template) |
| POST | `/scripts/ugc` | Generate UGC video prompt by style |
| POST | `/scripts/generate-with-affiliate` | Script + affiliate links |
| GET | `/scripts/variations` | Available hook/tone/CTA variations |
| GET | `/scripts/templates` | List script templates |

### Video Pipeline
| Method | Path | Description |
|---|---|---|
| **POST** | **`/video/generate`** | **🎯 Main pipeline entry point** — full UGC generation |
| GET | `/video/status/{job_id}` | Check pipeline job status |
| POST | `/video/status` | Check video gen status (legacy) |
| GET | `/video/providers` | List providers, presets, options |
| POST | `/video/queue` | Enqueue video task (DISABLED!) |
| POST | `/video/queue-status` | Check queued task (DISABLED!) |
| POST | `/video/concat` | Concat videos (legacy) |
| POST | `/video/generate-with-fallback` | **DISABLED** — raises error |

### Image Generation
| Method | Path | Description |
|---|---|---|
| POST | `/images/generate` | Generate product image |
| POST | `/images/build-prompt` | **🎯 Dynamic prompt builder** (use this!) |
| POST | `/images/generate-enhanced` | Build prompt + generate image |
| POST | `/images/remove-bg` | Remove background |
| POST | `/images/edit` | Edit image |
| POST | `/images/upscale` | Upscale image |
| GET | `/images/templates` | List image templates |
| POST | `/images/product` | Product-specific image gen |

### TTS
| Method | Path | Description |
|---|---|---|
| POST | `/tts/generate` | Generate TTS audio (gTTS) |
| POST | `/tts/script` | Generate TTS for full script segments |

### Product Analysis
| Method | Path | Description |
|---|---|---|
| POST | `/product/analyze` | Analyze product via Mistral (multipart) |
| POST | `/product/scrape-and-generate` | Scrape URL + generate script |

### Pipeline DB
| Method | Path | Description |
|---|---|---|
| GET | `/pipeline/{job_id}/status` | Pipeline job status |
| GET | `/pipeline/list` | List pipeline jobs |
| POST | `/pipeline/run` | Run full pipeline (TTS→video→compose) |

### Scout (Trend Analysis)
| Method | Path | Description |
|---|---|---|
| GET | `/scout/trends` | Discover trending content |
| POST | `/scout/analyze` | Analyze video/viral structure |
| POST | `/scout/compare` | Compare with competitors |
| GET | `/scout/templates` | List content templates |
| POST | `/scout/templates/generate` | Generate script from template |
| POST | `/scout/clone` | Clone trending structure |
| POST | `/scout/keywords` | Search trending keywords |
| POST | `/scout/extract` | Extract trending elements |
| GET/POST/DELETE | `/scout/targets/*` | Scout target CRUD |
| POST | `/scout/targets/analyze` | Batch analyze targets |

### Monitor (Optimization)
| Method | Path | Description |
|---|---|---|
| GET | `/monitor/performance` | Video performance summary |
| GET | `/monitor/videos` | Published videos with analytics |
| POST | `/monitor/analytics/record` | Record analytics data |
| GET | `/monitor/strategy` | Get current strategy |
| POST | `/monitor/strategy/update` | Update strategy parameters |
| POST | `/monitor/strategy/reset` | Reset strategy to defaults |
| POST | `/monitor/optimize` | Run full optimization loop |

### Google Sheets Import
| Method | Path | Description |
|---|---|---|
| GET | `/products/sheets/status` | Check Google Sheets credentials status |
| POST | `/products/sheets/connect` | Test connection to a spreadsheet |
| POST | `/products/sheets/import` | Import products from Sheet → TUS DB |

### Scheduled Posts
| Method | Path | Description |
|---|---|---|
| GET | `/posts/scheduled` | List scheduled posts (proxy → scheduler :8130) |
| DELETE | `/posts/scheduled/{id}` | Cancel a pending scheduled post |

### Drive & Sheets (Media Logger)
| Method | Path | Description |
|---|---|---|
| GET | `/drive/connect` | Check drive-service health & credentials |
| POST | `/drive/config` | Set MEDIA_SHEET_ID for auto-logging |

### Other
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/export` | Export asset |
| GET | `/prompts/list` | List prompt files |
| GET | `/prompts/{path}` | Get prompt file content |
| GET | `/affiliate/config` | Get affiliate link config |
| GET | `/api/image-proxy` | Image proxy (CORS) |

---

## 7. Frontend (Web UI)

**Location:** `tiktok-ugc-studio/frontend/` (React, ~993 files)
**Served by:** PM2 service `tiktok-frontend` (ID 3, port 8120)
**URL:** https://openhands.m2igen.com/tiktok/

**Navigation:**
- 📊 Dashboard
- 🎯 Products — เลือกสินค้า → Create Video
- 🎬 Content — Content Wizard (4 steps)
- 📦 Pipeline — Pipeline configuration
- 📊 Social — Social accounts
- 📱 Accounts — TikTok account management
- 📋 History — Pipeline run history
- ⚙️ Settings

**Content Wizard Flow:**
1. **Product** — Select product, auto-fill from product data
2. **Script** — Generate script (hook/value/cta), edit manually
3. **Summary** — Review scene prompts, UGC style, sound style, mood
4. **Generate** — Click "🚀 Generate Video" → calls `/video/generate`

---

## 8. BGM System

**Files:** `tiktok-ugc-studio/bgm/*.mp3` (git TRACKED — never lost on redeploy)

**Auto-fetcher:** `bgm_fetcher.py`
- Called by pipeline `Step 5`
- If BGM file exists → use cache
- If missing → auto-download from Mixkit CDN: `https://assets.mixkit.co/music/{id}/{id}.mp3`
- Multiple track IDs per style, shuffled randomly each run

**Track IDs:**
```
chill_loft:     494 (Lofi Chill, 99s, -16.3 dB), 16, 25, 256, 1077, 510
jazz:           493 (Jazz, 97s, -14.5 dB), 39, 24, 752, 644, 89
edm:            371 (EDM, 124s, -13.8 dB), 113, 124, 181, 157, 629
upbeat_pop:     644 (Upbeat, 110s, -13.5 dB), 528, 652, 820
asmr:           16 (Ambient, 124s, -17.4 dB), 494, 510, 1077
```

**Volume:** `volume=0.50` (in `[1:a]volume=0.50[bg]` FFmpeg filter)

**To add more tracks:**
1. Go to https://mixkit.co/free-stock-music/{style}/
2. Find a track, get its ID from the URL
3. Add ID to `STYLE_TRACKS` in `bgm_fetcher.py`
4. Commit + push

---

## 9. TTS System

| Provider | Voice ID | Cost | How |
|---|---|---|---|
| **MiniMax 2.8 HD** ✅ | **`lovely_girl`** + `language_boost=Thai` | **~$0.10/1K chars** | Fal.ai API |
| ~~MiniMax 2.8 HD~~ ❌ | ~~thai_female~~ | ~~$0.10/1K chars~~ | voice ID ไม่มีจริง — ห้ามใช้! |
| ~~Edge TTS~~ ❌ | ~~th-TH-PremwadeeNeural~~ | ~~$0~~ | User rejected — เสียงไม่ดีเท่า MiniMax |

**Code:** `pipeline_affiliate.py` `generate_voice()` (line 270+)
**API Endpoint:** MiniMax Speech 2.8 HD via `https://fal.run/fal-ai/minimax/speech-2.8-hd`
**Voice cost calc:** `(len(script) / 1000) * 0.10`

---

## 10. Image Prompt System

**DO NOT hardcode image prompts.** The system has a dynamic prompt builder:

**File:** `image_prompt_builder.py`
**Function:** `build_prompt(product_name, description, ugc_style, mistral_analysis)`

**How it works:**
1. Analyze product category (beauty, skincare, food, fashion, electronics, etc.)
2. Determine model attributes (gender, age, setting)
3. Determine lighting (product studio, makeup, natural, lifestyle)
4. Build UGC-style specific prompt (holding, usage, review, talking)
5. Add Mistral analysis if available (from `/product/analyze`)

**Usage:**
```python
from image_prompt_builder import build_prompt
result = build_prompt(
    product_name="BEAUTILAB Concealer",
    description="Brightening concealer...",
    ugc_style="holding"
)
prompt = result["prompt"]       # Dynamic, varies by product
aspect = result["aspect_ratio"] # 9:16
gender = result["model_gender"] # female, male, unisex
```

**OR** use the API endpoint:
`POST /images/build-prompt` with product_name, description, ugc_style

**IMPORTANT:** In `main.py` `/video/generate`, the `img_prompt` is now set to `scene_prompts[0]` (the AI-generated scene prompt from Web UI). Do NOT replace this with hardcoded text.

---

## 11. Script Generator

**File:** `script_gen.py`
**Purpose:** Generate Hook + Value + CTA + Scene + Voice scripts

**Flow:**
1. Tries LLM (DeepSeek) if `LLM_API_KEY` is set in environment
2. Falls back to prompt templates in `prompts/` directory

**Prompt Files:** `tiktok-ugc-studio/prompts/`
- `system.prompt.txt` / `system_16s.prompt.txt` — System prompt
- `master.prompt.txt` / `master_16s_3step.prompt.txt` — Master template
- `user.template.prompt.txt` / `user_16s.prompt.txt` — User template
- `variation.json` — Hook/tone/CTA variations
- `tiktok_review_prompts.json` — Review prompts
- `UGC_prompts/` — UGC style prompts

**API Endpoints:**
```python
POST /scripts/generate    # Generate script
POST /scripts/ugc         # Generate UGC prompt
```

**DO NOT** write custom script generators. Use the existing system.

---

## 12. Scout (Trend Analysis)

**Purpose:** Analyze TikTok trends, viral content, competitor analysis
**Files:** `tiktok-ugc-studio/scout/` directory

**Key Files:**
- `scout/trends.py` — Discover trends, analyze viral structure, search keywords
- `scout/analyzer.py` — Analyze videos, compare competitors, extract elements
- `scout/targets.py` — Target account management (CRUD)
- `scout/templates.py` — Content templates and cloning

**Usage:** API endpoints under `/scout/*` (see Section 6)

---

## 13. Monitor (Performance Optimization)

**Purpose:** Track video performance, optimize content strategy
**Files:** `tiktok-ugc-studio/monitor/` directory

**Key Files:**
- `monitor/tracker.py` — Record and query video analytics
- `monitor/optimizer.py` — Analyze performance, update strategy

**Usage:** API endpoints under `/monitor/*` (see Section 6)

---

## 14. Cost Breakdown

| Component | Cost | Provider | Notes |
|---|---|---|---|
| SAM3 (product image) | $0.0011 | Prodia | Step 0 |
| SAM3 (UGC image) | $0.0011 | Prodia | Step 1b |
| Klein 9B (img2img) | $0.005 | Prodia | Step 1 |
| MiniMax TTS | ~$0.054 | Fal.ai | Step 2, ~540 chars |
| Wan 2.7 (video) | $0.03 | Prodia | Step 3, per 8s clip |
| BGM | $0 | Mixkit CDN | Free, royalty-free |
| **Total (1 scene, 8s)** | **~$0.09** | | |
| **Total (2 scenes, 16s)** | **~$0.15** | | (double video + extra SAM3) |

---

## 15. File Reference

| File | Purpose | Key Functions |
|---|---|---|
| `main.py` | FastAPI backend (126+ endpoints) | Entry point for all API calls |
| `pipeline_affiliate.py` | Core pipeline orchestrator | `run_pipeline()`, `generate_voice()`, `generate_video()` |
| `image_prompt_builder.py` | Dynamic image prompt generation | `build_prompt()`, `_build_component_prompt()` |
| `script_gen.py` | AI script generation | `generate_tiktok_review_script()`, `_call_llm()` |
| `bgm_fetcher.py` | Auto-download BGM from Mixkit | `fetch_bgm()` |
| `fal_client.py` | Fal.ai API client | Wan 2.7, MiniMax |
| `tts_gen.py` | TTS via gTTS | `text_to_speech()`, `script_to_speech()` |
| `sam3_client.py` | SAM3 image analysis client | `segment_image()`, `track_object_in_video()` |
| `composer.py` | Video composition (legacy) | `compose_video()`, `add_sound_effects()` |
| `../modules/scheduler/main.py` | Auto-post scheduler service (:8130) | `schedule_post()`, `_worker_loop()` polling every 60s |
| `../modules/drive_service/main.py` | Google Drive + Sheets media logger (:8132) | `drive_upload()`, `sheets_log_media()`, `drive_list()` |
| `../modules/product/export_service.py` | Google Sheets export (shared creds) | `export_products_to_sheet()`, `is_ready()` |
| `video_gen.py` | Video gen (legacy/DISABLED) | `generate_video_with_fallback()` — DISABLED |
| `AGENT_OPS.md` | **This file** | Operations manual |
| `bgm/` | BGM music files (git tracked) | 5 files, ~3-4MB each |
| `storage/` | Generated assets (gitignored) | images/, videos/, tts/, sounds/ |
| `prompts/` | LLM prompt templates | system, master, user templates |
| `scout/` | Trend analysis module | trends, analyzer, targets, templates |
| `monitor/` | Performance optimization | tracker, optimizer |
| `frontend/` | React Web UI (~993 files) | Content Wizard |
| `design/` | Design assets | Static design files |
| `sessions/` | Session storage | User sessions |

---

## 16. Git History

| Commit | v | Summary | Cost |
|---|---|---|---|
| `60ffb4c` | 4.2 | Initial Prodia-only pipeline | - |
| `055d727` | - | Klein 9B image route | - |
| `2801129` | - | Cleanup unused services | - |
| `a28b567` | - | Disable WaveSpeed/Fal.ai chain | - |
| `8a0b762` | - | MiniMax 2.8 HD upgrade | - |
| `1fbc430` | 4.3 | lovely_girl voice, BGM=0.80 | $0.077 |
| `24b83e2` | 4.4 | Edge TTS Thai (FREE) | $0.037 |
| `4715bc0` | 4.5 | Revert to MiniMax (user rejected Edge) | $0.077 |
| `561cda3` | - | BGM volume fix (0.80→3.0) | - |
| `faed2c6` | 4.6 | Dynamic prompts, no double BGM | $0.09 |
| `d25f459` | - | Real BGM from Mixkit (volume=0.50) | - |
| `7b0bb43` | - | BGM to git-tracked bgm/ dir | - |
| `a311ace` | - | bgm_fetcher auto-download | - |
| `28a936b` | - | AGENT_OPS.md documentation | - |
| `40f08f9` | - | Micro-service refactor: scheduler (:8130) + Google Sheets import + scheduled UI | - |
| `4d63f81` | - | Google Drive + Sheets media logger (:8132) + auto-upload on video compose | - |

---

## 17. Configuration

**Environment Variables:**
| Variable | Purpose | Set in |
|---|---|---|
| `FAL_API_KEY` / `FAL_KEY` | Fal.ai API (video, TTS) | `.env` |
| `PRODIA_TOKEN` / `PRODIA_KEY` | Prodia API (SAM3, FLUX, Klein, Wan) | `.env` |
| `LLM_API_KEY` | DeepSeek/LLM API (script gen) | `.env` (optional) |
| `LLM_BASE_URL` | Custom LLM endpoint | `.env` (optional) |
| `LLM_MODEL` | LLM model name | `.env` (optional) |

**Loading:** `main.py` loads `.env` from `tiktok-ugc-studio/.env` on startup

**New service env vars (from `.env` or shell):**
| Variable | Default | Service | Purpose |
|---|---|---|---|
| `SCHEDULER_API` | `http://localhost:8130` | tiktok-ugc-studio | Scheduler endpoint |
| `DRIVE_API` | `http://localhost:8132` | tiktok-ugc-studio | Drive service endpoint |
| `MEDIA_SHEET_ID` | `""` | tiktok-ugc-studio | Google Sheet ID for media log |
| `TUS_API` | `http://localhost:8105` | scheduler | TUS endpoint for worker callback |

---

## 18. Deployment

```bash
# After code changes — deploy all:
cd /home/openhands/erp-stack
git add -A
git commit -m "description"
git push

# OR full deploy via ecosystem config (recommended):
pm2 restart /home/openhands/erp-stack/tiktok-ugc-studio/ecosystem.config.js

# OR individual restart:
# tiktok-ugc-studio = main backend (port 8105)
pm2 restart tiktok-ugc-studio
# scheduler = auto-post (port 8130)
pm2 restart scheduler
# drive-service = Drive + Sheets (port 8132)
pm2 restart drive-service
# image-gen (port 8110)
pm2 restart image-gen
# tiktok-frontend (port 8120)
pm2 restart tiktok-frontend
```

**To check service status:**
```bash
pm2 status 5 0 3 9 10
```

**To restart all TUS services:**
```bash
# Full restart (3 new services)
pm2 restart tiktok-ugc-studio scheduler drive-service
```

**To view logs:**
```bash
tail -f /home/openhands/.pm2/logs/tiktok-ugc-studio-error.log
```

---

## 19. Testing

### Web UI Test Flow
1. Open https://openhands.m2igen.com/tiktok/
2. Navigate: Products → 🎬 Create Video
3. Content Wizard opens with product auto-filled
4. Step 2: Click "📝 Generate Script" → AI gen hook/value/cta
5. Edit if needed → Next
6. Step 3: Review summary (scene prompts, sound, mood)
7. Step 4: Click "🚀 Generate Video"
8. Wait ~1-2 minutes (SAM3 → Klein → MiniMax → Wan → FFmpeg)
9. Check result image + video BEFORE sending to user

### What to Check Before Sending to User
1. **Image:** Does the model face look different per product? Is the product visible and correct?
2. **Video:** Is the motion smooth? Is mouth closed (no speaking)?
3. **Audio:** Can you hear voice + BGM? BGM not too loud/quiet?
4. **Cost:** What's the total? Acceptable?

---

## 20. Next Steps (สิ่งที่ต้องทำต่อ)

### 🆕 Drive & Sheets Setup Checklist
- [ ] Place `sheets_credentials.json` at `modules/product/sheets_credentials.json`
- [ ] Enable Google Drive API + Google Sheets API in GCP Console
- [ ] Share Google Drive folder with service account email
- [ ] Share Google Sheet with service account email
- [ ] Set spreadsheet ID via: `curl -X POST http://localhost:8105/drive/config -H 'Content-Type: application/json' -d '{"spreadsheet_id":"YOUR_ID"}'`
- [ ] Verify: `curl http://localhost:8105/drive/connect`

### Todo
- [ ] Config/template system for pipeline recipes (save different pipeline configs)
- [ ] Add more BGM track IDs to `bgm_fetcher.py` (currently 5-6 per style)
- [ ] Script shortening — AI scripts are too long (540+ chars → expensive TTS)
- [ ] Re-evaluate GPT Image 2 + SAM3 inpaint approach (optional, higher quality)
- [ ] Product photo diversity — ensure each product generates different model faces
- [ ] Add Pixabay music as secondary BGM source (fallback if Mixkit CDN fails)

### ✅ Completed
- [x] Scheduler micro-service (:8130) — auto-post background worker
- [x] Google Sheets product import — status/connect/import endpoints
- [x] Drive & Sheets media logger (:8132) — auto-upload composed videos
- [x] Frontend: Scheduled tab, Sheets import UI, schedule datetime picker
- [x] Post-scheduling with date/time picker (immediate vs scheduled)

### Known Issues
- Script is too long → costs more for MiniMax TTS ($0.054 instead of $0.02-0.03)
- Some Klein 9B outputs have similar faces across products (same seed?)
- BGM files are 2-4 minutes but only 8s is used (trimmed by FFmpeg -shortest)
- Drive service needs `sheets_credentials.json` — same file as Sheets import

---

## 📝 Quick Start for New Agents

**If you're a new agent and have never worked on this system:**

1. **Read this file fully** — don't skip any section
2. Read the RED LINES (Section 4) twice
3. Look at the pipeline flow (Section 3)
4. Check the existing systems BEFORE writing new code:
   - `image_prompt_builder.py` — dynamic prompt system exists!
   - `script_gen.py` — script generator exists!
   - `bgm_fetcher.py` — BGM auto-downloader exists!
5. Ask user before ANY generation
6. Inspect ALL output before sending to user
7. Commit + push + restart after changes

**Remember:** Previous agents wasted days by not reading the system first.
Don't be that agent.

---

*Document updated: 2026-06-16*
*Maintained by: Agent operations — update this file when system changes*
