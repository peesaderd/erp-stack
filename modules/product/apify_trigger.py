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


def _clean_keyword(kw: str, max_len: int = 60) -> str:
    """Tidy a raw product title into a concise search keyword.

    cunning_soil search matches by text; long promotions / bracketed tags /
    percent-encoding make it return 0 results. Strip brackets and promo words,
    decode spaces, drop redundant promo tokens, and cap length.
    """
    kw = (kw or "").strip()
    if not kw:
        return ""
    # URL-encoded spaces
    try:
        if "%" in kw:
            import urllib.parse as _up
            kw = _up.unquote(kw)
    except Exception:
        pass
    kw = kw.replace("+", " ")
    # Drop bracketed promotion tags, e.g. [2 ชิ้น ลด 20% | 3 ชิ้น ลด 30%]
    import re as _re
    kw = _re.sub(r"\[[^\]]*\]", " ", kw)
    kw = _re.sub(r"\([^)]*(ลด|ชิ้น|%|off|OFF)\b[^)]*\)", " ", kw)
    # Drop standalone promo tokens
    promo = _re.compile(r"\b(ลด\s*\d+\s*%|\d+\s*%|ชิ้น|ชิ้นขึ้นไป|ลด|off|OFF|%)\b")
    kw = promo.sub(" ", kw)
    # Collapse whitespace
    kw = _re.sub(r"\s+", " ", kw).strip()
    # Cap length on a word boundary
    if len(kw) > max_len:
        cut = kw[:max_len]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        kw = cut.strip()
    return kw


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

    Owner 2026-09-09: ACTOR_PRODUCT returns {"product_info": {"products": [{...}]}}.
    Flatten the inner product up so title/price/images/seller map the same way
    as the search-actor flat rows. Specifications live deep at
    additional.raw_product.product_base.specifications — they become the
    description so imported rows are never desc-less.
    """
    _meta = item.get("product_info") or {}
    _prods = (_meta or {}).get("products") or []
    if _prods:
        _merged = dict(item)
        _merged.update({k: v for k, v in _prods[0].items() if v not in (None, "")})
        item = _merged
    # Deep-dive into ACTOR_PRODUCT's raw product for specs (desc source)
    _add = (item.get("additional") or {}).get("raw_product") or {}
    _pb = _add.get("product_base") or {}
    _specs = _pb.get("specifications") or []
    item.setdefault("specifications", _specs)
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

    # features (owner 2026-09-12 / plan B): the REAL product options/variants live in the
    # SKU list (inventory.skus[].sku_sale_props[].prop_value). For a multi-variant product
    # (different noodle types / flavours / sizes) these are the authoritative feature names
    # the script must mention - the PDP has no prose description. Build a clean comma list.
    try:
        _inv = item.get("inventory") or {}
        _skus = _inv.get("skus") or []
        _seen_feats: list = []
        for _s in _skus:
            if not isinstance(_s, dict):
                continue
            for _pr in (_s.get("sku_sale_props") or []):
                _v = (_pr or {}).get("prop_value", "")
                if isinstance(_v, str):
                    _v = _v.strip().strip('\u200b\ufe0f').strip()
                if _v and _v not in _seen_feats:
                    _seen_feats.append(_v)
        if _seen_feats:
            out["features"] = ", ".join(_seen_feats)
    except Exception:
        pass

    # price — handle both search-actor (price dict) and product-actor (pricing dict)
    price = item.get("price") or item.get("pricing") or {}
    if isinstance(price, dict):
        # cunning_soil search returns price.sale_price / price.original_price
        # cunning_soil product actor returns pricing.sale_price ("฿79.00") / original_price / raw.min_sku_price
        sale = price.get("sale_price") or price.get("min_price") or ""
        orig = price.get("original_price") or price.get("max_price") or ""
        raw_p = price.get("raw") or {}
        if not sale:
            sale = raw_p.get("real_price") or raw_p.get("min_sku_price") or ""
        out["minPrice"] = _num(sale)
        out["maxPrice"] = _num(orig or sale)
        out["price"] = _num(sale)
        out["currency"] = price.get("currency", item.get("currency", "THB"))
    else:
        out["price"] = _num(price)
        out["currency"] = item.get("currency", "THB")

    # images: try images / image_urls / image (single) / primaryImage / media.images|image_urls
    images = item.get("images") or item.get("image_urls") or []
    media = item.get("media") or {}
    if not images and isinstance(media, dict):
        # media.image_urls = list[str] (preferred); media.images = list[dict] (thumb_url_list)
        images = media.get("image_urls") or media.get("images") or []
    url_list: list = []
    if isinstance(images, list):
        for u in images:
            if isinstance(u, str):
                url_list.append(u)
            elif isinstance(u, dict):
                # media.images entries carry thumb_url_list / url
                tl = u.get("thumb_url_list") or u.get("url") or []
                if isinstance(tl, list):
                    url_list.extend(x for x in tl if isinstance(x, str))
                elif isinstance(tl, str):
                    url_list.append(tl)
    if url_list:
        out["images"] = url_list
    elif item.get("image"):
        out["images"] = [item["image"]]
    elif item.get("primaryImage"):
        out["primaryImage"] = item["primaryImage"]

    # description — search actor may not include it; ACTOR_PRODUCT has none
    # (only specs). Use specifications as a light desc fallback so enrich
    # (B1 _gen_thai_description) has some input.
    if not out.get("description"):
        specs = item.get("specifications") or (item.get("product_base") or {}).get("specifications") or []
        if isinstance(specs, list) and specs:
            parts = []
            for s in specs:
                if isinstance(s, dict):
                    name = s.get("name") or ""
                    val = s.get("value") or ""
                    if name and val:
                        parts.append(f"{name}: {val}")
                elif isinstance(s, str):
                    parts.append(s)
            if parts:
                out["description"] = " ".join(parts)[:400]
    # Final guard: never ship a desc-less row — fall back to the title so every
    # imported product has a non-empty description (owner 2026-09-09).
    if not out.get("description") and out.get("title"):
        out["description"] = out["title"]

    # stock / sales
    inv = item.get("inventory") or {}
    out["stock"] = item.get("stock", 0) or (inv.get("total_quantity") if isinstance(inv, dict) else 0) or 0
    sales = item.get("sales") or {}
    out["soldCount"] = (item.get("sales_count") or item.get("sold_count") or 0) or (sales.get("sold_count") if isinstance(sales, dict) else 0) or 0

    # seller — search actor: store_info; product actor: seller
    store = item.get("store_info") or item.get("seller") or {}
    if isinstance(store, dict) and store:
        out["shopName"] = store.get("name", "")
        out["sellerId"] = store.get("shop_id") or store.get("id") or store.get("seller_id") or ""
        out["rating"] = store.get("rating", 0)
    else:
        out["shopName"] = item.get("seller_name", "")
        out["sellerId"] = item.get("seller_id", "")

    # rating / reviews
    if not out.get("rating"):
        out["rating"] = item.get("product_rating", item.get("rating", 0))
    reviews = item.get("reviews") or {}
    out["reviewCount"] = (item.get("review_count") or item.get("comment_count") or 0) or (reviews.get("review_count") if isinstance(reviews, dict) else 0) or 0

    # commission not in actor output; leave 0
    out["commissionRate"] = item.get("commission_rate", 0)

    # description if present — merge only when the raw item really has one
    # (ACTOR_PRODUCT has no top-level description; specs-built desc must survive)
    _raw_desc = item.get("description") or item.get("product_name") or ""
    if _raw_desc and not out.get("description"):
        out["description"] = _raw_desc

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
    #    product actor (ACTOR_PRODUCT) so we fetch THAT EXACT product.
    #    Owner 2026-09-09: search actor returns look-alike products ("คนละตัว").
    pid = ""
    pdp_url = ""
    link_title = ""
    if link:
        pid, pdp_url, link_title = resolve_link(link)
        if not pid:
            # Could not extract an id from the link; fall back to searching the
            # link text itself as a keyword.
            keyword = keyword or link

    # 1b) Exact-product path: PDP/VT link resolves to an id -> scrape it directly.
    #     productInput + region are both required (no region => products empty).
    if pid:
        try:
            direct, direct_actor = await _scrape_product_direct(pid, pdp_url, region)
        except Exception as e:
            logger.warning(f"direct product scrape failed ({e}) — falling back to keyword search")
            direct, direct_actor = None, ""
        if direct:
            return await _run_pipeline(
                direct, [direct_actor], link=link, keyword=pid, candidates=1
            )
        logger.warning("direct product scrape returned nothing — falling back to keyword search")

    # 2) Keyword search — used for both direct keyword input and the resolved
    #    link (we search by the product title since the search actor is
    #    keyword-based and free-plan-compatible).
    if not keyword:
        # Prefer the PDP title (exact product) over the raw id, because the
        # search actor matches by text, not by numeric id.
        keyword = link_title or pid or keyword
    if not keyword:
        return {"success": False, "error": "ไม่สามารถระบุสินค้าได้จากข้อมูลที่ส่งมา (ไม่มี keyword หรือ product id)"}

    # Tidy the keyword: long promo-laden titles make the search actor return 0.
    search_kw = _clean_keyword(keyword)
    if not search_kw:
        search_kw = keyword  # fallback to the raw keyword if we stripped everything

    run_input = {
        "query": search_kw,
        "region": region,
        "resultsLimit": limit,
        "outputMode": "formatted_filtered",
    }
    logger.info(f"Keyword search via Apify {ACTOR_SEARCH} (query={search_kw}, region={region}, limit={limit})")
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


async def _scrape_product_direct(pid: str, pdp_url: str, region: str):
    """Fetch one exact TikTok Shop product via ACTOR_PRODUCT (mobile-api).

    Returns (mapped_product_dict_or_None, actor_id). productInput accepts the
    PDP URL or a bare id; region must be set or products come back empty.
    """
    if not pdp_url:
        pdp_url = f"https://shop.tiktok.com/view/product/{pid}"
    run_input = {"productInput": pdp_url, "region": region or "TH"}
    logger.info(f"Exact product scrape via {ACTOR_PRODUCT} (pid={pid}, region={region or 'TH'})")
    items = await _call_actor(ACTOR_PRODUCT, run_input, timeout=120)
    if not items:
        logger.warning(f"_scrape_product_direct: actor returned no items for {pid}")
        return None, ACTOR_PRODUCT
    mapped = map_search_items(items)  # flattens product_info.products + maps
    chosen = None
    for m in mapped:
        if str(m.get("productId", "")) == str(pid):
            chosen = m
            break
    if chosen is None and mapped:
        chosen = mapped[0]
    if chosen is None:
        logger.warning(f"_scrape_product_direct: no mapped product for {pid}")
    return chosen, ACTOR_PRODUCT


async def _run_pipeline(
    mapped: dict, actors_used: list, link: str = "", keyword: str = "", candidates: int = 1
) -> Dict[str, Any]:
    """Feed one mapped product through ingest_from_apify."""
    product_id = mapped.get("productId", "")
    if not product_id:
        logger.error(
            f"Apify ไม่คืน product_id: raw_source={mapped.get('_source_item')!r} mapped_keys={list(mapped.keys())}"
        )
        return {"success": False, "error": "Apify ไม่คืน product_id", "raw": mapped.get("_source_item"), "mapped": mapped, "actors_used": actors_used}

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
        "duplicate": result.duplicate,
        "sync_action": result.sync_action,
        "steps": result.to_dict().get("steps", {}),
    }
    if not result.success:
        summary["error"] = "pipeline ingest ล้มเหลว ดู step ต่อ"
    return summary
