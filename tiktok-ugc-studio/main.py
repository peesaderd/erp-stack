# tiktok-ugc-studio/gateway (FastAPI)

import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="TikTok UGC Studio Gateway")

# Mapping of logical service name to base URL (host:port)
_MODULES = {
    "video": os.getenv("VIDEO_SERVICE_URL", "http://video:8116"),
    "tts": os.getenv("TTS_SERVICE_URL", "http://tts:8117"),
    "ugc": os.getenv("UGC_SERVICE_URL", "http://ugc:8118"),
    "recipe": os.getenv("RECIPE_SERVICE_URL", "http://recipe:8119"),
    "analysis": os.getenv("ANALYSIS_SERVICE_URL", "http://analysis:8120"),
    "auto_prompt": os.getenv("AUTOPROMPT_SERVICE_URL", "http://auto_prompt:8121"),
    "automation": os.getenv("AUTOMATION_SERVICE_URL", "http://automation:8122"),
    "product_loop": os.getenv("PRODUCTLOOP_SERVICE_URL", "http://product_loop:8123"),
    "image": os.getenv("IMAGE_SERVICE_URL", "http://image:8124"),
}

async def proxy(request: Request, target_url: str):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(
                request.method,
                target_url,
                headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
                params=request.query_params,
                content=await request.body(),
                timeout=60.0,
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
    return StreamingResponse(
        resp.aiter_raw(),
        status_code=resp.status_code,
        headers=resp.headers,
        media_type=resp.headers.get("content-type"),
    )

# Generic proxy endpoint – path after /proxy/{service}
@app.api_route("/proxy/{service}/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"]) 
async def generic_proxy(service: str, full_path: str, request: Request):
    base = _MODULES.get(service)
    if not base:
        raise HTTPException(status_code=404, detail="Service not found")
    target = f"{base}/{full_path}"
    return await proxy(request, target)

# Example: old monolith endpoint /pipeline/run now proxies to video service
@app.post("/pipeline/run")
async def pipeline_run(request: Request):
    return await proxy(request, f"{_MODULES['video']}/api/v1/video/generate")

# Status endpoint example
@app.get("/pipeline/{job_id}/status")
async def pipeline_status(job_id: str, request: Request):
    return await proxy(request, f"{_MODULES['video']}/api/v1/video/status/{job_id}")

# Health check
@app.get("/health")
async def health():
    return JSONResponse({"status": "gateway ok"})
