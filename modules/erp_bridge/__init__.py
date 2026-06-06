"""ERP Bridge — Module registration client

แต่ละ module เรียก register_module() ตอน startup
เพื่อ register ตัวเองกับ central ERP registry service.
"""
import os
import json
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

ERP_REGISTRY_URL = os.environ.get("ERP_REGISTRY_URL", "http://localhost:8100")
DEFAULT_MODULE_PREFIX = os.environ.get("MODULE_PREFIX", "modules")


async def register_module(
    name: str,
    version: str = "1.0.0",
    host: str = "localhost",
    port: int = 8100,
    description: str = "",
    tables: list = None,
    permissions: list = None,
    registry_url: str = None,
) -> dict:
    """
    Register this module with the ERP registry.

    Args:
        name: Module name (e.g. "auth", "payment")
        version: Semver
        host: Server hostname
        port: Module's HTTP port
        description: Human-readable description
        tables: List of DB table names this module owns
        permissions: List of permission keys
        registry_url: Override ERP registry URL

    Returns:
        Registry response dict
    """
    url = registry_url or ERP_REGISTRY_URL
    payload = {
        "name": name,
        "version": version,
        "endpoint": f"http://{host}:{port}",
        "description": description,
        "tables": tables or [],
        "permissions": permissions or [],
        "status": "online",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{url}/api/v1/modules/register",
                json=payload,
            )
            result = resp.json()
            logger.info(f"Module '{name}' registered: {resp.status_code}")
            return result
    except Exception as e:
        logger.warning(f"Module '{name}' registration failed: {e}")
        return {"error": str(e)}


async def deregister_module(name: str, registry_url: str = None):
    """Remove module from ERP registry."""
    url = registry_url or ERP_REGISTRY_URL
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(f"{url}/api/v1/modules/{name}")
            if resp.status_code == 200:
                logger.info(f"Module '{name}' deregistered")
    except Exception as e:
        logger.warning(f"Module '{name}' deregistration failed: {e}")


def get_module_url(name: str, registry_url: str = None) -> Optional[str]:
    """Get endpoint URL for a registered module."""
    url = registry_url or ERP_REGISTRY_URL
    try:
        import httpx
        resp = httpx.get(f"{url}/api/v1/modules/{name}", timeout=5)
        if resp.status_code == 200:
            return resp.json().get("endpoint")
    except Exception:
        pass
    return None
