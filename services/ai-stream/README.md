# 🎙️ AI Live Streaming System

**CPU-only, Zero GPU, Zero Cost** — AI Live Stream with RAG Q&A + TTS

## Architecture

```
OBS/FFmpeg → RTMP (1935) → SRS → HLS (8083) → Viewers
                              ↓
                         [FastAPI :8150] ←→ Cloudflare Workers AI (ฟรี)
                              ↓
                         ChromaDB ← BookStack Knowledge Base
                              ↓
                         Edge-TTS → Audio response
```

## Services

| Service | Port | URL |
|---------|------|-----|
| AI Backend (FastAPI) | 8150 | `/api/` |
| SRS RTMP (OBS push) | 1935 | `rtmp://.../live/stream` |
| SRS HLS Stream | 8083 | `/hls/live/stream.m3u8` |
| SRS HTTP API | 1987 | `/srs-api/` |
| OBS Overlay | — | `/overlay` |
| WebPlayer | — | `/` |

## Quick Start

```bash
# 1. Start SRS (Docker)
cd /home/openhands/erp-stack/services/ai-stream
docker compose up -d srs

# 2. Start AI Backend
python3 server.py

# 3. OBS Settings
#    Server: rtmp://ai-stream.m2igen.com/live
#    Stream Key: stream
```

## API Endpoints

### RAG
- `GET /api/health` — Server health
- `GET /api/rag/search?q=...&k=5` — Search knowledge base
- `GET /api/rag/stats` — Collection stats
- `POST /api/rag/sync/bookstack` — Sync all BookStack
- `POST /api/rag/sync/page/{id}` — Sync single page

### Q&A
- `POST /api/ask` — Ask with RAG (non-stream)
- `POST /api/ask/stream` — Ask with SSE streaming

### TTS
- `GET /api/tts/voices?lang=th` — List voices
- `POST /api/tts` — Generate speech

### WebSocket
- `ws://host/ws/live/{session_id}` — Live chat with streaming Q&A

## Connecting to OBS

1. Open OBS Studio → Settings → Stream
2. **Service**: Custom
3. **Server**: `rtmp://ai-stream.m2igen.com/live`
4. **Stream Key**: `stream`
5. Start Streaming ✓

## OBS Overlay (Browser Source)

1. Add Browser Source in OBS
2. URL: `https://ai-stream.m2igen.com/overlay`
3. Width: 1920, Height: 1080
4. The overlay auto-shows questions & answers

## Web Player

เปิด `https://ai-stream.m2igen.com` — แสดงวิดีโอ + แชทสด + Q&A sidebar

## Cost Breakdown

| Component | Cost/Month |
|-----------|-----------|
| Cloudflare Workers AI (Llama 3.3 70B) | $0 |
| SRS Streaming Server (Docker) | $0 |
| ChromaDB (CPU, persistent) | $0 |
| Edge-TTS (Microsoft) | $0 |
| VPS (existing) | $0 |
| **Total** | **$0** 🎉 |

## Technical Details

- **LLM**: @cf/meta/llama-3.3-70b-instruct-fp8-fast (Cloudflare Workers AI)
- **Fallback**: Gemini 2.5 Flash
- **Embedding**: @cf/baai/bge-small-en-v1.5 (384-dim)
- **Vector DB**: ChromaDB PersistentClient
- **TTS**: edge-tts (th-TH-PremwadeeNeural / th-TH-NiwatNeural)
- **Streaming**: SRS v5 (RTMP → HLS)
