# TikTok UGC Studio — Work Plan (P1 → P5)

## Architecture Decision
- Frontend: **Embedded in bos-gateway** (Express serves /tiktok/)
- TikTok API proxy: Already at /api/tiktok/ → :8105
- Dashboard URL: https://openhands.m2igen.com/tiktok/
- Figma: Rate limited for 4 days → Design from scratch using unified UI

---

## P1: Negative Prompt + Enhanced UX/UI (NOW)

### Backend
- [ ] Add `negative_prompt` field to `/video/generate` endpoint
- [ ] Make negative_prompt API-configurable per request (not just file-based)
- [ ] UGC prompts: separate negative prompt from system prompt cleanly
- [ ] Response includes negative_prompt used for traceability

### Frontend (TikTok Mobile Dashboard)
- [ ] Redesign from scratch — Unified UI (clean dark mode, neon accents)
- [ ] **Dashboard page** — Credit balance, recent jobs, quick actions
- [ ] **New Content page** — Step-by-step wizard (UGC Flow)
- [ ] **Pipeline page** — Visual pipeline status (Scrape → Script → Gen Video → Upload)
- [ ] **Sidebar navigation** (replaces current tabs)
- [ ] **Negative prompt field** visible in advanced options

---

## P2: Workflow + Pipeline (Clear & Visible)

### Backend
- [ ] `/tiktok/pipeline` — rewrite to return detailed step tracking
- [ ] Pipeline: Job ID + status per step (scrape, script, video, upload)
- [ ] Add pipeline job queue (no Redis — use SQLite + background thread)
- [ ] Add `/pipeline/{job_id}/status` endpoint

### Frontend
- [ ] Pipeline monitor page — live status per step
- [ ] Cancel/retry per step
- [ ] History of past pipeline runs

---

## P3: UGC Style Templates + Product Scraper Integration

### Backend
- [ ] Template library management (CRUD)
- [ ] Auto-category detection → suggest template
- [ ] Full pipeline: URL → Scrape → Script → Video → Upload (one click)

### Frontend
- [ ] Template browser / picker
- [ ] "Quick Post" — paste URL, select template, one-click go

---

## P4: Asset Library + Schedule Management

### Backend
- [ ] Asset storage (local + path tracking)
- [ ] Schedule CRUD (create, list, cancel)
- [ ] Background scheduler (Python APScheduler or simple loop)

### Frontend
- [ ] Asset Library page (images + videos)
- [ ] Schedule calendar view
- [ ] Cancel/reschedule

---

## P5: Payment + Credit System

### Backend
- [ ] Credit model (user has credits, deduct per action)
- [ ] Payment integration with existing bos payment system
- [ ] Webhook to top-up credits

### Frontend
- [ ] Credit balance display (sidebar + header)
- [ ] Top-up page with packages
- [ ] Payment flow (QR code, confirm)

---

## Tech Stack Per P1
- Backend: Python FastAPI (existing)
- Frontend: Vanilla HTML/CSS/JS (no build step — deliver fast)
- Design: Dark mode, neon gradient (#ff2a6d → #05d9e8), card-based
- Deploy: PM2 tiktok-frontend (already running)
