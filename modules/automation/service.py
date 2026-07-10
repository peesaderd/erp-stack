# Automation Service (orchestrator placeholder)

import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Automation Service")

# URLs for downstream services (read from env, fallback to default names)
VIDEO_URL = os.getenv("VIDEO_SERVICE_URL", "http://video:8116")
TTS_URL = os.getenv("TTS_SERVICE_URL", "http://tts:8117")
UGC_URL = os.getenv("UGC_SERVICE_URL", "http://ugc:8118")
RECIPE_URL = os.getenv("RECIPE_SERVICE_URL", "http://recipe:8119")
ANALYSIS_URL = os.getenv("ANALYSIS_SERVICE_URL", "http://analysis:8120")
AUTOPROMPT_URL = os.getenv("AUTOPROMPT_SERVICE_URL", "http://auto_prompt:8121")
PRODUCT_LOOP_URL = os.getenv("PRODUCTLOOP_SERVICE_URL", "http://product_loop:8123")

async def _proxy_post(url: str, json_body: dict):
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=json_body)
        resp.raise_for_status()
        return resp.json()

@app.post("/api/v1/automation/run")
async def run_pipeline(request: Request):
    payload = await request.json()
    # Expected payload includes keys: recipe, user_id, content, use_wave2lip (bool)
    # 1. Get recipe
    recipe_name = payload.get("recipe", "default")
    recipe_resp = await _proxy_post(f"{RECIPE_URL}/api/v1/recipe/{recipe_name}", {})
    # 2. Store UGC (if any)
    if "ugc" in payload:
        await _proxy_post(f"{UGC_URL}/api/v1/ugc/upload", payload["ugc"])
    # 3. Generate video (placeholder)
    video_resp = await _proxy_post(f"{VIDEO_URL}/api/v1/video/generate", {"prompt": recipe_resp.get("description", "")})
    # 4. Generate TTS
    tts_resp = await _proxy_post(f"{TTS_URL}/api/v1/tts/generate", {"text": payload.get("text", "")})
    # 5. Run analysis
    analysis_resp = await _proxy_post(f"{ANALYSIS_URL}/api/v1/analysis/run", {"video_url": video_resp.get("video_url"), "audio_url": tts_resp.get("audio_url")})
    # 6. Auto prompt (optional)
    auto_prompt_resp = await _proxy_post(f"{AUTOPROMPT_URL}/api/v1/prompt/generate", {"recipe": recipe_name, "context": payload})
    # 7. Record usage in product loop
    await _proxy_post(f"{PRODUCT_LOOP_URL}/api/v1/usage/{payload.get('user_id','guest')}", {})
    # Return a summary
    return JSONResponse({
        "status": "pipeline completed",
        "video": video_resp,
        "tts": tts_resp,
        "analysis": analysis_resp,
        "prompt": auto_prompt_resp,
    })

@app.get("/health")
async def health():
    return JSONResponse({"status": "automation ok"})
