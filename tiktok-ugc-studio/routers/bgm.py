"""BGM playlist routes — split from main.py monolith (Phase A2).

Static mount for /bgm stays in main.py (app-level); these are the API routes.
"""
import shutil
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["bgm"])

BGM_DIR = Path(__file__).resolve().parent.parent / "bgm"
BGM_DIR.mkdir(parents=True, exist_ok=True)


class SetBGMRequest(BaseModel):
    file: str


@router.post("/api/set-bgm")
async def set_bgm(req: SetBGMRequest):
    """Set the selected BGM file as the main bg_upbeat.mp3."""
    src = BGM_DIR / req.file
    if not src.exists():
        return {"ok": False, "error": f"File not found: {req.file}"}
    # Backup current bg_upbeat.mp3
    dest = BGM_DIR / "bg_upbeat.mp3"
    if dest.exists():
        backup = BGM_DIR / "bg_upbeat_backup.mp3"
        shutil.copy2(dest, backup)
    shutil.copy2(src, dest)
    return {"ok": True, "file": req.file, "message": f"BGM set to {req.file}"}


@router.get("/api/bgm-list")
async def bgm_list():
    """List all BGM files with metadata."""
    files = []
    for f in sorted(BGM_DIR.glob("*.mp3")):
        files.append({
            "name": f.stem,
            "file": f.name,
            "size": f.stat().st_size,
        })
    return {"ok": True, "files": files}
