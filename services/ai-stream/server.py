"""
AI Live Streaming Backend — RAG Q&A + TTS + WebSocket
CPU-only, Cloudflare Workers AI (ฟรี) + Gemini fallback
"""
import os
import json
import uuid
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from rag.vector_store import search, add_documents, get_stats, clear_all
from rag.knowledge_base import sync_from_bookstack, sync_single_page
from ai.llm import ask
from ai.tts import generate_speech, list_voices

load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8120"))
STREAM_KEY = os.getenv("STREAM_KEY", "changeme_live_key")

# --- Chat history store (per session) ---
chat_sessions: dict[str, list] = {}
active_connections: dict[str, list[WebSocket]] = {}


# ============================================================
# Lifecycle
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown."""
    # Ensure dirs
    Path("data/audio").mkdir(parents=True, exist_ok=True)
    print(f"[AI-Stream] Server starting on {HOST}:{PORT}")
    yield
    print("[AI-Stream] Server shutting down")


app = FastAPI(
    title="AI Live Stream Backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# RAG APIs
# ============================================================
@app.get("/api/health")
async def health():
    """Server health check."""
    stats = get_stats()
    return {
        "status": "ok",
        "rag": stats,
        "sessions": len(chat_sessions),
        "connections": sum(len(v) for v in active_connections.values()),
    }


@app.get("/api/rag/search")
async def api_search(q: str = Query(..., description="Search query"), k: int = Query(5, ge=1, le=20)):
    """Search RAG knowledge base."""
    results = await search(q, k=k)
    return {"query": q, "results": results, "count": len(results)}


@app.get("/api/rag/stats")
async def api_rag_stats():
    """RAG collection stats."""
    return get_stats()


@app.post("/api/rag/sync/bookstack")
async def api_sync_bookstack():
    """Sync all BookStack pages into RAG."""
    result = await sync_from_bookstack()
    return result


@app.post("/api/rag/sync/page/{page_id}")
async def api_sync_page(page_id: int):
    """Sync a single BookStack page."""
    result = await sync_single_page(page_id)
    return result


@app.post("/api/rag/clear")
async def api_rag_clear(key: str = Query(...)):
    """Clear RAG collection (requires stream key)."""
    if key != STREAM_KEY:
        raise HTTPException(403, "Invalid key")
    clear_all()
    return {"status": "cleared"}


# ============================================================
# Q&A API (non-stream)
# ============================================================
@app.post("/api/ask")
async def api_ask(body: dict):
    """
    Ask a question with RAG context.
    
    Body:
    {
        "question": "...",
        "session_id": "optional-session-id",
        "stream": false
    }
    """
    question = body.get("question", "")
    session_id = body.get("session_id", f"session_{uuid.uuid4().hex[:8]}")
    use_stream = body.get("stream", False)
    
    if not question:
        raise HTTPException(400, "question is required")
    
    # Get RAG context
    rag_results = await search(question)
    context = "\n\n".join([r["text"] for r in rag_results]) if rag_results else "ไม่พบข้อมูลที่เกี่ยวข้อง"
    
    # Chat history
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
    history = chat_sessions[session_id]
    
    # Get answer
    answer = await ask(context, question, history)
    
    # Store history
    history.append(question)
    history.append(answer)
    if len(history) > 50:
        history[:] = history[-50:]
    
    return {
        "answer": answer,
        "session_id": session_id,
        "rag_sources": rag_results[:3],  # top 3 sources
    }


@app.post("/api/ask/stream")
async def api_ask_stream(body: dict):
    """
    Streamed Q&A response.
    
    Body:
    {
        "question": "...",
        "session_id": "..."
    }
    """
    question = body.get("question", "")
    session_id = body.get("session_id", f"session_{uuid.uuid4().hex[:8]}")
    
    if not question:
        raise HTTPException(400, "question is required")
    
    rag_results = await search(question)
    context = "\n\n".join([r["text"] for r in rag_results]) if rag_results else "ไม่พบข้อมูลที่เกี่ยวข้อง"
    
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
    history = chat_sessions[session_id]
    
    async def generate():
        full_answer = ""
        async for chunk in await ask(context, question, history, stream=True):
            full_answer += chunk
            yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
        
        # Store
        history.append(question)
        history.append(full_answer)
        if len(history) > 50:
            history[:] = history[-50:]
        
        yield f"data: {json.dumps({'chunk': '', 'done': True, 'full_answer': full_answer, 'session_id': session_id})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ============================================================
# TTS API
# ============================================================
@app.post("/api/tts")
async def api_tts(body: dict):
    """Generate TTS audio from text."""
    text = body.get("text", "")
    voice = body.get("voice", None)
    
    if not text:
        raise HTTPException(400, "text is required")
    
    audio_path = await generate_speech(text, voice)
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(500, "TTS generation failed")
    
    return FileResponse(audio_path, media_type="audio/mpeg")


@app.get("/api/tts/voices")
async def api_tts_voices(lang: str = Query("th", description="Language code")):
    """List available TTS voices."""
    voices = await list_voices(lang)
    return {"voices": voices, "count": len(voices)}


@app.get("/api/tts/audio/{filename}")
async def api_tts_audio(filename: str):
    """Serve generated audio files."""
    filepath = Path(f"data/audio/{filename}")
    if not filepath.exists():
        raise HTTPException(404, "Audio not found")
    return FileResponse(str(filepath), media_type="audio/mpeg")


# ============================================================
# WebSocket — Live Stream Chat
# ============================================================
@app.websocket("/ws/live/{session_id}")
async def websocket_live(websocket: WebSocket, session_id: str):
    """WebSocket for live stream chat with RAG Q&A."""
    await websocket.accept()
    
    if session_id not in active_connections:
        active_connections[session_id] = []
    active_connections[session_id].append(websocket)
    print(f"[WS] {session_id} connected ({len(active_connections[session_id])} total)")
    
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
    
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg.get("type") == "question":
                question = msg.get("text", "")
                if not question:
                    continue
                
                # Broadcast "thinking" status
                await _broadcast(session_id, {
                    "type": "status",
                    "text": "กำลังคิด...",
                    "user": msg.get("user", "ผู้ชม"),
                }, exclude=websocket)
                
                # RAG search
                rag_results = await search(question)
                context = "\n\n".join([r["text"] for r in rag_results]) if rag_results else ""
                
                # Generate answer
                try:
                    full_answer = ""
                    async for chunk in await ask(context, question, chat_sessions[session_id], stream=True):
                        full_answer += chunk
                        await _broadcast(session_id, {
                            "type": "chunk",
                            "text": chunk,
                            "session_id": session_id,
                        })
                    
                    # Store history
                    chat_sessions[session_id].append(question)
                    chat_sessions[session_id].append(full_answer)
                    if len(chat_sessions[session_id]) > 50:
                        chat_sessions[session_id] = chat_sessions[session_id][-50:]
                    
                    # Broadcast done + optional TTS
                    await _broadcast(session_id, {
                        "type": "answer",
                        "text": full_answer,
                        "user": msg.get("user", "ผู้ชม"),
                        "session_id": session_id,
                    })
                    
                    # Auto TTS if requested
                    if msg.get("tts", False):
                        audio_path = await generate_speech(full_answer[:500])
                        if audio_path:
                            await _broadcast(session_id, {
                                "type": "audio",
                                "path": f"/api/tts/audio/{Path(audio_path).name}",
                            })
                    
                except Exception as e:
                    print(f"[WS] Error: {e}")
                    await _broadcast(session_id, {
                        "type": "error",
                        "text": "ขออภัย เกิดข้อผิดพลาด กรุณาลองใหม่",
                    })
            
            elif msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Disconnect: {e}")
    finally:
        if session_id in active_connections:
            active_connections[session_id].remove(websocket)
            if not active_connections[session_id]:
                del active_connections[session_id]
        print(f"[WS] {session_id} disconnected")


async def _broadcast(session_id: str, msg: dict, exclude: WebSocket = None):
    """Broadcast message to all WebSocket clients in session."""
    if session_id not in active_connections:
        return
    dead = []
    for ws in active_connections[session_id]:
        if ws == exclude:
            continue
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        try:
            active_connections[session_id].remove(ws)
        except ValueError:
            pass


# ============================================================
# OBS Overlay
# ============================================================
@app.get("/overlay", response_class=HTMLResponse)
async def overlay():
    """OBS Browser Source overlay that shows live Q&A."""
    html = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@400;600;700&display=swap');
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Noto Sans Thai', sans-serif;
    background: transparent;
    width: 1920px; height: 1080px;
    overflow: hidden;
    position: relative;
}
#container {
    position: absolute;
    bottom: 120px;
    left: 50%;
    transform: translateX(-50%);
    width: 80%;
    max-width: 1400px;
}
.qa-box {
    background: linear-gradient(135deg, rgba(0,0,0,0.85), rgba(20,20,30,0.85));
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 20px;
    padding: 24px 32px;
    margin-bottom: 16px;
    opacity: 0;
    transform: translateY(30px);
    transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}
.qa-box.show {
    opacity: 1;
    transform: translateY(0);
}
.qa-box .user {
    color: #60a5fa;
    font-weight: 600;
    font-size: 22px;
    margin-bottom: 8px;
}
.qa-box .user .name {
    color: #93c5fd;
}
.qa-box .question {
    color: #e2e8f0;
    font-size: 26px;
    font-weight: 400;
    margin-bottom: 12px;
    line-height: 1.4;
}
.qa-box .answer {
    color: #f1f5f9;
    font-size: 28px;
    font-weight: 600;
    line-height: 1.5;
}
.qa-box .answer .cursor {
    display: inline-block;
    width: 3px;
    height: 28px;
    background: #60a5fa;
    margin-left: 4px;
    animation: blink 0.8s infinite;
}
@keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}
.status-bar {
    position: absolute;
    bottom: 40px;
    left: 50%;
    transform: translateX(-50%);
    color: rgba(255,255,255,0.5);
    font-size: 18px;
}
</style>
</head>
<body>
    <div id="container"></div>
    <div class="status-bar" id="statusBar">พร้อมตอบคำถามแล้ว 🙋</div>

    <script>
    const container = document.getElementById('container');
    const statusBar = document.getElementById('statusBar');
    const sessionId = 'overlay_' + Date.now();
    let ws = null;
    let currentBox = null;
    let reconnectTimer = null;

    function connect() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${location.host}/ws/live/${sessionId}`);

        ws.onopen = () => {
            statusBar.textContent = '🟢 กำลังสตรีม — ถามได้เลย!';
            statusBar.style.color = 'rgba(255,255,255,0.7)';
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            if (data.type === 'chunk') {
                if (!currentBox) return;
                const answerEl = currentBox.querySelector('.answer');
                if (answerEl) {
                    answerEl.innerHTML = data.text.replace(/\\n/g, '<br>') + '<span class="cursor"></span>';
                }
            } else if (data.type === 'answer') {
                if (currentBox) {
                    const answerEl = currentBox.querySelector('.answer');
                    if (answerEl) {
                        answerEl.textContent = data.text;
                    }
                    setTimeout(() => {
                        currentBox.classList.remove('show');
                        setTimeout(() => {
                            if (currentBox && currentBox.parentNode) {
                                currentBox.remove();
                            }
                            currentBox = null;
                        }, 500);
                    }, 15000);
                }
                statusBar.textContent = '🙋 พร้อมสำหรับคำถามถัดไป';
                setTimeout(() => {
                    statusBar.textContent = 'พร้อมตอบคำถามแล้ว 🙋';
                }, 3000);
            } else if (data.type === 'status') {
                statusBar.textContent = '🤔 ' + data.text;
                showQuestion(data.user, data.text);
            } else if (data.type === 'error') {
                if (currentBox) {
                    const answerEl = currentBox.querySelector('.answer');
                    if (answerEl) {
                        answerEl.textContent = data.text;
                    }
                }
            }
        };

        ws.onclose = () => {
            statusBar.textContent = '⏳ กำลังเชื่อมต่อใหม่...';
            statusBar.style.color = 'rgba(255,165,0,0.7)';
            reconnectTimer = setTimeout(connect, 3000);
        };

        ws.onerror = () => {
            ws.close();
        };
    }

    function showQuestion(user, questionText) {
        if (currentBox) {
            currentBox.classList.remove('show');
            setTimeout(() => {
                if (currentBox && currentBox.parentNode) {
                    currentBox.remove();
                }
                currentBox = null;
                createNewBox(user, questionText);
            }, 300);
        } else {
            createNewBox(user, questionText);
        }
    }

    function createNewBox(user, questionText) {
        const box = document.createElement('div');
        box.className = 'qa-box';
        box.innerHTML = `
            <div class="user"><span class="name">${escapeHtml(user)}</span> ถาม</div>
            <div class="question">${escapeHtml(questionText)}</div>
            <div class="answer"><span class="cursor"></span></div>
        `;
        container.prepend(box);
        currentBox = box;
        requestAnimationFrame(() => {
            box.classList.add('show');
        });

        // Limit to 3 boxes
        while (container.children.length > 3) {
            container.removeChild(container.lastChild);
        }
    }

    function escapeHtml(text) {
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    connect();
    </script>
</body>
</html>"""
    return html


# ============================================================
# Admin / Stream Info
# ============================================================
@app.get("/api/sessions")
async def api_sessions():
    """List active chat sessions."""
    return {
        "chat_sessions": len(chat_sessions),
        "ws_connections": {k: len(v) for k, v in active_connections.items()},
    }


@app.get("/api/sessions/{session_id}/history")
async def api_session_history(session_id: str):
    """Get chat history for a session."""
    history = chat_sessions.get(session_id, [])
    return {"session_id": session_id, "messages": len(history), "history": history}


# ============================================================
# Entry
# ============================================================
if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info",
    )
