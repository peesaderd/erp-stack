"""
ERP Modular MCP Server — stdio mode for AI Agent access

ให้ AI Agents (Claude, OpenHands, GPT) สามารถเรียกใช้งาน modules ทั้งหมด
ผ่าน MCP Protocol (Model Context Protocol)

Modules ที่เชื่อม:
  - Profile Module (port 8107) — Business & Client profiles
  - Payment Module (port 8122) — Stripe + QR PromptPay
  - Image Generation (port 8190) — AI Image generation
  - Video Generation (port 8116) — AI Video generation
  - Media Module (port 8103) — File/media upload
  - Auth Module (port 8101) — User/authentication

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
SERVICES = {
    "profile":      {"url": "http://localhost:8107",   "name": "Profile Module"},
    "payment":      {"url": "http://localhost:8122",   "name": "Payment Module"},
    "image-gen":    {"url": "http://localhost:8110",   "name": "Image Generation"},
    "video-gen":    {"url": "http://localhost:8116",   "name": "Video Generation"},
    "media":        {"url": "http://localhost:8103",   "name": "Media Module"},
    "auth":         {"url": "http://localhost:8101",   "name": "Auth Module"},
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
        modules = result["data"].get("items", result["data"])
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
    """Check health status of all registered services."""
    statuses = {}
    for slug, info in SERVICES.items():
        result = await _http_call("GET", f"{info['url']}/health")
        statuses[slug] = {
            "name": info["name"],
            "url": info["url"],
            "alive": result["ok"],
            "status_code": result["status"],
        }
    return json.dumps({"services": statuses}, indent=2, ensure_ascii=False)


@mcp.tool()
async def call_api(
    module: str = "",
    method: str = "GET",
    path: str = "/health",
    body: str = "",
) -> str:
    """Call any API endpoint on a registered module.

    Args:
        module: Module slug (profile, payment, image-gen, video-gen, media, auth)
        method: HTTP method (GET, POST, PUT, DELETE)
        path: URL path (e.g., /api/v1/profiles/business)
        body: JSON body string (for POST/PUT)
    """
    service = SERVICES.get(module)
    if not service:
        return json.dumps({"ok": False, "error": f"Unknown module: {module}. Available: {list(SERVICES.keys())}"})

    url = f"{service['url']}{path}"
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
    """Call Payment Module functions.

    Args:
        action: One of: health, create_checkout, list_plans, create_qr, list_customers
        customer_email: Email for checkout/customer
        plan_id: Plan ID for checkout
        amount: Amount in satang (for QR)
        currency: Currency code (thb, usd)
    """
    pmt = SERVICES.get("payment")
    if not pmt:
        return json.dumps({"ok": False, "error": "Payment module not configured"})

    actions = {
        "health":              ("GET",  "/api/payment/health", {}),
        "list_plans":          ("GET",  "/api/payment/checkout/plans", {}),
        "list_customers":      ("GET",  "/api/payment/subscriptions/customers", {}),
        "create_checkout":     ("POST", "/api/payment/checkout/create", {"customerEmail": customer_email, "planId": plan_id, "successUrl": "https://wpilot.ai/success", "cancelUrl": "https://wpilot.ai/cancel"}),
        "create_qr":           ("POST", "/api/payment/qr/generate", {"amount": amount, "currency": currency}),
    }

    if action not in actions:
        return json.dumps({"ok": False, "error": f"Unknown action: {action}. Available: {list(actions.keys())}"})

    method, path, default_body = actions[action]
    url = f"{pmt['url']}{path}"
    result = await _http_call(method, url, json=default_body if method == "POST" else None)
    return json.dumps(result, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# Convenience Tools — Profile
# ═══════════════════════════════════════════════════════════════

@mcp.tool()
async def call_profile(
    action: str = "list_businesses",
    profile_id: str = "",
    name: str = "",
    email: str = "",
    phone: str = "",
    tax_id: str = "",
    business_name: str = "",
    client_name: str = "",
    search: str = "",
) -> str:
    """Call Profile Module (Business & Client profiles).

    Args:
        action: One of: list_businesses, get_business, create_business, update_business,
                delete_business, list_clients, get_client, create_client, update_client,
                delete_client, health
        profile_id: ID for specific profile operations
        name: Business or Client name (for create)
        email: Client email
        phone: Business phone
        tax_id: Business tax ID
        business_name: Alias for name (create_business)
        client_name: Alias for name (create_client)
        search: Search term for list
    """
    svc = SERVICES.get("profile")
    if not svc:
        return json.dumps({"ok": False, "error": "Profile module not configured"})

    base = svc["url"]

    # Map actions
    action_map = {
        "health":           ("GET",  "/health", None),
        "list_businesses":  ("GET",  "/api/v1/profiles/business", {"search": search}),
        "get_business":     ("GET",  f"/api/v1/profiles/business/{profile_id}", None),
        "create_business":  ("POST", "/api/v1/profiles/business", {
            "name": business_name or name or "New Business",
            "tax_id": tax_id,
            "phone": phone,
        }),
        "update_business":  ("PUT",  f"/api/v1/profiles/business/{profile_id}", {
            "name": name, "tax_id": tax_id, "phone": phone,
        }),
        "delete_business":  ("DELETE", f"/api/v1/profiles/business/{profile_id}", None),
        "list_clients":     ("GET",  "/api/v1/profiles/client", {"search": search}),
        "get_client":       ("GET",  f"/api/v1/profiles/client/{profile_id}", None),
        "create_client":    ("POST", "/api/v1/profiles/client", {
            "name": client_name or name or "New Client",
            "email": email, "phone": phone,
        }),
        "update_client":    ("PUT",  f"/api/v1/profiles/client/{profile_id}", {
            "name": name, "email": email, "phone": phone,
        }),
        "delete_client":    ("DELETE", f"/api/v1/profiles/client/{profile_id}", None),
    }

    if action not in action_map:
        return json.dumps({"ok": False, "error": f"Unknown action: {action}. Available: {list(action_map.keys())}"})

    method, path, default_body = action_map[action]

    kwargs = {}
    if method == "POST" and default_body:
        kwargs["json"] = {k: v for k, v in default_body.items() if v}
    elif method == "PUT" and default_body:
        kwargs["json"] = {k: v for k, v in default_body.items() if v}
    elif method == "GET" and default_body:
        params = {k: v for k, v in default_body.items() if v}
        if params:
            kwargs["params"] = params

    url = f"{base}{path}"
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
