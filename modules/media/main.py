"""Media Module - File upload and management service on port 8103."""
import os, sys, uuid, shutil, json, logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

_module_dir = os.path.dirname(os.path.abspath(__file__))
_modules_dir = os.path.dirname(_module_dir)
if _modules_dir not in sys.path:
    sys.path.insert(0, _modules_dir)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("media_module")

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
THUMB_DIR = BASE_DIR / "thumbnails"
UPLOAD_DIR.mkdir(exist_ok=True)
THUMB_DIR.mkdir(exist_ok=True)

media_store: dict = {}
ALLOWED_TYPES = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
    "image/gif": ".gif", "video/mp4": ".mp4", "video/webm": ".webm",
    "application/pdf": ".pdf",
}
MAX_SIZE = 50 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Media module starting, uploads at {UPLOAD_DIR}")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post("http://localhost:8101/api/v1/register", json={
                "name": "media-module", "port": 8103,
                "description": "File upload and media management",
                "endpoints": [
                    {"path": "/api/v1/media/upload", "method": "POST"},
                    {"path": "/api/v1/media/list", "method": "GET"},
                    {"path": "/api/v1/media/{media_id}", "method": "GET"},
                    {"path": "/health", "method": "GET"},
                ]
            })
            logger.info("Registered with erp_bridge")
    except Exception as e:
        logger.warning(f"Bridge registration skipped: {e}")
    yield


app = FastAPI(title="Media Module", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "media-module"}


@app.post("/api/v1/media/upload")
async def upload_media(file: UploadFile = File(...)):
    if file.size and file.size > MAX_SIZE:
        raise HTTPException(413, "File too large (max 50MB)")

    ext = os.path.splitext(file.filename or "file")[1].lower()
    if not ext and file.content_type in ALLOWED_TYPES:
        ext = ALLOWED_TYPES[file.content_type]

    media_id = str(uuid.uuid4())
    safe_name = f"{media_id}{ext}" if ext else f"{media_id}"
    filepath = UPLOAD_DIR / safe_name

    try:
        content = await file.read()
        filepath.write_bytes(content)
    except Exception as e:
        raise HTTPException(500, f"Save failed: {e}")

    meta = {
        "id": media_id,
        "filename": file.filename or safe_name,
        "stored_as": safe_name,
        "size": len(content),
        "mime_type": file.content_type or "application/octet-stream",
        "url": f"/media/uploads/{safe_name}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    media_store[media_id] = meta
    return meta


@app.get("/api/v1/media/list")
async def list_media(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    items = list(media_store.values())
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {
        "total": len(items),
        "limit": limit,
        "offset": offset,
        "items": items[offset:offset + limit],
    }


@app.get("/api/v1/media/{media_id}")
async def get_media(media_id: str):
    meta = media_store.get(media_id)
    if not meta:
        raise HTTPException(404, "Media not found")
    return meta


# Serve uploaded files
app.mount("/media/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


def main():
    port = int(os.environ.get("MEDIA_PORT", 8103))
    uvicorn.run("media.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
