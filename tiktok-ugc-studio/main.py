"""
TikTok UGC Studio — API Gateway
Reduced to ~800 lines. Proxies to module services for business logic.
"""

import os
import json
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

# ─── Storage paths ────────────────────────────────────────────────────────
STORAGE_DIR = Path(__file__).parent / "storage"
TTS_DIR = STORAGE_DIR / "tts"
IMAGES_DIR = STORAGE_DIR / "images"
VIDEOS_DIR = STORAGE_DIR / "videos"
for d in [STORAGE_DIR, TTS_DIR, IMAGES_DIR, VIDEOS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

TIKTOK_ACCOUNTS_FILE = STORAGE_DIR / "tiktok_accounts.json"

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx
import sqlite3

# ─── Module service URLs ──────────────────────────────────────────────────
MODULE_URLS = {
    "image-gen": "http://localhost:8110",
    "video": "http://localhost:8111",
    "prompt-builder": "http://localhost:8117",
    "payment": "http://localhost:8122",
    "profile": "http://localhost:8107",
    "auth": "http://localhost:8101",
    "product": "http://localhost:8106",
}

async def _proxy(method: str, module: str, path: str, body: dict = None, timeout: float = 90.0) -> dict:
    """Proxy request to a module service."""
    base = MODULE_URLS.get(module)
    if not base:
        raise HTTPException(status_code=400, detail=f"Unknown module: {module}")
    url = f"{base}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            if method == "GET":
                resp = await client.get(url, params=body)
            else:
                resp = await client.post(url, json=body or {})
            if resp.status_code >= 400:
                return {"ok": False, "status": resp.status_code, "error": resp.text[:300]}
            try:
                return {"ok": True, "status": resp.status_code, "data": resp.json()}
            except Exception:
                return {"ok": True, "status": resp.status_code, "data": {"text": resp.text}}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}

# ─── Load .env ────────────────────────────────────────────────────────────
_env_file = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                if _k not in os.environ:
                    os.environ[_k] = _v

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tiktok-ugc")

# ─── FastAPI app ──────────────────────────────────────────────────────────
app = FastAPI(title="TikTok UGC Studio", version="0.3.0", description="API Gateway for UGC video pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
(STORAGE_DIR / "tts").mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "composed").mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "videos").mkdir(parents=True, exist_ok=True)
try:
    app.mount("/static", StaticFiles(directory=str(STORAGE_DIR)), name="static")
except Exception as e:
    logger.warning(f"Static mount: {e}")

PRODUCT_IMAGE_DIR = STORAGE_DIR / "product_images"
PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
try:
    app.mount("/static/product_images", StaticFiles(directory=PRODUCT_IMAGE_DIR), name="product_images")
except Exception as e:
    logger.warning(f"Product images mount: {e}")

# ─── Pydantic Models ──────────────────────────────────────────────────────
class TikTokAccountConfig(BaseModel):
    account_id: str = ""
    username: str = ""
    session_token: Optional[str] = None
    use_qr: bool = False

class TikTokUploadRequest(BaseModel):
    account_id: str
    video_path: str
    caption: str = ""
    hashtags: list[str] = []

class TikTokSessionRequest(BaseModel):
    account_id: str

class PipelineRequest(BaseModel):
    product_url: str = ""
    product_title: str = ""
    ugc_style: str = "product_usage"
    hook: str = ""
    value: str = ""
    cta: str = ""
    duration: int = 8
    aspect_ratio: str = "9:16"
    preset: Optional[str] = None

# ─── TikTok accounts storage ──────────────────────────────────────────────
def _load_tiktok_accounts() -> dict:
    if TIKTOK_ACCOUNTS_FILE.exists():
        try:
            return json.loads(TIKTOK_ACCOUNTS_FILE.read_text())
        except Exception:
            return {}
    return {}

def _save_tiktok_accounts(accounts: dict):
    TIKTOK_ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2))

# ─── Pipeline DB (SQLite) ─────────────────────────────────────────────────
PIPELINE_DB = STORAGE_DIR / "pipeline.db"

def _init_pipeline_db():
    conn = sqlite3.connect(str(PIPELINE_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_jobs (
            job_id TEXT PRIMARY KEY,
            created_at TEXT,
            status TEXT DEFAULT 'pending',
            account_id TEXT,
            product_url TEXT,
            current_step TEXT,
            result_json TEXT
        )
    """)
    conn.commit()
    conn.close()

_init_pipeline_db()

def _create_pipeline_job(account_id: str = "", product_url: str = "") -> str:
    job_id = f"pipe_{int(time.time())}_{os.urandom(4).hex()}"
    conn = sqlite3.connect(str(PIPELINE_DB))
    conn.execute(
        "INSERT INTO pipeline_jobs (job_id, created_at, account_id, product_url, current_step) VALUES (?, ?, ?, ?, ?)",
        (job_id, datetime.utcnow().isoformat(), account_id, product_url, "init")
    )
    conn.commit()
    conn.close()
    return job_id

def _update_pipeline_step(job_id: str, step: str, status: str, result: dict = None):
    conn = sqlite3.connect(str(PIPELINE_DB))
    conn.execute(
        "UPDATE pipeline_jobs SET current_step=?, status=?, result_json=? WHERE job_id=?",
        (step, status, json.dumps(result or {}), job_id)
    )
    conn.commit()
    conn.close()

def _get_pipeline_job(job_id: str) -> dict:
    conn = sqlite3.connect(str(PIPELINE_DB))
    cur = conn.execute("SELECT * FROM pipeline_jobs WHERE job_id=?", (job_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    cols = [c[0] for c in cur.description]
    return dict(zip(cols, row))

# ─── Health ───────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "tiktok-ugc-studio", "version": "0.3.0"}

@app.get("/api/auth/{provider}/login")
async def auth_oauth_login(provider: str):
    """OAuth login redirect."""
    return await _proxy("GET", "auth", f"/api/v1/auth/{provider}/login")

@app.get("/api/auth/{provider}/callback")
async def auth_oauth_callback(provider: str, code: str = "", state: str = "", error: str = ""):
    """OAuth callback."""
    return await _proxy("GET", "auth", f"/api/v1/auth/{provider}/callback", {"code": code, "state": state, "error": error})

# ─── Auth catch-all ───────────────────────────────────────────────────────
@app.api_route("/api/v1/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def auth_proxy(request: Request, path: str):
    """Proxy all /api/v1/auth/* to auth module."""
    body = await request.json() if request.method in ("POST", "PUT", "PATCH") else None
    return await _proxy(request.method, "auth", f"/api/v1/auth/{path}", body)

# ─── Pipeline orchestration ───────────────────────────────────────────────
@app.post("/pipeline/run")
async def run_pipeline(req: PipelineRequest):
    """Orchestrate full pipeline via module services."""
    job_id = _create_pipeline_job(product_url=req.product_url)
    
    async def run():
        try:
            # Step 1: Generate script
            _update_pipeline_step(job_id, "script", "running")
            script_result = await _proxy("POST", "prompt-builder", "/api/v1/build", {
                "product_url": req.product_url,
                "product_title": req.product_title,
                "ugc_style": req.ugc_style,
                "hook": req.hook,
                "value": req.value,
                "cta": req.cta,
            })
            if not script_result.get("ok"):
                _update_pipeline_step(job_id, "script", "failed", script_result)
                return
            script = script_result["data"].get("script", "")
            _update_pipeline_step(job_id, "script", "done", {"script": script})
            
            # Step 2: TTS
            _update_pipeline_step(job_id, "tts", "running")
            tts_result = await _proxy("POST", "video", "/api/v1/tts/generate", {
                "script": script,
                "lang": "th",
            })
            if not tts_result.get("ok"):
                _update_pipeline_step(job_id, "tts", "failed", tts_result)
                return
            tts_url = tts_result["data"].get("audio_url", "")
            _update_pipeline_step(job_id, "tts", "done", {"audio_url": tts_url})
            
            # Step 3: Video generation
            _update_pipeline_step(job_id, "video", "running")
            video_result = await _proxy("POST", "video", "/api/v1/generate", {
                "script": script,
                "duration": req.duration,
                "aspect_ratio": req.aspect_ratio,
                "audio_url": tts_url,
            })
            if not video_result.get("ok"):
                _update_pipeline_step(job_id, "video", "failed", video_result)
                return
            video_url = video_result["data"].get("video_url", "")
            _update_pipeline_step(job_id, "video", "done", {"video_url": video_url})
            
            # Done
            _update_pipeline_step(job_id, "complete", "done", {"video_url": video_url})
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            _update_pipeline_step(job_id, "error", "failed", {"error": str(e)})
    
    asyncio.create_task(run())
    return {"success": True, "job_id": job_id}

@app.get("/pipeline/{job_id}/status")
def pipeline_status(job_id: str):
    job = _get_pipeline_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/pipeline/list")
def pipeline_list(limit: int = 20):
    conn = sqlite3.connect(str(PIPELINE_DB))
    cur = conn.execute("SELECT * FROM pipeline_jobs ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    cols = [c[0] for c in cur.description]
    conn.close()
    return {"jobs": [dict(zip(cols, r)) for r in rows]}

# ─── TikTok account management ────────────────────────────────────────────
@app.get("/tiktok/accounts")
def tiktok_list_accounts():
    accounts = _load_tiktok_accounts()
    session_dir = Path(__file__).parent / "sessions" / "tiktok"
    account_list = []
    for aid, cfg in accounts.items():
        session_file = session_dir / f"{aid}.json"
        has_token = bool(cfg.get("session_token", ""))
        account_list.append({
            "id": aid,
            "username": cfg.get("username", aid),
            "use_qr": cfg.get("use_qr", False),
            "session_token": has_token,
            "is_logged_in": session_file.exists() or has_token,
        })
    return {"accounts": account_list, "total": len(account_list)}

@app.post("/tiktok/accounts")
async def tiktok_add_account(req: TikTokAccountConfig):
    accounts = _load_tiktok_accounts()
    account_id = req.account_id or req.username
    if not account_id:
        return {"success": False, "error": "Username required"}
    
    acct_data = req.model_dump(exclude_none=True, exclude={"session_token"})
    account_id = account_id.lstrip("@")
    acct_data["account_id"] = account_id
    acct_data["is_logged_in"] = bool(req.session_token)
    if req.session_token:
        acct_data["session_token"] = req.session_token
    accounts[account_id] = acct_data
    _save_tiktok_accounts(accounts)
    return {"success": True, "account_id": account_id}

@app.delete("/tiktok/accounts/{account_id}")
async def tiktok_remove_account(account_id: str):
    accounts = _load_tiktok_accounts()
    accounts.pop(account_id, None)
    _save_tiktok_accounts(accounts)
    
    session_file = Path(__file__).parent / "sessions" / "tiktok" / f"{account_id}.json"
    if session_file.exists():
        session_file.unlink()
    qr_file = Path(__file__).parent / "sessions" / "tiktok" / f"{account_id}_qr.png"
    if qr_file.exists():
        qr_file.unlink()
    
    return {"success": True}

# ─── TikTok QR login ──────────────────────────────────────────────────────
_qr_login_tokens = {}

@app.post("/tiktok/qr-login")
async def tiktok_qr_login(req: TikTokAccountConfig):
    """Start TikTok QR login flow using Playwright."""
    try:
        from playwright.async_api import async_playwright
        
        account_id = req.account_id or req.username
        if not account_id:
            return {"success": False, "error": "Username required"}
        account_id = account_id.lstrip("@")
        
        session_dir = Path(__file__).parent / "sessions" / "tiktok"
        session_dir.mkdir(parents=True, exist_ok=True)
        
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--window-size=1280,720"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
        )
        page = await context.new_page()
        
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        
        logger.info("Navigating to TikTok login...")
        await page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        
        qr_btn = page.locator('text="Use QR code"').first
        await qr_btn.wait_for(timeout=10000)
        await qr_btn.click()
        await page.wait_for_timeout(3000)
        
        await page.wait_for_selector('canvas, img[src*="qr"], [class*="qr"]', timeout=15000)
        await page.wait_for_timeout(1000)
        
        qr_path = str(session_dir / f"{account_id}_qr.png")
        await page.screenshot(path=qr_path, full_page=False)
        logger.info(f"QR code captured: {qr_path}")
        
        import base64
        with open(qr_path, "rb") as f:
            qr_b64 = base64.b64encode(f.read()).decode()
        
        token_id = f"qr_{int(time.time())}_{os.urandom(4).hex()}"
        _qr_login_tokens[token_id] = {
            "account_id": account_id,
            "status": "pending",
            "created_at": time.time(),
        }
        
        asyncio.create_task(_poll_tiktok_qr_login(token_id, account_id, p, context, browser, page))
        
        return {
            "success": True,
            "qr_code": f"data:image/png;base64,{qr_b64}",
            "account_id": account_id,
            "token_id": token_id,
            "method": "qr",
        }
    except Exception as e:
        logger.error(f"QR login error: {e}")
        return {"success": False, "error": f"QR login failed: {str(e)[:300]}"}

async def _poll_tiktok_qr_login(token_id: str, account_id: str, playwright_inst, context, browser, page):
    """Poll TikTok QR login until scan completes."""
    try:
        logger.info(f"QR poll started for {account_id}")
        start = time.time()
        timeout_seconds = 180
        logged_in = False
        
        while time.time() - start < timeout_seconds:
            await asyncio.sleep(3)
            try:
                current_url = page.url
                if "login" not in current_url.lower():
                    logged_in = True
                    break
                
                scan_ok = await page.evaluate("""
                    () => {
                        const text = document.body?.innerText || '';
                        return text.includes('Confirm') || text.includes('success');
                    }
                """)
                if scan_ok:
                    logged_in = True
                    break
            except Exception:
                pass
        
        if logged_in:
            logger.info(f"QR login success for {account_id}")
            cookies = await context.cookies()
            session_data = {"cookies": cookies, "logged_in_at": datetime.utcnow().isoformat()}
            session_file = Path(__file__).parent / "sessions" / "tiktok" / f"{account_id}.json"
            session_file.write_text(json.dumps(session_data, indent=2))
            
            accounts = _load_tiktok_accounts()
            if account_id not in accounts:
                accounts[account_id] = {"account_id": account_id, "username": account_id}
            accounts[account_id]["is_logged_in"] = True
            _save_tiktok_accounts(accounts)
            
            _qr_login_tokens[token_id] = {
                "account_id": account_id,
                "status": "completed",
                "session_file": str(session_file),
            }
        else:
            _qr_login_tokens[token_id] = {"account_id": account_id, "status": "expired"}
    except Exception as e:
        logger.error(f"QR poll error: {e}")
        _qr_login_tokens[token_id] = {"account_id": account_id, "status": "failed", "error": str(e)}
    finally:
        try:
            await browser.close()
            await playwright_inst.stop()
        except Exception:
            pass

@app.get("/tiktok/qr-status/{token_id}")
def tiktok_qr_status(token_id: str):
    entry = _qr_login_tokens.get(token_id)
    if not entry:
        return {"status": "not_found"}
    
    result = {"status": entry.get("status", "pending")}
    if entry.get("account_id"):
        result["account_id"] = entry["account_id"]
    
    if entry.get("status") in ("completed", "expired", "failed"):
        if time.time() - entry.get("created_at", 0) > 3600:
            _qr_login_tokens.pop(token_id, None)
    
    return result

# ─── TikTok upload ────────────────────────────────────────────────────────
@app.post("/tiktok/upload")
async def tiktok_upload_video(req: TikTokUploadRequest):
    """Upload video to TikTok using session token."""
    try:
        accounts = _load_tiktok_accounts()
        acct = accounts.get(req.account_id.lstrip("@"))
        if not acct:
            return {"success": False, "error": "Account not found"}
        
        token = acct.get("session_token", "")
        if not token:
            return {"success": False, "error": "No session token"}
        
        video_path = Path(req.video_path)
        if not video_path.exists():
            return {"success": False, "error": f"Video not found: {req.video_path}"}
        
        from simple_tiktok_uploader import upload
        os.environ["TIKTOK_SESSION"] = token
        
        caption = req.caption
        if req.hashtags:
            caption += " " + " ".join(f"#{h}" for h in req.hashtags)
        
        result = upload(str(video_path), caption)
        return {
            "success": True,
            "video_id": getattr(result, "id", "") or getattr(result, "video_id", ""),
            "url": getattr(result, "url", "") or getattr(result, "share_url", ""),
            "account_id": req.account_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}

@app.post("/tiktok/check-session")
async def tiktok_check_session(req: TikTokSessionRequest):
    """Check if TikTok session is valid."""
    try:
        from tiktok_browser import check_session
        result = await check_session(req.account_id)
        
        accounts = _load_tiktok_accounts()
        if req.account_id in accounts:
            accounts[req.account_id]["is_logged_in"] = result.get("valid", False)
            _save_tiktok_accounts(accounts)
        
        return result
    except Exception as e:
        return {"valid": False, "error": str(e)[:200]}

@app.get("/tiktok/published")
def tiktok_published(limit: int = 20):
    """List published TikTok videos (from local storage)."""
    published_file = STORAGE_DIR / "tiktok_published.json"
    if not published_file.exists():
        return {"videos": []}
    try:
        data = json.loads(published_file.read_text())
        return {"videos": data[:limit]}
    except Exception:
        return {"videos": []}

@app.post("/tiktok/batch-upload")
async def tiktok_batch_upload(account_ids: list[str], video_path: str, caption: str = ""):
    """Upload video to multiple TikTok accounts."""
    results = []
    for account_id in account_ids:
        req = TikTokUploadRequest(account_id=account_id, video_path=video_path, caption=caption)
        result = await tiktok_upload_video(req)
        results.append({"account_id": account_id, **result})
    return {"results": results}

# ─── Affiliate config ─────────────────────────────────────────────────────
@app.get("/affiliate/config")
def get_affiliate_config():
    """Get affiliate platform URLs."""
    config_file = STORAGE_DIR / "affiliate_config.json"
    if not config_file.exists():
        return {"platforms": {}}
    try:
        return json.loads(config_file.read_text())
    except Exception:
        return {"platforms": {}}

# ─── UGC Creator Management ─────────────────────────────────────────────
@app.get("/ugc/accounts")
async def ugc_accounts():
    return await _proxy("GET", "product", "/api/v1/ugc/accounts")

@app.post("/ugc/post")
async def ugc_post(req: dict):
    return await _proxy("POST", "product", "/api/v1/ugc/post", req)

@app.post("/ugc/schedule")
async def ugc_schedule(req: dict):
    return await _proxy("POST", "product", "/api/v1/ugc/schedule", req)

@app.post("/ugc/webhook/pfm")
async def ugc_webhook_pfm(req: dict):
    return await _proxy("POST", "product", "/api/v1/ugc/webhook/pfm", req)

@app.post("/ugc/media/upload-url")
async def ugc_media_upload_url(req: dict):
    return await _proxy("POST", "product", "/api/v1/ugc/media/upload-url", req)

# ─── Products ─────────────────────────────────────────────────────────────
@app.get("/products/sheets/status")
async def products_sheets_status():
    return await _proxy("GET", "product", "/api/v1/products/sheets/status")

@app.post("/products/sheets/connect")
async def products_sheets_connect(req: dict):
    return await _proxy("POST", "product", "/api/v1/products/sheets/connect", req)

@app.post("/products/sheets/import")
async def products_sheets_import(req: dict):
    return await _proxy("POST", "product", "/api/v1/products/sheets/import", req)

@app.get("/products/list")
async def products_list(limit: int = 50):
    return await _proxy("GET", "product", "/api/v1/products/list", {"limit": limit})

# ─── Posts ────────────────────────────────────────────────────────────────
@app.get("/posts/scheduled")
async def posts_scheduled():
    return await _proxy("GET", "product", "/api/v1/posts/scheduled")

@app.delete("/posts/scheduled/{post_id}")
async def posts_scheduled_delete(post_id: str):
    return await _proxy("DELETE", "product", f"/api/v1/posts/scheduled/{post_id}")

# ─── Drive ────────────────────────────────────────────────────────────────
@app.get("/drive/connect")
async def drive_connect():
    return await _proxy("GET", "product", "/api/v1/drive/connect")

@app.post("/drive/config")
async def drive_config(req: dict):
    return await _proxy("POST", "product", "/api/v1/drive/config", req)

# ─── Payment ──────────────────────────────────────────────────────────────
@app.post("/payment/create-checkout")
async def payment_create_checkout(req: dict):
    return await _proxy("POST", "payment", "/api/v1/payment/create-checkout", req)

@app.post("/payment/create-qr")
async def payment_create_qr(req: dict):
    return await _proxy("POST", "payment", "/api/v1/payment/create-qr", req)

@app.get("/payment/plans")
async def payment_plans():
    return await _proxy("GET", "payment", "/api/v1/payment/plans")

@app.get("/payment/health")
async def payment_health():
    return await _proxy("GET", "payment", "/api/v1/payment/health")

# ─── Profile ──────────────────────────────────────────────────────────────
@app.get("/profile/health")
async def profile_health():
    return await _proxy("GET", "profile", "/api/v1/profile/health")

@app.post("/profile/register")
async def profile_register(req: dict):
    return await _proxy("POST", "profile", "/api/v1/profile/register", req)

@app.get("/profile/tier/{user_id}")
async def profile_tier(user_id: str):
    return await _proxy("GET", "profile", f"/api/v1/profile/tier/{user_id}")

# ─── Gallery ──────────────────────────────────────────────────────────────
@app.get("/images/gallery")
def images_gallery(limit: int = 50):
    """List generated images."""
    files = sorted(IMAGES_DIR.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    return {"images": [{"filename": f.name, "url": f"/static/images/{f.name}"} for f in files]}

@app.get("/videos/gallery")
def videos_gallery(limit: int = 50):
    """List generated videos."""
    files = sorted(VIDEOS_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    return {"videos": [{"filename": f.name, "url": f"/static/videos/{f.name}"} for f in files]}

# ─── Stats ────────────────────────────────────────────────────────────────
@app.get("/stats")
def stats():
    """Get basic stats."""
    accounts = _load_tiktok_accounts()
    conn = sqlite3.connect(str(PIPELINE_DB))
    cur = conn.execute("SELECT COUNT(*) FROM pipeline_jobs")
    pipeline_count = cur.fetchone()[0]
    conn.close()
    
    return {
        "tiktok_accounts": len(accounts),
        "pipeline_jobs": pipeline_count,
        "images_count": len(list(IMAGES_DIR.glob("*.png"))),
        "videos_count": len(list(VIDEOS_DIR.glob("*.mp4"))),
    }

# ─── Startup ──────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    logger.info("TikTok UGC Studio API Gateway started")
    logger.info(f"Module URLs: {MODULE_URLS}")
