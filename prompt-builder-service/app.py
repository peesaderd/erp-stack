#!/usr/bin/env python3
import sys
import os
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

sys.path.insert(0, os.path.dirname(__file__))
from prompt_builder import analyze_and_build_prompts
from pipeline import PipelineError
from steps import ALL_STEPS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prompt-builder-service")

app = FastAPI(title="Prompt Builder Service", version="1.0.0")

# ─── Build input model ───────────────────────────────────────────
class BuildRequest(BaseModel):
    product_name: str
    description: str = ""
    keywords: Optional[List[str]] = None
    ugc_style: str = "holding"
    product_id: str = ""
    price: float = 0.0
    product_image: str = ""
    category: str = ""
    product_category: str = ""


# ─── Health ──────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "prompt-builder-service"}


# ─── Main build endpoint (unchanged API) ─────────────────────────
@app.post("/api/v1/build")
async def build(req: BuildRequest):
    try:
        result = await analyze_and_build_prompts(
            product_name=req.product_name,
            description=req.description,
            keywords=req.keywords,
            ugc_style=req.ugc_style,
            product_id=req.product_id,
            price=req.price,
            product_image=req.product_image,
            category=req.category,
            product_category=req.product_category,
        )
        return result
    except PipelineError as pe:
        logger.error(f"Pipeline error: {pe}")
        return JSONResponse(
            status_code=500,
            content=pe.to_dict(),
        )
    except Exception as e:
        logger.exception("build failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Pipeline introspection — for agents ─────────────────────────
from pipeline import Pipeline
_pipeline = Pipeline("prompt-builder", ALL_STEPS)


@app.get("/api/v1/pipeline/steps")
async def pipeline_steps():
    """Return full pipeline structure — agents introspect this."""
    return _pipeline.describe()


@app.get("/api/v1/pipeline/step/{name}")
async def pipeline_step(name: str):
    """Return details for one step."""
    for s in ALL_STEPS:
        if s.name == name:
            return s.describe()
    raise HTTPException(status_code=404, detail=f"Step '{name}' not found")


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8117, reload=False)
