"""
Prodia Pricing Module — Dynamic Real-Time Pricing
===================================================
Fetches actual pricing from Prodia and maps model_type → cost.
Falls back to cached/hardcoded prices when Prodia is unreachable.

Usage:
    from prodia_pricing import get_price

    cost = get_price("nano-banana.img2img.v2")  # → 0.039
    cost = get_price("wan2-7.txt2vid.v1")       # → 0.030
"""

import json
import os
import time
import logging
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("prodia-pricing")

# ─── Pricing Cache ─────────────────────────────────────────────────────────

PRICING_CACHE_PATH = Path(__file__).parent / "prodia_pricing_cache.json"
CACHE_TTL_SECONDS = 3600  # Refresh every hour

# Default prices (verified against https://inference.prodia.com/pricing as of 2026-07-13)
# These are fallbacks — real prices come from Prodia API response or pricing page
DEFAULT_PRICES: dict[str, float] = {
    # Image models
    "nano-banana.img2img.v2": 0.039,    # Nano Banana (Gemini 2.5 Flash, 1K)
    "flux-2.dev.txt2img.v1": 0.010,     # Flux 2 Dev (1K) — deprecated, removed from our code
    "sdxl.txt2img.v1": 0.004,           # SDXL (1K)
    
    # Video models  
    "wan2-7.txt2vid.v1": 0.030,         # Wan 2.7 txt2vid
    "wan2-7.img2vid.v1": 0.035,         # Wan 2.7 img2vid
    
    # Default/unknown
    "default": 0.005,
}

# ─── Price from Prodia async job result ────────────────────────────────────

def extract_price_from_job_result(job_result: dict, model_type: str = "") -> dict:
    """
    Extract REAL pricing from Prodia async job result.
    
    Prodia async API returns: {
        "price": {
            "dollars": 0.030,
            "credits_spent": 3000,
            ...
        }
    }
    
    Returns {"dollars": float, "product": str}
    Uses API-returned price when available, falls back to cached/hardcoded.
    """
    api_price = job_result.get("price", {})
    dollars = api_price.get("dollars")
    
    if dollars is not None and dollars > 0:
        logger.info(f"  💰 Real price from Prodia: ${dollars} for {model_type}")
        # Cache this price for future reference
        _update_cache(model_type, dollars)
        return {"dollars": dollars, "product": model_type, "source": "api"}
    
    # Fallback: use cached/known price
    fallback = get_price(model_type)
    logger.info(f"  💰 Using cached price: ${fallback} for {model_type} (no price in API response)")
    return {"dollars": fallback, "product": model_type, "source": "fallback"}


# ─── Price Lookup ──────────────────────────────────────────────────────────

def get_price(model_type: str) -> float:
    """
    Get current price for a model type.
    
    1. Check cache file (refreshed hourly)
    2. Fall back to DEFAULT_PRICES
    3. Fall back to "default" entry
    """
    # Try cache first
    cached = _read_cache()
    if model_type in cached:
        return cached[model_type]
    
    # Try defaults
    if model_type in DEFAULT_PRICES:
        return DEFAULT_PRICES[model_type]
    
    # Try partial match (e.g. "nano-banana" matches "nano-banana.img2img.v2")
    for key, price in {**cached, **DEFAULT_PRICES}.items():
        if model_type in key or key in model_type:
            return price
    
    # Ultimate fallback
    logger.warning(f"No price found for {model_type}, using default ${DEFAULT_PRICES['default']}")
    return DEFAULT_PRICES["default"]


def get_price_for_sync_image(model_type: str = "nano-banana.img2img.v2") -> dict:
    """
    Get price for sync image generation (no price in API response).
    
    Returns {"dollars": float, "product": str, "source": str}
    """
    dollars = get_price(model_type)
    return {"dollars": dollars, "product": model_type, "source": "local"}


# ─── Cache Management ──────────────────────────────────────────────────────

def _read_cache() -> dict[str, float]:
    """Read pricing cache from disk."""
    try:
        if not PRICING_CACHE_PATH.exists():
            return {}
        
        mtime = PRICING_CACHE_PATH.stat().st_mtime
        if time.time() - mtime > CACHE_TTL_SECONDS:
            # Cache expired
            return {}
        
        with open(PRICING_CACHE_PATH) as f:
            data = json.load(f)
        
        prices = data.get("prices", {})
        saved_at = data.get("saved_at", 0)
        if time.time() - saved_at > CACHE_TTL_SECONDS:
            return {}
        
        return prices
    except Exception as e:
        logger.debug(f"Cache read failed: {e}")
        return {}


def _update_cache(model_type: str, dollars: float) -> None:
    """Update a single price in the cache."""
    try:
        prices = _read_cache()
        prices[model_type] = dollars
        _write_cache(prices)
    except Exception as e:
        logger.debug(f"Cache update failed: {e}")


def _write_cache(prices: dict[str, float]) -> None:
    """Write pricing cache to disk."""
    try:
        data = {
            "prices": prices,
            "saved_at": time.time(),
            "source": "prodia_api_response",
        }
        with open(PRICING_CACHE_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.debug(f"Cache write failed: {e}")


def refresh_pricing_from_prodia() -> bool:
    """
    Try to refresh prices from Prodia pricing page.
    Returns True if successful.
    """
    try:
        resp = requests.get(
            "https://inference.prodia.com/pricing",
            headers={"Accept": "application/json, text/html"},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.debug(f"Pricing page returned {resp.status_code}")
            return False
        
        # Prodia pricing page is HTML — parse model prices
        # This is best-effort; default prices are the authoritative fallback
        text = resp.text
        
        # Try to extract prices from page content
        # Pattern: model names + dollar amounts
        import re
        extracted = {}
        
        # Look for model-price patterns in the page
        for model_key, _ in DEFAULT_PRICES.items():
            if model_key == "default":
                continue
            # Search for the model name nearby a dollar amount
            short_name = model_key.split(".")[0]  # e.g. "nano-banana"
            pattern = re.compile(
                rf'{re.escape(short_name)}.*?\$?(\d+\.?\d*)',
                re.IGNORECASE | re.DOTALL,
            )
            match = pattern.search(text)
            if match:
                try:
                    extracted[model_key] = float(match.group(1))
                except ValueError:
                    pass
        
        if extracted:
            _write_cache(extracted)
            logger.info(f"💰 Refreshed {len(extracted)} prices from Prodia: {extracted}")
            return True
        
        return False
    except Exception as e:
        logger.debug(f"Price refresh failed: {e}")
        return False


# ─── Startup ───────────────────────────────────────────────────────────────

# Try to refresh prices on module load (fire-and-forget)
try:
    refresh_pricing_from_prodia()
except Exception:
    pass  # Silent — defaults are fine
