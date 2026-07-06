"""
ERP Modular MCP Server — stdio mode for AI Agent access

ให้ AI Agents (Claude, OpenHands, GPT) สามารถเรียกใช้งาน ERP Modular
ผ่าน MCP Protocol (Model Context Protocol)

ERP Modular เป็น unified FastAPI service บน port 8102 ที่รวม:
  - Auth + Rate Limiting
  - Module Registry (/api/v1/modules)
  - Entity CRUD (/api/v1/entities)
  - Template CRUD (/api/v1/templates)
  - Agent Activity Logging (/agent/logs)

Usage:
  python3 erp_mcp_server.py                    # stdio mode
  python3 erp_mcp_server.py --http :8000       # SSE mode

For OpenClaw config:
  "mcpServers": {
    "erp-modular": {
      "type": "stdio",
      "command": "python3",
      "args": ["/home/openhands/erp-stack/mcp/erp_mcp_server.py"]
    }
  }
"""

import json, os, sys, logging, uuid, asyncio
from typing import Optional, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import httpx

# ═══════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════

ERP_MODULAR_URL = "http://localhost:8102"
# ERP Modular is a unified service — all tools route through it.
# The old sub-module architecture (profile/payment/media/auth as separate microservices)
# was merged into a single FastAPI app on port 8102.
SERVICES = {
    "erp-modular": {"url": ERP_MODULAR_URL, "name": "ERP Modular"},
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("erp-mcp")

# ═══════════════════════════════════════════════════════════════
# FastMCP Server
# ═══════════════════════════════════════════════════════════════

from mcp.server import FastMCP

mcp = FastMCP(
    "ERP Modular MCP",
    instructions="""ERP Modular MCP Server — ให้ AI Agent จัดการ ERP modules ผ่าน MCP Protocol

Tools ที่มี:
  1. list_modules — ดู modules ที่ลงทะเบียนใน ERP Modular
  2. call_api — เรียก API ของ module ใดๆ (GET/POST/PUT/DELETE)
  3. get_health — ตรวจสอบว่า service ไหนรันอยู่บ้าง
  4. register_service — ลงทะเบียน service ใหม่เข้ากับ ERP Modular
  5. call_payment — เรียกฟังก์ชัน Payment โดยตรง
  6. call_profile — เรียกฟังก์ชัน Profile โดยตรง
""",
)

# ═══════════════════════════════════════════════════════════════
# HTTP Helper
# ═══════════════════════════════════════════════════════════════

async def _http_call(method: str, url: str, **kwargs) -> dict:
    """Make HTTP call with timeout and error handling."""
    timeout = httpx.Timeout(30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            resp = await client.request(method, url, **kwargs)
            try:
                data = resp.json()
            except Exception:
                data = {"text": resp.text}
            return {
                "ok": resp.status_code < 400,
                "status": resp.status_code,
                "data": data,
            }
    except httpx.ConnectError:
        return {"ok": False, "status": 0, "error": f"Connection refused: {url}"}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e)}

# ═══════════════════════════════════════════════════════════════
# Tools
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def list_modules() -> str:
    """List all modules registered in ERP Modular."""
    result = await _http_call("GET", f"{ERP_MODULAR_URL}/api/v1/modules")
    if result["ok"]:
        data = result["data"]
        modules = data.get("items", data) if isinstance(data, dict) else data
        if isinstance(modules, dict):
            modules = [modules]
        return json.dumps({
            "ok": True,
            "count": len(modules),
            "modules": [
                {
                    "name": m.get("name", m.get("slug", "?")),
                    "slug": m.get("slug", "?"),
                    "version": m.get("version", "?"),
                    "endpoint": m.get("endpoint", m.get("url", "?")),
                }
                for m in modules
            ],
        }, indent=2, ensure_ascii=False)
    # Fallback: return known services
    services_list = [
        {"name": info["name"], "slug": slug, "url": info["url"]}
        for slug, info in SERVICES.items()
    ]
    return json.dumps({
        "ok": True,
        "note": "From local config (ERP Modular unreachable)",
        "count": len(services_list),
        "modules": services_list,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_health() -> str:
    """Check health status of ERP Modular service."""
    result = await _http_call("GET", f"{ERP_MODULAR_URL}/health")
    if result["ok"]:
        health_data = result.get("data", {})
        return json.dumps({
            "status": "ok",
            "service": "ERP Modular",
            "url": ERP_MODULAR_URL,
            "version": health_data.get("version", "?"),
            "gateway": health_data.get("gateway", False),
            "auth": health_data.get("auth", False),
            "rate_limit": health_data.get("rate_limit", False),
        }, indent=2, ensure_ascii=False)
    return json.dumps({
        "status": "error",
        "service": "ERP Modular",
        "url": ERP_MODULAR_URL,
        "error": result.get("error", "Unreachable"),
    }, indent=2, ensure_ascii=False)


@mcp.tool()
async def call_api(
    module: str = "",
    method: str = "GET",
    path: str = "/health",
    body: str = "",
) -> str:
    """Call any API endpoint on ERP Modular.

    All routes go through the unified ERP Modular service on port 8102.
    Available API namespaces:
      - /api/v1/modules     — Module registry
      - /api/v1/entities    — CRUD entities
      - /api/v1/templates   — Templates
      - /agent/logs         — Activity logs
      - /agent/stats        - Agent stats
      - /health             - Health check

    Args:
        module: Ignored (all routes go to ERP Modular). Kept for backward compat.
        method: HTTP method (GET, POST, PUT, DELETE, PATCH)
        path: URL path (e.g., /api/v1/entities)
        body: JSON body string (for POST/PUT/PATCH)
    """
    url = f"{ERP_MODULAR_URL}{path}"
    kwargs = {}
    if body and method in ("POST", "PUT", "PATCH"):
        try:
            kwargs["json"] = json.loads(body)
        except json.JSONDecodeError:
            kwargs["data"] = body
            kwargs["headers"] = {"Content-Type": "application/json"}

    result = await _http_call(method, url, **kwargs)
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
async def register_service(
    name: str = "",
    slug: str = "",
    version: str = "1.0.0",
    endpoint: str = "",
    description: str = "",
) -> str:
    """Register a new service/module with the ERP Modular registry.

    Args:
        name: Human-friendly service name (e.g., "Social Post Service")
        slug: URL-safe identifier (e.g., "social-post")
        version: Semver version
        endpoint: Full URL of the service (e.g., http://localhost:8112)
        description: Short description
    """
    payload = {
        "name": name or slug,
        "slug": slug,
        "version": version,
        "endpoint": endpoint,
        "description": description,
    }
    result = await _http_call("POST", f"{ERP_MODULAR_URL}/api/v1/modules/register", json=payload)
    return json.dumps(result, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# Convenience Tools — Payment
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def call_payment(
    action: str = "health",
    customer_email: str = "",
    plan_id: str = "",
    amount: int = 0,
    currency: str = "thb",
) -> str:
    """Call Payment functions via ERP Modular entities API.

    Routes through ERP Modular's /api/v1/entities?type=payment.
    Dedicated payment endpoints (create_checkout, create_qr) to be added.

    Args:
        action: One of: health, list, get, create
        customer_email: Email for customer lookup
        plan_id: Plan ID reference
        amount: Amount in satang
        currency: Currency code (thb, usd)
    """
    actions = {
        "health":              ("GET",  "/health", None),
        "list":                ("GET",  "/api/v1/entities?type=payment", None),
        "list_customers":      ("GET",  "/api/v1/entities?type=customer", None),
        "create":              ("POST", "/api/v1/entities", {"type": "payment", "fields": {"email": customer_email, "amount": amount, "currency": currency, "planId": plan_id}}),
    }

    if action not in actions:
        return json.dumps({"ok": False, "error": f"Unknown action: {action}. Available: {list(actions.keys())}"})

    method, path, default_body = actions[action]
    url = f"{ERP_MODULAR_URL}{path}"
    kwargs = {"json": default_body} if method == "POST" and default_body else {}
    result = await _http_call(method, url, **kwargs)
    return json.dumps(result, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# Prompt Studio Tools — Centralized Prompt Registry
# ═══════════════════════════════════════════════════════════════

PROMPT_STUDIO_URL = os.environ.get("PROMPT_STUDIO_URL", "http://localhost:8108")


@mcp.tool()
async def prompts_list() -> str:
    """List all prompt modules available from Prompt Studio.

    Returns a structured list of prompt modules (tiktok, ugc, image)
    with submodules and file counts.
    """
    result = await _http_call("GET", f"{PROMPT_STUDIO_URL}/modules")
    if result["ok"]:
        data = result["data"]
        return json.dumps({
            "ok": True,
            "total": data.get("total", 0),
            "mode": data.get("mode", "unknown"),
            "modules": data.get("modules", []),
        }, indent=2, ensure_ascii=False)
    return json.dumps({"ok": False, "error": "Prompt Studio unreachable"}, indent=2)


@mcp.tool()
async def resources_list() -> str:
    """List all available prompt files from Prompt Studio.

    Returns a flat list of all prompt files across all modules
    with their paths, sizes, and module names.
    """
    modules_result = await _http_call("GET", f"{PROMPT_STUDIO_URL}/modules")
    if not modules_result["ok"]:
        return json.dumps({"ok": False, "error": "Prompt Studio unreachable"}, indent=2)

    modules = modules_result["data"].get("modules", [])
    resources = []

    for mod in modules:
        mod_name = mod["name"]
        prompts_result = await _http_call("GET", f"{PROMPT_STUDIO_URL}/prompts/{mod_name}")
        if prompts_result["ok"]:
            for f in prompts_result["data"].get("files", []):
                resource = {
                    "name": f"prompts/{mod_name}/{f['name']}",
                    "module": mod_name,
                    "path": f["path"],
                    "size": f["size"],
                    "uri": f"prompt-studio://{mod_name}/{f['name']}",
                }
                if mod.get("submodules"):
                    resource["submodule"] = mod["submodules"]
                resources.append(resource)

    return json.dumps({
        "ok": True,
        "total": len(resources),
        "resources": resources,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
async def get_prompt(module: str = "", name: str = "") -> str:
    """Get the content of a specific prompt from Prompt Studio.

    Args:
        module: Module name (e.g., tiktok, ugc, image)
        name: Prompt file name (e.g., system.prompt.txt, master.prompt.txt)
    """
    if not module or not name:
        return json.dumps({"ok": False, "error": "module and name required"}, indent=2)
    result = await _http_call("GET", f"{PROMPT_STUDIO_URL}/prompts/{module}/{name}")
    if result["ok"]:
        data = result["data"]
        return json.dumps({
            "ok": True,
            "module": data.get("module", module),
            "name": data.get("name", name),
            "content": data.get("content", ""),
            "size": data.get("size", 0),
            "mode": data.get("mode", "unknown"),
        }, indent=2, ensure_ascii=False)
    return json.dumps({"ok": False, "error": f"Prompt not found: {module}/{name}"}, indent=2)


# ═══════════════════════════════════════════════════════════════
# Convenience Tools — Profile
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def call_profile(
    action: str = "list",
    profile_id: str = "",
    name: str = "",
    email: str = "",
    phone: str = "",
    tax_id: str = "",
    business_name: str = "",
    client_name: str = "",
    search: str = "",
) -> str:
    """Call Profile functions via ERP Modular entities API.

    Routes through ERP Modular's /api/v1/entities.
    Dedicated profile endpoints to be added in future.

    Args:
        action: One of: health, list, get, create, search
        profile_id: Entity ID for specific operations
        name: Name for create action
        email: Email field
        phone: Phone field
        tax_id: Tax ID field
        business_name: Alias for name (create action)
        client_name: Alias for name (create action)
        search: Search term
    """
    action_map = {
        "health":           ("GET",  "/health", None, {}),
        "list":             ("GET",  "/api/v1/entities?type=profile", None, {}),
        "get":              ("GET",  f"/api/v1/entities/{profile_id}", None, {}),
        "create":           ("POST", "/api/v1/entities", None, {
            "type": "profile",
            "fields": {"name": business_name or client_name or name or "New", "email": email, "phone": phone, "taxId": tax_id},
        }),
        "search":           ("GET",  "/api/v1/entities?type=profile", None, {"search": search} if search else {}),
        "list_businesses":  ("GET",  "/api/v1/entities?type=profile&tag=business", None, {}),
        "list_clients":     ("GET",  "/api/v1/entities?type=profile&tag=client", None, {}),
    }

    if action not in action_map:
        return json.dumps({"ok": False, "error": f"Unknown action: {action}. Available: {list(action_map.keys())}"})

    method, path, _, body_template = action_map[action]
    url = f"{ERP_MODULAR_URL}{path}"
    kwargs = {}

    if method in ("POST", "PUT", "PATCH") and body_template:
        kwargs["json"] = {k: v for k, v in body_template.items() if v}
    elif method == "GET":
        # Pass search as query param
        pass

    result = await _http_call(method, url, **kwargs)
    return json.dumps(result, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════

def main():
    """Run MCP server in stdio mode (default) or SSE/HTTP mode."""
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        host = "0.0.0.0"
        port = 8109
        if len(sys.argv) > 2:
            parts = sys.argv[2].split(":")
            host = parts[0] if parts[0] else "0.0.0.0"
            port = int(parts[1]) if len(parts) > 1 else 8109
        logger.info(f"Starting ERP MCP server in SSE mode on {host}:{port}")
        mcp.run(host=host, port=port)
    else:
        logger.info("Starting ERP MCP server in stdio mode — ready for AI agent connection")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
