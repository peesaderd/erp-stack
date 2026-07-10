from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os

app = FastAPI(title="TTS Service")

@app.post("/api/v1/tts/generate")
async def generate_tts(request: Request):
    # Placeholder: just echo back dummy audio URL
    return JSONResponse({"status": "tts generated", "audio_url": "http://example.com/audio.mp3"})

@app.get("/health")
async def health():
    return JSONResponse({"status": "tts service ok"})
