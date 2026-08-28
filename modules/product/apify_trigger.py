"""Apify trigger adapter for the Product Scraper service (port 8106).

Receives a TikTok Shop link (product URL / video / affiliate short link) or a
keyword from TUS, resolves it to a TikTok Shop product, calls the Apify actor to
scrape it, maps the actor output to the camelCase fields that
``ProductNormalizer._normalize_apify`` expects, then feeds it into the existing
``ingest_from_apify`` pipeline (analyze + enrich + sync to tus_products.db).

Designed to be imported and wired into the FastAPI app (product/main.py). It does
NOT reach into the video pipeline; products are imported through the SCRAPER
session only, exactly like the dedicated /product/scrape-pipeline flow.
"""
from __future__ import annotations

import os
import re
import json
import logging
import asyncio
from typing import Optional, Dict, Any, Tuple

import httpx

logger = logging.getLogger("apify_trigger")


# ─── Actor selection ────────────────────────────────────────────────────────
# Product-URL / product-ID scraping (mobile API, no CAPTCHA). Used for links.
ACTOR_PRODUCT = "cunning_soil/tiktok-shop-product-scraper-mobile-api"
# Keyword search fallback (returns a list of products).
ACTOR_SEARCH = "cunning_soil/tiktok-shop-product-search-api"


# ─── Env loading ────────────────────────────────────────────────────────────
# product/main.py only tries to load `modules/tiktok-ugc-studio/.env` (which does
# not exist), so APIFY_API_KEY is NOT in os.environ for this service. We load the
# key directly from the root .env (/home/openhands/erp-stack/.env) to be sure.
_ENV_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"),   # erp-stack/.env
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"),          # modules/.env
    "/home/openhands/erp-stack/.env",
]

def _load_env() -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for p in _ENV_CANDIDATES:
        p = os.path.abspath(p)
        if not os.path.exists(p):
            continue
        try:
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        merged.setdefault(k.strip(), v.strip())
        except Exception as e:  # pragma: no cover
            logger.warning(f"Could not read env file {p}: {e}")
    return merged


_env = _load_env()
APIFY_API_KEY = os.environ.get("APIFY_API_KEY") or _env.get("APIFY_API_KEY", "")
APIFY_API_BASE = "https://api.apify.com/v2"


# ─── Link resolution ─────────────────────────────────────────────────────────
_PDP_RE = re.compile(r"pdp/(\d{8,25})", re.I)
_VIEW_PRODUCT_RE = re.compile(r"(?:view|product[s]?)/\s*(\d{8,25})", re.I)
_VT_RE = re.compile(r"vt\.tiktok\.com/[A-Za-z0-9_-]+", re.I)


def extract_product_id(text: str) -> str:
    """Pull a 19-digit-ish TikTok Shop product id from a link or raw id."""
    text = text.strip()
    if text.isdigit():
        return text
    for pat in (_PDP_RE, _VIEW_PRODUCT_RE, re.compile(r"(\d{15,25})")):
        m = pat.search(text)
        if m:
            return m.group(1)
    return ""


def extract_product_title_from_url(url: str) -> str:
    """Pull the og_info.title from a TikTok PDP redirect URL (percent-encoded JSON).
    Falls back to empty string if not found.
    """
    if not url:
        return ""
    m = re.search(r"og_info=([^&]+)", url)
    if not m:
        return ""
    import urllib.parse
    try:
        og = json.loads(urllib.parse.unquote(m.group(1)))
        return og.get("title", "")
    except Exception:
        return ""


def resolve_link(link: str) -> Tuple[str, str, str]:
    """Resolve a link to (product_id, canonical_product_url, product_title).
    Handles:
    - vt.tiktok.com short links (follow redirect once to find the pdp)
    - shop.tiktok.com/.../pdp/<id> direct product links
    - /view/product/<id> links
    Returns ("", "", "") if no product id can be found.
    """
    pid = extract_product_id(link)
    if pid:
        return pid, f"https://shop.tiktok.com/view/product/{pid}", ""

    if _VT_RE.search(link):
        try:
            r = httpx.get(
                link,
                follow_redirects=True,
                timeout=20.0,
                headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"},
            )
            final_url = str(r.url)
            pid = extract_product_id(final_url)
            title = extract_product_title_from_url(final_url)
            if pid:
                return pid, f"https://shop.tiktok.com/view/product/{pid}", title
        except Exception as e:
            logger.warning(f"resolve_link redirect failed for {link}: {e}")

    return "", "", ""


def guess_region(link: str = "", keyword: str = "") -> str:
    """Best-effort region detection ('TH' default for this business)."""
    if "/th/" in link or "share_region=TH" in link or "shop.tiktok.com/th" in link:
        return "TH"
    return "TH"


# ─── Apify client ────────────────────────────────────────────────────────────
async def _call_actor(actor_id: str, run_input: dict, timeout: float = 300.0) -> list:
    """Run an Apify actor and return its dataset items.

    Uses run-sync-get-dataset-items (server waits up to 300s). Returns [] on
    failure; logs the error.
    """
    if not APIFY_API_KEY:
        raise RuntimeError("APIFY_API_KEY is not set (check erp-stack/.env)")

    # Apify REST uses '~' to separate owner/name (e.g. owner~actor-name),
    # and maxItems is a billed-item cap on the RUN (required > 0 for
    # pay-per-result actors). It is a query parameter, not Actor input.
    actor_ref = actor_id.replace("/", "~")
    url = f"{APIFY_API_BASE}/acts/{actor_ref}/run-sync-get-dataset-items"
    max_items = run_input.pop("maxItems", None)
    if max_items:
        url = f"{url}?maxItems={int(max_items)}"
    headers = {
        "Authorization": f"Bearer {APIFY_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=headers, json=run_input)
        if r.status_code >= 400:
            logger.error(
                f"Apify actor {actor_id} HTTP {r.status_code}: {r.text[:400]}"
            )
            return []
        try:
            data = r.json()
        except Exception as e:
            logger.error(f"Apify actor {actor_id} bad JSON: {e}")
            return []
        items = data if isinstance(data, list) else data.get("items", [])
        logger.info(f"Apify actor {actor_id} -> {len(items)} item(s)")
        return items


# ─── Field mapping (actor output -> _normalize_apify camelCase) ──────────────
def _num(v) -> float:
    try:
        s = str(v).replace("$", "").replace("฿", "").replace(",", "").strip()
        return float(s) if s else 0.0
    except Exception:
        return 0.0


def map_product_item(item: dict) -> dict:
    """Map cunning_soil product-scraper output (formatted_filtered / full_readable)
    to the camelCase keys ProductNormalizer._normalize_apify expects.
    """
    out: Dict[str, Any] = {}

    # product id
    pid = item.get("product_id") or item.get("productId") or ""
    if not pid:
        pi = item.get("product_info", {})
        prods = (pi or {}).get("products", []) or []
        if prods:
            pid = prods[0].get("product_id", "") or ""
    out["productId"] = pid

    # title
    out["title"] = item.get("title") or item.get("product_name") or ""

    # price
    price = item.get("price") or {}
    if isinstance(price, dict):
        # cunning_soil search returns price.sale_price / price.original_price
        out["minPrice"] = _num(price.get("sale_price") or price.get("min_price"))
        out["maxPrice"] = _num(price.get("original_price") or price.get("max_price"))
        out["price"] = _num(price.get("sale_price"))
        out["currency"] = price.get("currency", "THB")
    else:
        out["price"] = _num(price)
        out["currency"] = item.get("currency", "THB")

    # images: try images / image_urls / image (single) / primaryImage
    images = item.get("images") or item.get("image_urls") or []
    if isinstance(images, list) and images:
        out["images"] = [u for u in images if isinstance(u, str)]
    elif item.get("image"):
        out["images"] = [item["image"]]
    elif item.get("primaryImage"):
        out["primaryImage"] = item["primaryImage"]

    # stock / sales
    out["stock"] = item.get("stock", 0)
    out["soldCount"] = item.get("sales_count") or item.get("sold_count") or 0

    # seller
    store = item.get("store_info") or {}
    if store:
        out["shopName"] = store.get("name", "")
        out["sellerId"] = store.get("shop_id") or store.get("id") or ""
        out["rating"] = store.get("rating", 0)
    else:
        out["shopName"] = item.get("seller_name", "")
        out["sellerId"] = item.get("seller_id", "")

    # rating / reviews
    if "rating" not in out or not out["rating"]:
        out["rating"] = item.get("product_rating", item.get("rating", 0))
    out["reviewCount"] = item.get("review_count") or item.get("comment_count") or 0

    # commission not in actor output; leave 0
    out["commissionRate"] = item.get("commission_rate", 0)

    # description if present
    out["description"] = item.get("description", "")

    # keep original for debugging
    out["_source_item"] = item
    return out


def map_search_items(items: list) -> list:
    """Map keyword-search actor output to camelCase list.

    cunning_soil/tiktok-shop-product-search-api returns one dataset row per
    search with a `products` array. Flatten that array, then map each product.
    """
    flat: list = []
    for it in items:
        if not it:
            continue
        if isinstance(it, dict) and isinstance(it.get("products"), list):
            flat.extend(p for p in it["products"] if p)
        else:
            flat.append(it)
    return [map_product_item(p) for p in flat if p]


# ─── Main entry ──────────────────────────────────────────────────────────────
async def scrape_and_ingest(
    link: str = "",
    keyword: str = "",
    region: str = "",
    limit: int = 5,
) -> Dict[str, Any]:
    """Resolve input, scrape via Apify, map fields, run ingest_from_apify.

    Returns a summary dict with the first ingested product (or an error).
    """
    if not link and not keyword:
        return {"success": False, "error": "ต้องส่ง link หรือ keyword อย่างน้อยหนึ่งอย่าง"}

    region = region or guess_region(link, keyword)
    actors_used = []

    # 1) Resolve share/product link -> real PDP, then drive it through the
    #    search actor (the actor that runs on the free plan, per owner).
    pid = ""
    pdp_url = ""
    link_title = ""
    if link:
        pid, pdp_url, link_title = resolve_link(link)
        if not pid:
            # Could not extract an id from the link; fall back to searching the
            # link text itself as a keyword.
            keyword = keyword or link

    # 2) Keyword search — used for both direct keyword input and the resolved
    #    link (we search by the product title since the search actor is
    #    keyword-based and free-plan-compatible).
    if not keyword:
        # Prefer the PDP title (exact product) over the raw id, because the
        # search actor matches by text, not by numeric id.
        keyword = link_title or pid or keyword
    if not keyword:
        return {"success": False, "error": "ไม่สามารถระบุสินค้าได้จากข้อมูลที่ส่งมา (ไม่มี keyword หรือ product id)"}

    run_input = {
        "query": keyword,
        "region": region,
        "resultsLimit": limit,
        "outputMode": "formatted_filtered",
    }
    logger.info(f"Keyword search via Apify {ACTOR_SEARCH} (query={keyword}, region={region}, limit={limit})")
    items = await _call_actor(ACTOR_SEARCH, run_input)
    actors_used = [ACTOR_SEARCH]
    if not items:
        return {"success": False, "error": "Apify ไม่ได้ผลลัพธ์สำหรับ keyword นี้", "actors_used": actors_used}
    mapped = map_search_items(items)
    if not mapped:
        return {"success": False, "error": "Apify ให้ผลลัพธ์แต่ map product ไม่ได้", "actors_used": actors_used, "raw": items[0] if items else None}

    # If we had a resolved product id, try to pick the row that matches it;
    # otherwise take the top-ranked result.
    chosen = mapped[0]
    if pid:
        for m in mapped:
            if str(m.get("productId", "")) == str(pid):
                chosen = m
                break
    return await _run_pipeline(
        chosen, actors_used, link=link, keyword=keyword, candidates=len(mapped)
    )


async def _run_pipeline(
    mapped: dict, actors_used: list, link: str = "", keyword: str = "", candidates: int = 1
) -> Dict[str, Any]:
    """Feed one mapped product through ingest_from_apify."""
    product_id = mapped.get("productId", "")
    if not product_id:
        return {"success": False, "error": "Apify ไม่คืน product_id", "raw": mapped.get("_source_item"), "actors_used": actors_used}

    from product.pipeline_service import ingest_from_apify

    payload = dict(mapped)
    payload["source_site"] = "apify"
    payload["_actors_used"] = actors_used
    payload["_link"] = link
    payload["_keyword"] = keyword

    logger.info(f"Ingesting product {product_id} via ingest_from_apify")
    result = await ingest_from_apify(apify_data=payload, source="apify")

    summary = {
        "success": bool(result.success),
        "product_id": result.product_id or product_id,
        "actors_used": actors_used,
        "candidates": candidates,
        "steps": result.to_dict().get("steps", {}),
    }
    if not result.success:
        summary["error"] = "pipeline ingest ล้มเหลว ดู step ต่อ"
    return summary
