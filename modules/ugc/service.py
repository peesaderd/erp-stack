from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="UGC Service")

@app.post("/api/v1/ugc/upload")
async def upload_ugc(request: Request):
    # Placeholder: accept JSON and return ID
    data = await request.json()
    return JSONResponse({"status": "uploaded", "ugc_id": "ugc123", "data": data})

@app.get("/health")
async def health():
    return JSONResponse({"status": "ugc service ok"})
