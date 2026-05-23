#!/usr/bin/env python3
"""
ERP Internal Bridge Service
============================
Provides passwordless access to all internal services for team members.
Acts as a reverse proxy with automatic authentication headers.

Usage:
    python bridge.py --port <port>
"""

import argparse
import json
import os
import time
import urllib.parse

import requests
from flask import Flask, Response, render_template_string, request, redirect

app = Flask(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────

REGISTRY_PATH = os.environ.get(
    "ERP_REGISTRY_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".erp-gateway", "services.json"),
)

# Default team API token for ERP Core (auto-injected for proxied requests)
ERP_API_TOKEN = os.environ.get("ERP_API_TOKEN", "")

# Services that need auth headers injected
AUTH_SERVICES = {"erp-core", "task-manager", "noteforge"}

# ─── Service Registry ────────────────────────────────────────────────────────


def load_registry():
    """Load services from the gateway registry JSON."""
    path = REGISTRY_PATH
    if not os.path.exists(path):
        # Fallback: try relative to workspace
        alt = "/workspace/.erp-gateway/services.json"
        if os.path.exists(alt):
            path = alt
        else:
            return {"services": {}}

    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"services": {}}


def get_services():
    """Get list of services with their status and URLs."""
    data = load_registry()
    services = data.get("services", {})

    # Also load from ERP Core registry if available
    erp_registry_path = os.environ.get(
        "ERP_CORE_REGISTRY_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "erp-core", "erp-core", "data", "erp-registry.json"),
    )

    result = []
    seen = set()

    # First, load from .erp-gateway/services.json
    for name, info in services.items():
        if name in ("register", "test"):
            continue
        seen.add(name)
        result.append({
            "name": info.get("name", name),
            "slug": name,
            "url": info.get("url", ""),
            "status": info.get("status", "unknown"),
            "type": info.get("type", "unknown"),
        })

    # Then, merge in from ERP Core registry for richer info
    if os.path.exists(erp_registry_path):
        try:
            with open(erp_registry_path) as f:
                erp_data = json.load(f)
            for name, info in erp_data.get("services", {}).items():
                if name in seen:
                    # Update existing
                    for svc in result:
                        if svc["slug"] == name:
                            svc["name"] = info.get("name", svc["name"])
                            svc["url"] = info.get("url", svc["url"]) or svc["url"]
                            svc["status"] = info.get("status", svc["status"])
                            break
                else:
                    result.append({
                        "name": info.get("name", name),
                        "slug": name,
                        "url": info.get("url", ""),
                        "status": info.get("status", "unknown"),
                        "type": info.get("type", "unknown"),
                    })
        except (json.JSONDecodeError, OSError):
            pass

    # Sort: live first, then building, then planned
    status_order = {"live": 0, "building": 1, "planned": 2, "offline": 3, "unknown": 4}
    result.sort(key=lambda s: (status_order.get(s["status"], 99), s["name"]))

    return result


# ─── Proxy Logic ─────────────────────────────────────────────────────────────


def proxy_request(service_url, path, method, headers, body):
    """Proxy an HTTP request to the target service."""
    target = urllib.parse.urljoin(service_url.rstrip("/") + "/", path.lstrip("/"))

    # Forward relevant headers
    forward_headers = {
        "Content-Type": headers.get("Content-Type", "application/json"),
        "Accept": headers.get("Accept", "*/*"),
    }

    # Inject auth token for known services
    if ERP_API_TOKEN:
        forward_headers["Authorization"] = f"Bearer {ERP_API_TOKEN}"

    try:
        resp = requests.request(
            method=method,
            url=target,
            headers=forward_headers,
            data=body,
            timeout=30,
            allow_redirects=False,
        )
        excluded = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
        return Response(resp.content, status=resp.status_code, headers=resp_headers)
    except requests.RequestException as e:
        return Response(
            json.dumps({"error": f"Bridge proxy error: {str(e)}"}),
            status=502,
            content_type="application/json",
        )


# ─── Routes ──────────────────────────────────────────────────────────────────


DASHBOARD_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ERP Internal Bridge</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 2rem; padding-bottom: 1rem;
            border-bottom: 1px solid #1e293b;
        }
        h1 { font-size: 1.75rem; font-weight: 700; color: #f8fafc; }
        h1 span { color: #38bdf8; }
        .subtitle { color: #94a3b8; font-size: 0.875rem; margin-top: 0.25rem; }
        .stats { display: flex; gap: 1rem; margin-bottom: 2rem; }
        .stat-card {
            background: #1e293b; border-radius: 0.75rem; padding: 1rem 1.5rem;
            flex: 1; text-align: center;
        }
        .stat-card .num { font-size: 1.5rem; font-weight: 700; color: #38bdf8; }
        .stat-card .label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
        .services { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1rem; }
        .card {
            background: #1e293b; border-radius: 0.75rem; padding: 1.25rem;
            transition: transform 0.15s, box-shadow 0.15s;
            border: 1px solid transparent;
        }
        .card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
        .card-header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem; }
        .card-name { font-size: 1.1rem; font-weight: 600; color: #f1f5f9; }
        .card-type {
            font-size: 0.7rem; padding: 0.2rem 0.5rem; border-radius: 999px;
            background: #334155; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em;
        }
        .card-url { font-size: 0.8rem; color: #64748b; margin-bottom: 0.75rem; word-break: break-all; }
        .card-url a { color: #38bdf8; text-decoration: none; }
        .card-url a:hover { text-decoration: underline; }
        .status-badge {
            display: inline-flex; align-items: center; gap: 0.35rem;
            font-size: 0.75rem; padding: 0.25rem 0.75rem; border-radius: 999px;
            font-weight: 500;
        }
        .status-live { background: #064e3b; color: #6ee7b7; }
        .status-building { background: #1c1917; color: #fcd34d; }
        .status-planned { background: #1e1b4b; color: #a5b4fc; }
        .status-offline { background: #450a0a; color: #fca5a5; }
        .status-unknown { background: #1e293b; color: #94a3b8; }
        .status-dot {
            width: 6px; height: 6px; border-radius: 50%; display: inline-block;
        }
        .status-live .status-dot { background: #6ee7b7; }
        .status-building .status-dot { background: #fcd34d; }
        .status-planned .status-dot { background: #a5b4fc; }
        .status-offline .status-dot { background: #fca5a5; }
        .card-actions { margin-top: 0.75rem; display: flex; gap: 0.5rem; }
        .btn {
            display: inline-block; padding: 0.4rem 1rem; border-radius: 0.5rem;
            font-size: 0.8rem; font-weight: 500; text-decoration: none;
            transition: background 0.15s;
        }
        .btn-primary { background: #0ea5e9; color: #fff; }
        .btn-primary:hover { background: #0284c7; }
        .btn-secondary { background: #334155; color: #e2e8f0; }
        .btn-secondary:hover { background: #475569; }
        .btn-disabled { background: #1e293b; color: #475569; cursor: not-allowed; }
        .footer {
            margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid #1e293b;
            text-align: center; font-size: 0.8rem; color: #475569;
        }
        @media (max-width: 640px) {
            .container { padding: 1rem; }
            .services { grid-template-columns: 1fr; }
            .stats { flex-direction: column; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1><span>ERP</span> Internal Bridge</h1>
                <div class="subtitle">Service Portal for Team — ไม่ต้องใช้ Password</div>
            </div>
            <div>
                <span class="status-badge status-live">
                    <span class="status-dot"></span>
                    Bridge Active
                </span>
            </div>
        </header>

        <div class="stats">
            <div class="stat-card">
                <div class="num">{{ stats.live }}</div>
                <div class="label">Live</div>
            </div>
            <div class="stat-card">
                <div class="num">{{ stats.building }}</div>
                <div class="label">Building</div>
            </div>
            <div class="stat-card">
                <div class="num">{{ stats.planned }}</div>
                <div class="label">Planned</div>
            </div>
            <div class="stat-card">
                <div class="num">{{ stats.total }}</div>
                <div class="label">Total Services</div>
            </div>
        </div>

        <div class="services">
            {% for svc in services %}
            <div class="card">
                <div class="card-header">
                    <span class="card-name">{{ svc.name }}</span>
                    <span class="card-type">{{ svc.type }}</span>
                </div>
                <div class="card-url">
                    {% if svc.url %}
                    <a href="{{ svc.url }}" target="_blank">{{ svc.url }}</a>
                    {% else %}
                    <span style="color: #475569;">No URL configured</span>
                    {% endif %}
                </div>
                <div>
                    <span class="status-badge status-{{ svc.status }}">
                        <span class="status-dot"></span>
                        {{ svc.status }}
                    </span>
                </div>
                <div class="card-actions">
                    {% if svc.url and svc.status == 'live' %}
                    <a href="/proxy/{{ svc.slug }}/" class="btn btn-primary" target="_blank">Open</a>
                    {% elif svc.url and svc.status == 'building' %}
                    <a href="/proxy/{{ svc.slug }}/" class="btn btn-secondary" target="_blank">Preview</a>
                    {% else %}
                    <span class="btn btn-disabled">Not Available</span>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>

        <div class="footer">
            ERP Internal Bridge &mdash; สำหรับทีมพัฒนาเท่านั้น
        </div>
    </div>
</body>
</html>
"""


@app.route("/")
def dashboard():
    services = get_services()
    stats = {"live": 0, "building": 0, "planned": 0, "total": len(services)}
    for svc in services:
        if svc["status"] in stats:
            stats[svc["status"]] += 1
    return render_template_string(DASHBOARD_TEMPLATE, services=services, stats=stats)


@app.route("/proxy/<service_name>/", defaults={"path": ""})
@app.route("/proxy/<service_name>/<path:path>")
def proxy(service_name, path):
    services = get_services()
    target = None
    for svc in services:
        if svc["slug"] == service_name:
            target = svc
            break

    if not target:
        return Response(
            json.dumps({"error": f"Service '{service_name}' not found"}),
            status=404,
            content_type="application/json",
        )

    if not target["url"]:
        return Response(
            json.dumps({"error": f"Service '{service_name}' has no URL configured"}),
            status=503,
            content_type="application/json",
        )

    return proxy_request(
        target["url"],
        path,
        request.method,
        dict(request.headers),
        request.get_data(),
    )


@app.route("/api/services")
def api_services():
    services = get_services()
    return Response(json.dumps(services, indent=2), content_type="application/json")


@app.route("/health")
def health():
    return Response(json.dumps({"status": "ok", "timestamp": time.time()}), content_type="application/json")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ERP Internal Bridge Service")
    parser.add_argument("--port", type=int, default=51517, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()

    print(f"[Bridge] Starting ERP Internal Bridge on http://{args.host}:{args.port}")
    print(f"[Bridge] Dashboard: http://{args.host}:{args.port}/")
    print(f"[Bridge] Registry: {REGISTRY_PATH}")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
