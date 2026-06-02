"""Prompt Studio — Micro Service (port 8107)"""
import os, logging, re
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prompt_loader import get_loader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prompt-studio")
app = FastAPI(title="Prompt Studio", version="0.1.0", description="Centralized Prompt Repository with File/URL abstraction")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
loader = get_loader()

class FillRequest(BaseModel):
    template_content: str; data: dict

@app.get("/health")
def health():
    return {"status":"ok","service":"prompt-studio","mode":loader.mode,"base":loader.base_path or loader.base_url}

@app.get("/prompts/{module}/{name:path}")
def get_prompt(module: str, name: str):
    content = loader.load(module, name)
    if content is None: raise HTTPException(404, f"Not found: {module}/{name}")
    return {"module":module,"name":name,"content":content,"size":len(content),"mode":loader.mode}

@app.get("/prompts/{module}")
def list_module(module: str):
    files = loader.list_module(module)
    return {"module":module,"files":files,"total":len(files),"mode":loader.mode}

@app.get("/modules")
def list_modules():
    base = Path(loader.base_path)
    modules = []
    for d in sorted(base.iterdir()):
        if d.is_dir():
            subs = [s.name for s in sorted(d.iterdir()) if s.is_dir()]
            modules.append({"name":d.name,"submodules":subs,"file_count":sum(1 for _ in d.rglob("*") if _.is_file() and _.suffix in (".txt",".json",".prompt"))})
    return {"modules":modules,"total":len(modules),"mode":loader.mode}

@app.post("/prompts/fill")
def fill_template(req: FillRequest):
    return {"filled": loader.fill_template(req.template_content, req.data)}

@app.get("/config")
def config():
    return {"mode":loader.mode,"base_path":loader.base_path,"base_url":loader.base_url,"cache_size":len(loader._cache)}

@app.post("/admin/clear-cache")
def clear_cache():
    loader.clear_cache(); return {"status":"cache_cleared"}

@app.get("/stats")
def stats():
    return {"service":"prompt-studio","mode":loader.mode}
