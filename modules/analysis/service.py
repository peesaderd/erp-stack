from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Analysis Service")

@app.post("/api/v1/analysis/run")
async def run_analysis(request):
    # Placeholder: just echo back the received payload
    data = await request.json()
    return JSONResponse({"status": "analysis completed", "input": data})

@app.get("/health")
async def health():
    return JSONResponse({"status": "analysis service ok"})
