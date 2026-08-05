#!/usr/bin/env python3
import sys
import os
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

sys.path.insert(0, os.path.dirname(__file__))
from prompt_builder import analyze_and_build_prompts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prompt-builder-service")

app = FastAPI(title="Prompt Builder Service", version="1.0.0")


class BuildRequest(BaseModel):
    product_name: str
    description: str = ""
    features: str = ""
    keywords: Optional[List[str]] = None
    ugc_style: str = "holding"
    product_id: str = ""
    price: float = 0.0
    product_image: str = ""
    category: str = ""
    product_category: str = ""
    duration: int = 15
    target_duration: int = 15
    target_age: str = ""
    target_gender: str = ""
    country: str = ""


@app.get("/health")
async def health():
    return {"status": "ok", "service": "prompt-builder-service"}


@app.post("/api/v1/build")
async def build(req: BuildRequest):
    try:
        result = await analyze_and_build_prompts(
            product_name=req.product_name,
            description=req.description,
            features=req.features or "",
            keywords=req.keywords,
            ugc_style=req.ugc_style,
            product_id=req.product_id,
            price=req.price,
            product_image=req.product_image,
            category=req.category,
            product_category=req.product_category,
            target_duration=req.duration or req.target_duration or 15,
            target_age=req.target_age,
            target_gender=req.target_gender,
            country=req.country,
        )
        return result
    except Exception as e:
        logger.exception("build failed")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8117, reload=False)
