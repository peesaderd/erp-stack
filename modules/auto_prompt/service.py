# Auto Prompt Service (LLM wrapper)

import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse



app = FastAPI(title="Auto Prompt Service")

@app.post("/api/v1/prompt/generate")
async def generate_prompt(request: Request):
    payload = await request.json()
    # Expect payload: {"recipe": "...", "context": {...}}
    # Placeholder implementation – echo back combined text
    recipe = payload.get("recipe", "")
    context = payload.get("context", {})
    prompt = f"Recipe: {recipe}\nContext: {context}"

    return JSONResponse({"prompt": prompt, "status": "generated"})

@app.get("/health")
async def health():
    return JSONResponse({"status": "auto_prompt ok"})
