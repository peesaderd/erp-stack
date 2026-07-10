# Wave2Lip Service (wrapper)

import os
import subprocess
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Wave2Lip Service")

# Path to the compiled Wave2Lip binary (assumed to be placed in /app/wave2lip)
WAVE2LIP_BIN = os.getenv("WAVE2LIP_BIN", "/app/wave2lip/Wave2Lip")

@app.post("/sync")
async def sync_lip(video: UploadFile = File(...), audio: UploadFile = File(...)):
    # Save incoming files to temporary location
    video_path = f"/tmp/{video.filename}"
    audio_path = f"/tmp/{audio.filename}"
    out_path = f"/tmp/synced_{video.filename}"
    with open(video_path, "wb") as f:
        f.write(await video.read())
    with open(audio_path, "wb") as f:
        f.write(await audio.read())

    if not os.path.isfile(WAVE2LIP_BIN):
        raise HTTPException(status_code=500, detail="Wave2Lip binary not found")

    cmd = [WAVE2LIP_BIN, "-i", video_path, "-a", audio_path, "-o", out_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Wave2Lip failed: {e.stderr}")

    # In a real implementation you would stream the file back; here we just return path
    return JSONResponse({"status": "synced", "output_path": out_path})

@app.get("/health")
async def health():
    return JSONResponse({"status": "wave2lip service ok"})
