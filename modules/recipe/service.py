from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import json, os

app = FastAPI(title="Recipe Service")

# Simple in‑memory recipe store (in real code load from JSON files)
RECIPES = {
    "default": {"steps": ["script1", "script2"], "description": "Basic video recipe"},
    "thai": {"steps": ["thai_script1", "thai_script2"], "description": "Thai‑focused recipe"},
}

@app.get("/api/v1/recipe/{name}")
async def get_recipe(name: str):
    recipe = RECIPES.get(name)
    if not recipe:
        return JSONResponse({"error": "recipe not found"}, status_code=404)
    return JSONResponse(recipe)

@app.get("/api/v1/recipe/list")
async def list_recipes():
    return JSONResponse({"recipes": list(RECIPES.keys())})

@app.get("/health")
async def health():
    return JSONResponse({"status": "recipe service ok"})
