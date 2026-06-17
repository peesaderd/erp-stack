"""Drive & Sheets Media Logger — Micro-Service
FastAPI server on port 8132.

Uploads generated media (video MP4, keyframe images, TTS audio)
to Google Drive, and logs metadata to a Google Sheet.

PM2: process name 'drive-service', port 8132
"""

import os
import sys
import json
import time
import mimetypes
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("drive_service")

# ─── Paths ────────────────────────────────────────────────────────────────
MODULE_DIR = Path(__file__).parent
CREDENTIALS_PATH = MODULE_DIR.parent / "product" / "sheets_credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]

app = FastAPI(title="Drive & Sheets Media Logger", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── Models ────────────────────────────────────────────────────────────────
class UploadRequest(BaseModel):
    file_path: str
    folder_name: str = "TikTok UGC Media"
    file_name: Optional[str] = None
    mime_type: Optional[str] = None


class LogMediaRequest(BaseModel):
    spreadsheet_id: str
    sheet_name: str = "Media Log"
    filename: str
    file_type: str  # "video", "image", "audio"
    drive_url: str
    drive_file_id: str
    task_id: str = ""
    job_id: str = ""
    product_name: str = ""
    file_size_bytes: int = 0
    status: str = "completed"
    notes: str = ""


class LogMediaResponse(BaseModel):
    success: bool
    error: str = ""


# ─── Auth Helper ─────────────────────────────────────────────────────────
def _get_credentials():
    """Get Google API credentials from service account file."""
    creds_path = str(CREDENTIALS_PATH)
    if not os.path.exists(creds_path):
        raise FileNotFoundError(
            f"Credentials not found at {creds_path}. "
            "Place sheets_credentials.json in modules/product/ directory."
        )
    from google.oauth2.service_account import Credentials
    return Credentials.from_service_account_file(creds_path, scopes=SCOPES)


def is_ready() -> bool:
    """Check if credentials file exists."""
    return CREDENTIALS_PATH.exists()


def instructions() -> str:
    """Return setup instructions."""
    return (
        "1. Go to https://console.cloud.google.com/apis/credentials\n"
        "2. Create Service Account → Download JSON key\n"
        "3. Save as: " + str(CREDENTIALS_PATH) + "\n"
        "4. Enable Google Drive API + Google Sheets API in GCP\n"
        "5. Create a Google Drive folder for media, share with service account email\n"
        "6. Create a Google Sheet for media tracking, share with service account email\n"
        "7. pip install google-api-python-client google-auth gspread"
    )


# ─── Drive: Upload File ──────────────────────────────────────────────────
@app.post("/drive/upload")
async def drive_upload(req: UploadRequest):
    """Upload a local file to Google Drive in the specified folder."""
    if not is_ready():
        return {"success": False, "error": "Credentials not configured", "instructions": instructions()}

    file_path = Path(req.file_path)
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {req.file_path}"}

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = _get_credentials()
        service = build("drive", "v3", credentials=creds)

        # Find or create folder
        folder_id = _find_or_create_folder(service, req.folder_name)

        # Determine file name
        fname = req.file_name or file_path.name
        mime_type = req.mime_type or mimetypes.guess_type(fname)[0] or "application/octet-stream"

        # Upload
        media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)
        file_metadata = {
            "name": fname,
            "parents": [folder_id],
            "description": f"Uploaded from TUS at {datetime.now().isoformat()}",
        }

        uploaded = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, mimeType, size, webViewLink, webContentLink"
        ).execute()

        # Make publicly viewable
        try:
            permission = {
                "type": "anyone",
                "role": "reader",
            }
            service.permissions().create(fileId=uploaded["id"], body=permission).execute()
        except Exception:
            pass  # Not critical

        drive_url = uploaded.get("webViewLink", "")
        if not drive_url:
            # Build URL manually
            drive_url = f"https://drive.google.com/file/d/{uploaded['id']}/view"

        logger.info(f"Uploaded {fname} to Drive folder '{req.folder_name}' (id: {uploaded['id']})")

        return {
            "success": True,
            "drive_file_id": uploaded["id"],
            "file_name": uploaded["name"],
            "mime_type": uploaded.get("mimeType", mime_type),
            "size_bytes": uploaded.get("size", file_path.stat().st_size),
            "drive_url": drive_url,
            "folder": req.folder_name,
        }

    except ImportError as e:
        return {"success": False, "error": f"Missing package: {e}. Run: pip install google-api-python-client google-auth"}
    except Exception as e:
        logger.error(f"Drive upload failed: {e}")
        return {"success": False, "error": str(e)[:500]}


def _find_or_create_folder(service, folder_name: str) -> str:
    """Find a Drive folder by name, or create it."""
    try:
        results = service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name)",
            pageSize=10,
        ).execute()
        files = results.get("files", [])
        if files:
            return files[0]["id"]

        # Create folder
        folder_meta = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = service.files().create(body=folder_meta, fields="id").execute()
        logger.info(f"Created Drive folder '{folder_name}' (id: {folder['id']})")
        return folder["id"]

    except Exception as e:
        raise RuntimeError(f"Failed to find/create folder '{folder_name}': {e}")


# ─── Drive: List Files ───────────────────────────────────────────────────
@app.get("/drive/files")
async def drive_list(folder_name: str = "TikTok UGC Media", limit: int = 50):
    """List files in the specified Drive folder."""
    if not is_ready():
        return {"success": False, "error": "Credentials not configured"}

    try:
        from googleapiclient.discovery import build

        creds = _get_credentials()
        service = build("drive", "v3", credentials=creds)

        folder_id = _find_or_create_folder(service, folder_name)

        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, mimeType, size, createdTime, webViewLink)",
            pageSize=min(limit, 100),
            orderBy="createdTime desc",
        ).execute()

        files = []
        for f in results.get("files", []):
            files.append({
                "id": f["id"],
                "name": f["name"],
                "mime_type": f.get("mimeType", ""),
                "size_bytes": f.get("size", 0),
                "created_time": f.get("createdTime", ""),
                "url": f.get("webViewLink", f"https://drive.google.com/file/d/{f['id']}/view"),
            })

        return {"success": True, "folder": folder_name, "files": files, "count": len(files)}

    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


# ─── Sheets: Log Media ───────────────────────────────────────────────────
@app.post("/sheets/log-media")
async def sheets_log_media(req: LogMediaRequest):
    """Log a media file record to a Google Sheet."""
    if not is_ready():
        return {"success": False, "error": "Credentials not configured"}

    try:
        import gspread
        from google.oauth2.service_account import Credentials as GCreds

        creds = GCreds.from_service_account_file(str(CREDENTIALS_PATH), scopes=SCOPES)
        client = gspread.authorize(creds)

        try:
            sheet = client.open_by_key(req.spreadsheet_id)
        except Exception:
            return {"success": False, "error": f"Cannot open spreadsheet: {req.spreadsheet_id}"}

        # Ensure worksheet exists
        try:
            ws = sheet.worksheet(req.sheet_name)
        except Exception:
            ws = sheet.add_worksheet(title=req.sheet_name, rows=1000, cols=20)

        # Check if headers exist, add if empty
        existing = ws.get_all_values()
        if not existing:
            headers = [
                "Timestamp", "Filename", "File Type", "Drive URL", "Drive File ID",
                "Task ID", "Job ID", "Product Name", "File Size (bytes)", "Status", "Notes"
            ]
            ws.update("A1", [headers])
            row = 2
        else:
            row = len(existing) + 1

        # Append row
        row_data = [[
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            req.filename,
            req.file_type,
            req.drive_url,
            req.drive_file_id,
            req.task_id,
            req.job_id,
            req.product_name,
            req.file_size_bytes,
            req.status,
            req.notes,
        ]]
        ws.update(f"A{row}", row_data, value_input_option="USER_ENTERED")

        logger.info(f"Logged media '{req.filename}' to sheet row {row}")
        return {"success": True, "sheet_name": req.sheet_name, "row": row}

    except ImportError as e:
        return {"success": False, "error": f"Missing package: {e}. Run: pip install gspread google-auth"}
    except Exception as e:
        logger.error(f"Sheets log failed: {e}")
        return {"success": False, "error": str(e)[:500]}


# ─── Sheets: Read Log ────────────────────────────────────────────────────
@app.get("/sheets/media-log")
async def sheets_read_log(
    spreadsheet_id: str,
    sheet_name: str = "Media Log",
    limit: int = 100,
):
    """Read media log entries from a Google Sheet."""
    if not is_ready():
        return {"success": False, "error": "Credentials not configured"}

    try:
        import gspread
        from google.oauth2.service_account import Credentials as GCreds

        creds = GCreds.from_service_account_file(str(CREDENTIALS_PATH), scopes=SCOPES)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(spreadsheet_id)
        ws = sheet.worksheet(sheet_name)
        rows = ws.get_all_values()

        if not rows or len(rows) < 2:
            return {"success": True, "entries": [], "count": 0}

        headers = rows[0]
        entries = []
        for r in rows[1:1 + limit]:
            entry = {}
            for i, h in enumerate(headers):
                entry[h.lower().replace(" ", "_")] = r[i] if i < len(r) else ""
            entries.append(entry)

        return {"success": True, "sheet_name": sheet_name, "entries": entries, "count": len(entries)}

    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


# ─── Health ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "service": "drive-service",
        "credentials_configured": is_ready(),
        "uptime": time.time(),
    }


# ─── Main ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8132"))
    uvicorn.run(app, host="0.0.0.0", port=port)
