"""
LINE Rich Menu MCP Server - create/manage LINE Rich Menus via AI
================================================================
Tools:
  - create_rich_menu         create + optional image upload + set default
  - get_rich_menus           list all
  - get_rich_menu            get by id
  - set_default_rich_menu    set default
  - link_rich_menu_to_user   link to user
  - delete_rich_menu         delete by id
"""

import json
import logging
import os
import sys
import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger("line-richmenu-mcp")

LINE_API_BASE = "https://api.line.me/v2/bot"

mcp = FastMCP(
    "LINE Rich Menu MCP",
    instructions="LINE Rich Menu MCP - create/manage LINE Rich Menus via AI",
)

def _get_token() -> str:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is not set in environment")
    return token

def _api_headers() -> dict:
    return {"Authorization": f"Bearer {_get_token()}", "Content-Type": "application/json"}

async def _api_call(method: str, path: str, **kwargs) -> dict:
    url = f"{LINE_API_BASE}{path}"
    timeout = httpx.Timeout(30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, headers=_api_headers(), **kwargs)
            if resp.status_code >= 400:
                return {"ok": False, "status": resp.status_code, "error": resp.text}
            if resp.status_code == 200 and resp.content:
                try:
                    return {"ok": True, "data": resp.json()}
                except Exception:
                    return {"ok": True, "status": resp.status_code, "data": {}}
            return {"ok": True, "status": resp.status_code, "data": {}}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}

async def _upload_image(rich_menu_id: str, image_url: str) -> dict:
    token = _get_token()
    timeout = httpx.Timeout(60.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            img_resp = await client.get(image_url)
            if img_resp.status_code >= 400:
                return {"ok": False, "error": f"Cannot fetch image: {img_resp.status_code}"}
            ct = img_resp.headers.get("content-type", "image/png")
            if ct not in ("image/png", "image/jpeg"):
                ct = "image/png"
            upload_url = f"{LINE_API_BASE}/richmenu/{rich_menu_id}/content"
            upload_headers = {"Authorization": f"Bearer {token}", "Content-Type": ct}
            upload_resp = await client.request("POST", upload_url, headers=upload_headers, content=img_resp.content)
            if upload_resp.status_code >= 400:
                return {"ok": False, "status": upload_resp.status_code, "error": upload_resp.text}
            return {"ok": True, "status": upload_resp.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
async def create_rich_menu(name: str, chat_bar_text: str, areas_json: str, size: str = "full", selected: bool = True, image_url: str = "", set_as_default: bool = False) -> str:
    """Create a new LINE Rich Menu. areas_json = JSON array with bounds {x,y,width,height} and action {type,label,...}."""
    sm = {"full": {"width": 2500, "height": 1686}, "half": {"width": 2500, "height": 843}}
    if size not in sm:
        return json.dumps({"ok": False, "error": f"Invalid size '{size}'. Use full or half."})
    try:
        areas = json.loads(areas_json)
        if not isinstance(areas, list):
            return json.dumps({"ok": False, "error": "areas_json must be a JSON array"})
    except json.JSONDecodeError as e:
        return json.dumps({"ok": False, "error": f"Invalid areas JSON: {e}"})
    for i, a in enumerate(areas):
        if "bounds" not in a or "action" not in a:
            return json.dumps({"ok": False, "error": f"Area {i} missing bounds or action"})
        for k in ("x", "y", "width", "height"):
            if k not in a["bounds"]:
                return json.dumps({"ok": False, "error": f"Area {i}.bounds missing {k}"})
    payload = {"size": sm[size], "selected": selected, "name": name[:300], "chatBarText": chat_bar_text[:14], "areas": areas}
    result = await _api_call("POST", "/richmenu", json=payload)
    if not result["ok"]:
        return json.dumps(result, ensure_ascii=False)
    rid = result["data"]["richMenuId"]
    msg = f"OK RichMenuId: {rid}"
    if image_url:
        ir = await _upload_image(rid, image_url)
        msg += " +img" if ir["ok"] else f" img-fail:{ir.get('error','?')}"
    if set_as_default:
        dr = await _api_call("POST", f"/richmenu/{rid}/default")
        msg += " +default" if dr["ok"] else f" default-fail:{dr.get('error','?')}"
    return json.dumps({"ok": True, "richMenuId": rid, "message": msg}, ensure_ascii=False)

@mcp.tool()
async def get_rich_menus() -> str:
    """List all rich menus."""
    result = await _api_call("GET", "/richmenu/list")
    if not result["ok"]:
        return json.dumps(result, ensure_ascii=False)
    menus = result["data"].get("richMenus", [])
    out = []
    for m in menus:
        out.append({"richMenuId": m.get("richMenuId"), "name": m.get("name"), "chatBarText": m.get("chatBarText"), "selected": m.get("selected", False), "size": m.get("size"), "areaCount": len(m.get("areas", []))})
    return json.dumps({"ok": True, "count": len(out), "menus": out}, ensure_ascii=False, indent=2)

@mcp.tool()
async def get_rich_menu(rich_menu_id: str) -> str:
    """Get details of a specific rich menu."""
    result = await _api_call("GET", f"/richmenu/{rich_menu_id}")
    if not result["ok"]:
        return json.dumps(result, ensure_ascii=False)
    return json.dumps({"ok": True, "menu": result["data"]}, ensure_ascii=False, indent=2)

@mcp.tool()
async def set_default_rich_menu(rich_menu_id: str) -> str:
    """Set a rich menu as default for all users."""
    result = await _api_call("POST", f"/richmenu/{rich_menu_id}/default")
    if not result["ok"]:
        return json.dumps(result, ensure_ascii=False)
    return json.dumps({"ok": True, "message": f"Default: {rich_menu_id}"}, ensure_ascii=False)

@mcp.tool()
async def link_rich_menu_to_user(user_id: str, rich_menu_id: str) -> str:
    """Link a rich menu to a specific LINE user."""
    result = await _api_call("POST", f"/user/{user_id}/richmenu/{rich_menu_id}")
    if not result["ok"]:
        return json.dumps(result, ensure_ascii=False)
    return json.dumps({"ok": True, "message": f"Linked {rich_menu_id} -> {user_id}"}, ensure_ascii=False)

@mcp.tool()
async def delete_rich_menu(rich_menu_id: str) -> str:
    """Delete a rich menu."""
    result = await _api_call("DELETE", f"/richmenu/{rich_menu_id}")
    if not result["ok"]:
        return json.dumps(result, ensure_ascii=False)
    return json.dumps({"ok": True, "message": f"Deleted {rich_menu_id}"}, ensure_ascii=False)

def main():
    mcp.run()

if __name__ == "__main__":
    main()


@mcp.tool()
async def get_line_login_url() -> dict:
    """Get official LINE Login authorization URL for users."""
    login_url = "https://m2igen.com/api/auth/line/login"
    return {
        "ok": True,
        "line_login_url": login_url,
        "description": "Send this URL to users to login via LINE OAuth"
    }

@mcp.tool()
async def check_line_webhook_status() -> dict:
    """Check status of LINE Webhook and Auth API endpoints."""
    endpoints = [
        "https://m2igen.com/line/webhook",
        "https://openhands.m2igen.com/line/webhook",
        "https://m2igen.com/api/auth/line/login"
    ]
    results = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for ep in endpoints:
            try:
                resp = await client.get(ep, follow_redirects=False)
                results[ep] = {"status_code": resp.status_code, "ok": resp.status_code in (200, 301, 302, 307)}
            except Exception as e:
                results[ep] = {"error": str(e), "ok": False}
    return {"ok": True, "endpoints": results}
