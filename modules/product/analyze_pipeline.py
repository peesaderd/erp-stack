"""Product Analysis Pipeline — Normalizer → Enricher → Exporter
Transforms raw scraped data (TikTok Shop, Shopee, Lazada) into TUS-ready analyzed data.
"""
import os, json, logging, httpx, asyncio, re, time, uuid
from typing import Optional, Dict, List, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict
from collections import Counter
import os, sys
from pathlib import Path

# Load .env from erp-stack root (PM2 doesn't inject env vars)
_erp_root = str(Path(__file__).resolve().parents[2])
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_erp_root, '.env'))
except ImportError:
    # Manual .env loader if dotenv not installed
    _env_path = os.path.join(_erp_root, '.env')
    if os.path.exists(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    os.environ.setdefault(_k.strip(), _v.strip())

_modules_root = str(Path(__file__).resolve().parents[1])
if _modules_root not in sys.path:
    sys.path.insert(0, _modules_root)
from product.analyzer_db import store_analyzed as _store_analyzed, get_analyzed_stats as _get_stats, get_analyzed_products as _get_products
from product.analyzer_db import store_analyzed_batch

logger = logging.getLogger("analyze_pipeline")

MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "")

# Mistral key rotation — use the new MistralKeyRotator
from product.mistral_rotator import get_rotator as _get_mistral_rotator, MistralKeyRotator
_mistral_keys = []  # kept for backward compat with code that checks len()


def _load_mistral_keys():
    """Initialize rotator from env keys (called once)."""
    global _mistral_keys
    try:
        rotator = _get_mistral_rotator()
        _mistral_keys = [s.key for s in rotator._slots]
    except Exception as e:
        logger.warning(f"Could not init MistralKeyRotator: {e}")

# ─── Local Image Storage ───────────────────────────────────
# Images are downloaded to Analysis module static dir
# This is the source of truth — TUS reads from here
PRODUCT_IMAGE_DIR = Path("/home/openhands/erp-stack/tiktok-ugc-studio/storage/product_images")
PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# Proxy for hdnet.workers.dev download
DATAIMPULSE_PROXY = os.environ.get("DATAIMPULSE_PROXY", "")
PROXY_DICT = {"http": DATAIMPULSE_PROXY, "https": DATAIMPULSE_PROXY} if DATAIMPULSE_PROXY else None


async def _download_images_local(product_id: str, image_urls: list) -> list:
    """Download ALL product images to local storage.
    
    Downloads every URL we can reach (no limit). Returns list of dicts with:
      {"url": str, "local_path": str, "filename": str, "size": int}
    Falls back to keeping the original URL if download fails.
    """
    if not image_urls:
        return []
    
    local_images = []
    for url in image_urls:
        if not url:
            continue
        # Already local
        if url.startswith("/static/") or "localhost" in url:
            fname = url.rsplit("/", 1)[-1] if "/" in url else url
            local_images.append({
                "url": url,
                "local_path": str(PRODUCT_IMAGE_DIR / fname),
                "filename": fname,
                "size": (PRODUCT_IMAGE_DIR / fname).stat().st_size if (PRODUCT_IMAGE_DIR / fname).exists() else 0,
            })
            continue
        
        ext = url.rsplit(".", 1)[-1].split("?")[0] if "." in url else "jpg"
        local_name = f"{product_id}_{uuid.uuid4().hex[:4]}.{ext}"
        local_path = PRODUCT_IMAGE_DIR / local_name
        
        try:
            async with httpx.AsyncClient(
                proxy=PROXY_DICT.get('http') or PROXY_DICT.get('https') if PROXY_DICT else None,
                timeout=20,
                verify=False
            ) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    follow_redirects=True,
                )
                if resp.status_code == 200 and len(resp.content) > 1000:
                    local_path.write_bytes(resp.content)
                    local_images.append({
                        "url": f"/static/product_images/{local_name}",
                        "local_path": str(local_path),
                        "filename": local_name,
                        "size": len(resp.content),
                    })
                    logger.info(f"  Downloaded image: {local_name} ({len(resp.content)} bytes)")
                else:
                    local_images.append({
                        "url": url,
                        "local_path": "",
                        "filename": local_name,
                        "size": 0,
                    })
                    logger.warning(f"  Download failed {url[:50]}: HTTP {resp.status_code}")
        except Exception as e:
            local_images.append({
                "url": url,
                "local_path": "",
                "filename": local_name,
                "size": 0,
            })
            logger.warning(f"  Download error {url[:50]}: {e}")
    
    return local_images


async def _analyze_and_select_images(product_id: str, raw_images: list) -> tuple:
    """Use Mistral Pixtral to analyze each product image and select the best ones.
    
    For each image, it asks Mistral to describe what's in the image and rate its quality.
    Images that fail analysis (no product visible, blurry, text-only) get lower scores.
    
    Returns: (selected_urls, all_analyses)
      - selected_urls: list of URLs for the best 3-5 images
      - all_analyses: list of dicts with per-image analysis results
    """
    if not raw_images:
        return [], []
    
    mistral_key = os.environ.get("MISTRAL_API_KEY", "")
    if not mistral_key:
        # No Mistral — use quality gate alone (no vision analysis)
        try:
            from product.sam3_quality_gate import batch_check as _quality_gate
            quality_results = _quality_gate(raw_images)
            keep = [i for i in quality_results if i.get("quality_recommended", True)]
            logger.info(f"  Quality gate (no Mistral): {len(keep)}/{len(quality_results)} images passed")
            return [img["url"] for img in keep], []
        except ImportError:
            pass
        return [img["url"] for img in raw_images], []
    
    # ─── SAM3 Quality Gate (Rule-based pre-filter) ───────────────
    # Runs OpenCV analysis on downloaded images BEFORE Mistral vision API
    # Filters out: blurry, too small, low contrast, text-only, corrupted
    # Cost: $0 (FREE) — saves Mistral API calls on bad images
    try:
        from product.sam3_quality_gate import batch_check as _quality_gate
        quality_results = _quality_gate(raw_images)
        # Log quality scores
        for qr in quality_results:
            score = qr.get("quality_score", 50)
            rec = qr.get("quality_recommended", True)
            fname = qr.get("filename", "?")
            logger.info(f"  Quality gate [{fname}]: score={score}/100, recommended={rec}")
        # Separate into keep/reject lists
        keep = [i for i in quality_results if i.get("quality_recommended", True)]
        rejected = [i for i in quality_results if not i.get("quality_recommended", True)]
        logger.info(f"  Quality gate: {len(keep)}/{len(quality_results)} images passed, {len(rejected)} rejected")
        raw_images = keep + rejected[:1]  # Keep 1 borderline image for Mistral to double-check
    except ImportError:
        logger.warning("  SAM3 quality gate not available — skipping")
    except Exception as _qe:
        logger.warning(f"  Quality gate error (non-fatal): {_qe}")
    
    analyses = []
    for img in raw_images:
        url = img["url"]
        if not url.startswith("http"):
            url = f"http://localhost:8105{img['url']}" if img['url'].startswith("/") else img['url']
        
        prompt = (
            "Analyze this product image for a TikTok shop review video. "
            "Return JSON only with these fields:\n"
            '{"subjects": ["list of objects visible"], '
            '"quality": <1-10>, '
            '"has_product": <true/false>, '
            '"background": "clean/messy/solid", '
            '"text_on_image": <true/false>, '
            '"recommended": <true/false>}\n'
            "recommended=true if the product is clearly visible, "
            "good lighting, and suitable for video background. "
            "recommended=false if blurry, no product, or just text/logo."
        )
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                payload = {
                    "model": "pixtral-large-2501",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": url}
                        ]
                    }],
                    "temperature": 0.1,
                    "max_tokens": 300,
                }
                resp = await client.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {mistral_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code == 200:
                    text = resp.json()["choices"][0]["message"]["content"]
                    # Extract JSON
                    import re as _re
                    start = text.find("{")
                    end = text.rfind("}")
                    if start >= 0 and end > start:
                        analysis = json.loads(text[start:end+1])
                    else:
                        analysis = {"quality": 5, "has_product": True, "recommended": True}
                else:
                    analysis = {"quality": 5, "has_product": True, "recommended": True}
                    logger.warning(f"Mistral vision error for {img['filename']}: {resp.status_code}")
        except Exception as e:
            analysis = {"quality": 5, "has_product": True, "recommended": True}
            logger.warning(f"Mistral vision exception for {img['filename']}: {e}")
        
        analysis["_filename"] = img["filename"]
        analysis["_url"] = img["url"]
        analysis["_size"] = img["size"]
        analyses.append(analysis)
        logger.info(f"  Image {img['filename']}: recommended={analysis.get('recommended')}, quality={analysis.get('quality')}, subjects={analysis.get('subjects', [])[:3]}")
    
    # Score: recommended > has_product > quality > size
    def _score(a):
        s = 0
        if a.get("recommended"): s += 50
        if a.get("has_product"): s += 30
        s += (a.get("quality", 5) / 10) * 15
        if a.get("_size", 0) > 50000: s += 5
        if a.get("text_on_image"): s -= 10
        if a.get("background") == "messy": s -= 5
        return s
    
    analyses.sort(key=_score, reverse=True)
    
    # Pick top 5 images that are recommended or score well
    recommended = [a for a in analyses if a.get("recommended")]
    fallback = [a for a in analyses if not a.get("recommended") and a.get("has_product")]
    
    selected = (recommended + fallback)[:5]
    selected_urls = [a["_url"] for a in selected]
    
    if not selected_urls and analyses:
        # Last resort — keep best quality ones
        selected_urls = [a["_url"] for a in analyses[:3]]
    
    logger.info(f"  Selected {len(selected_urls)} best images for product {product_id}")
    return selected_urls, analyses


# ─── Error Rate Limiter ─────────────────────────────────────────────────────

class ErrorRateLimiter:
    """Rate-limit API calls with exponential backoff."""
    def __init__(self, max_calls: int = 10, period: float = 60.0, backoff_factor: float = 2.0):
        self.max_calls = max_calls
        self.period = period
        self.backoff_factor = backoff_factor
        self._call_times: List[float] = []
        self._error_count: int = 0
        self._backoff_until: float = 0.0

    def _prune(self):
        now = time.time()
        cutoff = now - self.period
        self._call_times = [t for t in self._call_times if t > cutoff]

    def can_call(self) -> bool:
        now = time.time()
        if now < self._backoff_until:
            return False
        self._prune()
        return len(self._call_times) < self.max_calls

    async def wait_if_needed(self):
        now = time.time()
        if now < self._backoff_until:
            wait = self._backoff_until - now
            logger.info(f"Rate limited — waiting {wait:.1f}s")
            await asyncio.sleep(wait)
        self._prune()
        while len(self._call_times) >= self.max_calls:
            await asyncio.sleep(1.0)
            self._prune()

    def record_call(self):
        self._call_times.append(time.time())

    def record_error(self):
        self._error_count += 1
        backoff_seconds = min(60, 1.0 * (self.backoff_factor ** (self._error_count - 1)))
        self._backoff_until = time.time() + backoff_seconds
        logger.warning(f"Rate limiter backoff: {backoff_seconds}s (error #{self._error_count})")

    def record_success(self):
        self._error_count = 0

_rate_limiter = ErrorRateLimiter()

# ─── In-Memory Cache (TTL 5 min) ─────────────────────────────────────────────

class TTLCache:
    """Simple in-memory cache with TTL."""
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, tuple] = {}
        self._ttl = ttl_seconds

    def get(self, key: str):
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value):
        self._cache[key] = (value, time.time() + self._ttl)

    def clear(self):
        self._cache.clear()

    def cleanup(self):
        now = time.time()
        stale = [k for k, (_, exp) in self._cache.items() if now >= exp]
        for k in stale:
            del self._cache[k]

_cache = TTLCache()

# ─── Unified Data Model ──────────────────────────────────────────────────────

@dataclass
class UnifiedProduct:
    product_id: str = ""
    title: str = ""
    title_th: str = ""
    description: str = ""
    price_min: float = 0.0
    price_max: float = 0.0
    price_avg: float = 0.0
    currency: str = "THB"
    rating: float = 0.0
    review_count: int = 0
    sold_total: int = 0
    sold_week: int = 0
    sold_month: int = 0
    sales_gmv_7d: float = 0.0
    sales_gmv_30d: float = 0.0
    sales_gmv_total: float = 0.0
    sales_gmv_7d_usd: float = 0.0
    sales_gmv_30d_usd: float = 0.0
    sales_gmv_total_usd: float = 0.0
    seller_name: str = ""
    seller_id: str = ""
    categories: List[str] = field(default_factory=list)
    category: str = ""
    images: List[str] = field(default_factory=list)
    commission_rate: float = 0.0
    influencer_count: int = 0
    video_count: int = 0
    rank: int = 0
    source: str = ""
    url: str = ""
    scrape_timestamp: str = ""
    viral_score: float = 0.0
    trending: bool = False
    keywords: List[str] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    gender: str = ""
    target_age: str = ""
    enriched: bool = False

# ─── Stage 1: Normalizer ─────────────────────────────────────────────────────

class ProductNormalizer:
    SOURCE_PATTERNS = {
        "tiktok": ["total_sale_cnt", "product_id", "total_sale_gmv_amt", "cover_url", "product_name", "product_rating"],
        "apify": ["sold_count", "title", "total_sales", "seller_name", "commission_rate", "week_sales", "week_sold_count"],
        "shopee": ["itemid", "shopid", "cmtid", "historical_sold", "shopee_verified"],
        "lazada": ["item_id", "shop_id", "lazada_sku", "lzd_sku", "seller_sku"],
    }

    @staticmethod
    def detect_source(raw_data: dict) -> str:
        """Auto-detect data source from field names"""
        for src, fields in ProductNormalizer.SOURCE_PATTERNS.items():
            if any(f in raw_data for f in fields):
                return src
        return "generic"

    @staticmethod
    def _safe_float(val, default=0.0) -> float:
        try: return float(val) if val else default
        except: return default

    @staticmethod
    def _safe_int(val, default=0) -> int:
        try: return int(val) if val else default
        except: return default

    @staticmethod
    def _parse_price_str(price_str: str) -> float:
        """Parse '฿12.52' or '$0.38' to float"""
        if not price_str: return 0.0
        cleaned = re.sub(r'[^\d.]', '', price_str)
        try: return float(cleaned)
        except: return 0.0

    @classmethod
    async def normalize(cls, raw_data: dict, source_hint: str = "") -> UnifiedProduct:
        # source_hint wins. If empty, try auto-detect from raw_data fields.
        auto = cls.detect_source(raw_data)
        source = source_hint or auto
        if source == "tiktok":
            return cls._normalize_tiktok(raw_data)
        elif source == "apify":
            return cls._normalize_apify(raw_data)
        elif source == "shopee":
            return cls._normalize_shopee(raw_data)
        elif source == "lazada":
            return cls._normalize_lazada(raw_data)
        elif source == "facebook":
            return cls._normalize_generic(raw_data)
        elif source == "generic":
            return cls._normalize_generic(raw_data)
        elif auto == "tiktok":
            return cls._normalize_tiktok(raw_data)
        elif auto == "apify":
            return cls._normalize_apify(raw_data)
        elif auto == "shopee":
            return cls._normalize_shopee(raw_data)
        elif auto == "lazada":
            return cls._normalize_lazada(raw_data)
        else:
            return cls._normalize_generic(raw_data)

    @classmethod
    def _normalize_tiktok(cls, d: dict) -> UnifiedProduct:
        seller = d.get("seller", {}) or {}
        return UnifiedProduct(
            product_id=str(d.get("product_id", d.get("id", ""))),
            title=d.get("product_title", d.get("product_name", d.get("title", ""))),
            description=d.get("rich_text", d.get("short_description", d.get("product_name", d.get("description", "")))),
            price_min=cls._safe_float(d.get("min_price", 0)),
            price_max=cls._safe_float(d.get("max_price", 0)),
            price_avg=cls._safe_float(d.get("avg_price", d.get("real_price", d.get("price", 0)))),
            currency="THB",
            rating=cls._safe_float(d.get("product_rating", d.get("rating", 0))),
            review_count=cls._safe_int(d.get("review_count", 0)),
            sold_total=cls._safe_int(d.get("total_sale_cnt", d.get("sold_count", d.get("total_sales", 0)))),
            sold_week=cls._safe_int(d.get("total_sale_7d_cnt", d.get("week_sales", d.get("week_sold_count", 0)))),
            sold_month=cls._safe_int(d.get("total_sale_30d_cnt", 0)),
            sales_gmv_7d=cls._parse_price_str(d.get("total_sale_gmv_7d_amt", "0")),
            sales_gmv_30d=cls._parse_price_str(d.get("total_sale_gmv_30d_amt", "0")),
            sales_gmv_total=cls._parse_price_str(d.get("total_sale_gmv_amt", "0")),
            seller_name=seller.get("seller_name", d.get("seller_name", "")),
            seller_id=str(seller.get("seller_id", d.get("seller_id", ""))),
            categories=[c.strip() for c in d.get("categories", "").split("/") if c.strip()],
            images=d.get("images", []) or ([d.get("cover_url", "")] if d.get("cover_url") else []),
            commission_rate=cls._safe_float(d.get("commission_rate", d.get("commission", "0")).replace("%", "")),
            influencer_count=cls._safe_int(d.get("influencers_count", d.get("total_ifl_cnt", 0))),
            video_count=cls._safe_int(d.get("videos_count", d.get("total_video_count", 0))),
            rank=cls._safe_int(d.get("rank", 0)),
            source="tiktok",
            gender=str(d.get("gender", "") or ""),
            target_age=str(d.get("age_group", d.get("target_age", "")) or ""),
            scrape_timestamp=datetime.utcnow().isoformat(),
        )

    @classmethod
    def _normalize_apify(cls, d: dict) -> UnifiedProduct:
        # Apify uses camelCase: productId, soldCount, shopName, etc.
        return UnifiedProduct(
            product_id=str(d.get("productId", d.get("id", d.get("product_id", "")))),
            title=d.get("title", d.get("product_name", "")),
            description=d.get("description", d.get("product_name", "")),
            price_min=cls._safe_float(d.get("minPrice", d.get("min_price", d.get("price", 0)))),
            price_max=cls._safe_float(d.get("maxPrice", d.get("max_price", d.get("price", 0)))),
            price_avg=cls._safe_float(d.get("price", d.get("avg_price", 0))),
            currency=d.get("currency", d.get("currencySymbol", "USD")).replace("฿","THB"),
            rating=cls._safe_float(d.get("rating", d.get("product_rating", 0))),
            review_count=cls._safe_int(d.get("reviewCount", d.get("review_count", 0))),
            sold_total=cls._safe_int(d.get("soldCount", d.get("sold_count", d.get("total_sales", d.get("total_sold", 0))))),
            sold_week=cls._safe_int(d.get("weekSoldCount", d.get("week_sold_count", d.get("week_sales", 0)))),
            categories=(d.get("categories", d.get("sourceQuery", "")) or "").split("|") if isinstance(d.get("categories", d.get("sourceQuery", "")), str) else (d.get("categories") or [d.get("sourceQuery", "")]),
            images=d.get("images", [d.get("primaryImage", "")]) if d.get("images") else [d.get("primaryImage", "")] if d.get("primaryImage") else [],
            commission_rate=cls._safe_float(str(d.get("commissionRate", d.get("commission_rate", "0"))).replace("%", "")),
            seller_name=d.get("shopName", d.get("seller_name", d.get("shop_name", ""))),
            source="apify",
            scrape_timestamp=datetime.utcnow().isoformat(),
        )

    @classmethod
    def _normalize_shopee(cls, d: dict) -> UnifiedProduct:
        return UnifiedProduct(
            product_id=str(d.get("itemid", d.get("id", ""))),
            title=d.get("title", d.get("name", "")),
            description=d.get("description", ""),
            price_min=cls._safe_float(d.get("price_min", d.get("price", 0))),
            price_max=cls._safe_float(d.get("price_max", d.get("price", 0))),
            price_avg=cls._safe_float(d.get("price", d.get("avg_price", 0))),
            currency="THB",
            rating=cls._safe_float(d.get("item_rating", d.get("rating", d.get("product_rating", 0)))),
            review_count=cls._safe_int(d.get("cmt_count", d.get("review_count", 0))),
            sold_total=cls._safe_int(d.get("historical_sold", d.get("sold_count", d.get("total_sales", 0)))),
            sold_week=cls._safe_int(d.get("week_sold_count", d.get("week_sales", 0))),
            seller_name=d.get("shop_location", d.get("seller_name", "")),
            categories=[],
            images=d.get("images", [])[:8] if isinstance(d.get("images"), list) else [],
            commission_rate=cls._safe_float(d.get("commission_rate", "0").replace("%", "")),
            source="shopee",
            scrape_timestamp=datetime.utcnow().isoformat(),
        )

    @classmethod
    def _normalize_lazada(cls, d: dict) -> UnifiedProduct:
        return UnifiedProduct(
            product_id=str(d.get("item_id", d.get("id", ""))),
            title=d.get("title", d.get("name", "")),
            description=d.get("description", ""),
            price_min=cls._safe_float(d.get("price_min", d.get("price", 0))),
            price_max=cls._safe_float(d.get("price_max", d.get("price", 0))),
            price_avg=cls._safe_float(d.get("price", d.get("avg_price", 0))),
            currency="THB",
            rating=cls._safe_float(d.get("item_rating", d.get("rating", d.get("product_rating", 0)))),
            review_count=cls._safe_int(d.get("review_count", 0)),
            sold_total=cls._safe_int(d.get("sold_count", d.get("total_sales", d.get("historical_sold", 0)))),
            sold_week=cls._safe_int(d.get("week_sold_count", d.get("week_sales", 0))),
            seller_name=d.get("seller_name", ""),
            categories=[],
            images=d.get("images", [])[:8] if isinstance(d.get("images"), list) else [],
            commission_rate=cls._safe_float(d.get("commission_rate", "0").replace("%", "")),
            source="lazada",
            scrape_timestamp=datetime.utcnow().isoformat(),
        )

    @classmethod
    def _normalize_generic(cls, d: dict) -> UnifiedProduct:
        return UnifiedProduct(
            product_id=str(d.get("id", "")),
            title=d.get("title", d.get("name", "")),
            description=d.get("description", ""),
            price_avg=cls._safe_float(d.get("price", 0)),
            rating=cls._safe_float(d.get("rating", 0)),
            source="generic",
            scrape_timestamp=datetime.utcnow().isoformat(),
        )

# ─── Stage 2: Enricher ───────────────────────────────────────────────────────

CATEGORY_MAP = {
    "beauty": "ความงาม", "fashion": "แฟชั่น", "electronics": "อิเล็กทรอนิกส์",
    "home": "บ้าน", "food": "อาหาร", "sports": "กีฬา", "pets": "สัตว์เลี้ยง",
    "health": "สุขภาพ", "kids": "เด็ก", "accessories": "เครื่องประดับ",
}

class ProductEnricher:
    @staticmethod
    async def enrich(product: UnifiedProduct) -> UnifiedProduct:
        try:
            product.category = await _detect_category(product.title, product.categories)
            product.title_th = await _translate_to_thai(product.title)
            product.keywords = await _extract_keywords(product.title, product.description)
            meta = await _extract_gender_age_hashtags(product.title, product.description, product.category)
            if not product.gender:
                product.gender = meta.get("gender", "")
            if not product.target_age:
                product.target_age = meta.get("target_age", "")
            product.hashtags = meta.get("hashtags", [])
            product.viral_score = _score_viral(product)
            if product.sold_total > 0:
                product.trending = (product.sold_week / product.sold_total) > 0.1
            
            # 1. Download ALL product images to local storage (no limit)
            raw_images = await _download_images_local(product.product_id, product.images)
            
            # 2. Keep all raw image data for reference
            all_photo_urls = [img["url"] for img in raw_images]
            
            # 3. Use Mistral Vision to analyze and select the best images
            selected_urls, image_analyses = await _analyze_and_select_images(
                product.product_id, raw_images
            )
            
            # 4. Store both: all_downloaded + selected
            product.images = selected_urls if selected_urls else all_photo_urls
            
            product.enriched = True
            return product
        except Exception as e:
            logger.error(f"Enrichment failed: {e}")
            product.enriched = False
            return product

# ─── Stage 3: Exporter ───────────────────────────────────────────────────────

class ProductExporter:
    @staticmethod
    def export_for_tus(products: List[UnifiedProduct], filters: dict = None) -> dict:
        filters = filters or {}
        result = []
        for p in products:
            if filters.get("min_rating") and p.rating < filters["min_rating"]: continue
            if filters.get("min_sold") and p.sold_total < filters["min_sold"]: continue
            if filters.get("commission") and p.commission_rate < filters["commission"]: continue
            if filters.get("category") and p.category != filters["category"]: continue
            result.append({
                "product_id": p.product_id, "title": p.title, "title_th": p.title_th,
                "price_thb": p.price_avg, "rating": p.rating, "sold_total": p.sold_total,
                "viral_score": p.viral_score, "trending": p.trending,
                "category": p.category, "keywords": p.keywords,
                "images": p.images, "commission": f"{p.commission_rate}%",
                "source": p.source, "seller_name": p.seller_name,
                "gender": p.gender, "target_age": p.target_age,
                "hashtags": p.hashtags,
                "image_count": len(p.images),
            })
        return {"tus_ready": True, "products": result, "count": len(result),
                "timestamp": datetime.utcnow().isoformat()}

# ─── Helper Functions ────────────────────────────────────────────────────────

async def _call_mistral(prompt: str, max_tokens: int = 500) -> str:
    """Call Mistral API via MistralKeyRotator with per-key cooldown.
    
    Key rotation features:
    - Per-key cooldown tracking (60s default, respects Retry-After headers)
    - Rotates to next available key on 429/401 (no sleep between retries)
    - When all keys exhausted: waits for earliest cooldown, retries with backoff
    - Concurrent-safe with asyncio.Lock
    """
    if not _mistral_keys:
        _load_mistral_keys()
    try:
        rotator = _get_mistral_rotator()
        return await rotator.call(prompt, max_tokens=max_tokens)
    except Exception as e:
        logger.error(f"MistralKeyRotator failed: {e}")
        return ""

async def _detect_category(title: str, categories: list) -> str:
    if categories and categories[0]:
        for en, th in CATEGORY_MAP.items():
            if en in categories[0].lower() or th in categories[0]:
                return th
    for en, th in CATEGORY_MAP.items():
        if en in title.lower():
            return th
    return categories[0] if categories else "อื่นๆ"

async def _translate_to_thai(text: str) -> str:
    if not text: return ""
    cache_key = f"trans_{text[:100]}"
    cached = _cache.get(cache_key)
    if cached:
        return cached
    prompt = f"Translate this product title to Thai naturally (keep brand names):\n\n{text}"
    result = await _call_mistral(prompt)
    if not result:
        result = text
    _cache.set(cache_key, result)
    return result

async def _extract_keywords(title: str, description: str) -> list:
    if not title: return []
    cache_key = f"kw_{title[:100]}"
    cached = _cache.get(cache_key)
    if cached:
        return cached
    prompt = f"Extract 5-10 Thai keywords for TikTok caption from:\nTitle: {title}\nDesc: {description}\nReturn JSON array only."
    result = await _call_mistral(prompt, max_tokens=200)
    if result:
        try:
            keywords = json.loads(result)
            _cache.set(cache_key, keywords)
            return keywords
        except:
            import re; words = re.findall(r'"([^"]+)"', result)
            keywords = words[:10] if words else []
            _cache.set(cache_key, keywords)
            return keywords
    return []

def _split_hashtags(raw) -> list:
    if isinstance(raw, list):
        out = []
        for h in raw:
            if isinstance(h, dict):
                h = h.get("tag") or h.get("hashtag") or ""
            out.append(str(h).strip().lstrip("#"))
        return [x for x in out if x][:12]
    if isinstance(raw, str):
        return [x.strip().lstrip("#") for x in re.split(r"[,\s]+", raw) if x.strip()][:12]
    return []


async def _extract_gender_age_hashtags(title: str, description: str, category: str = "") -> dict:
    """Use Mistral to determine gender, target age group, and hashtags."""
    out = {"gender": "", "target_age": "", "hashtags": []}
    if not title:
        return out
    prompt = (
        "Analyze this product's PRIMARY buyer/user for TikTok video content.\n"
        "Return ONLY valid JSON:\n"
        '{"gender": "ผู้หญิง|ผู้ชาย|ทุกเพศ", '
        '"target_age": "short age range e.g. 18-35", '
        '"hashtags": [5-8 Thai+English TikTok hashtags]}\n'
        "Gender rules (make a definitive choice):\n"
        "- Lipstick, skincare, beauty, makeup, serum, cream, concealer → ผู้หญิง\n"
        "- Diapers, baby products, kids items → ผู้หญิง (mother is buyer)\n"
        "- Shaver, razor, men's accessories → ผู้ชาย\n"
        "- Vitamins, cleaning supplies, food, electronics, tools → ทุกเพศ\n"
        "Only return ทุกเพศ for truly universal products. Do NOT overthink.\n"
        f"Title: {title}\n"
        f"Description: {description or 'N/A'}"
    )
    result = await _call_mistral(prompt, max_tokens=300)

    def _resolve_gender(g: str, category: str = "") -> str:
        """Normalize LLM gender output to Thai standard values.
        Returns: "หญิง" / "ชาย" / "" (empty = unisex)
        """
        g = (g or "").strip()
        # Thai direct match
        if g in ("ผู้หญิง", "หญิง", "สาว", "แม่"):
            return "หญิง"
        if g in ("ผู้ชาย", "ชาย", "หนุ่ม"):
            return "ชาย"
        if g in ("ทุกเพศ", "unisex", "", "all"):
            return ""
        # English match (backward compat)
        gl = g.lower()
        if gl in ("female", "f", "women", "woman", "ladies"):
            return "หญิง"
        if gl in ("male", "m", "men", "man", "gentlemen"):
            return "ชาย"
        # Keyword-based fallback from title + description
        t = f"{title} {description or ''}".lower()
        _FEMALE_KW = (
            "ลิปสติก", "ลิป", "เซรั่ม", "ครีม", "มาส์ก", "สกินแคร์",
            "แต่งหน้า", "เครื่องสำอาง", "กันแดด", "โลชั่น", "น้ำหอม",
            "ผ้าอ้อม", "diaper", "lipstick", "serum", "cream",
            "skincare", "makeup", "cosmetic", "perfume", "sunscreen",
        )
        _MALE_KW = (
            "สูท", "นาฬิกาผู้ชาย", "shaver", "razor", "beard",
            "men", "man", "male",
        )
        if any(k.lower() in t for k in _FEMALE_KW):
            return "หญิง"
        if any(k.lower() in t for k in _MALE_KW):
            return "ชาย"
        return ""  # truly unisex

    if result:
        try:
            data = json.loads(result)
            out["gender"] = _resolve_gender(data.get("gender", ""), category)
            out["target_age"] = str(data.get("target_age", "") or "").strip()
            out["hashtags"] = _split_hashtags(data.get("hashtags", []))
        except Exception:
            m = re.search(r'"gender"\s*:\s*"([^"]+)"', result)
            if m:
                out["gender"] = _resolve_gender(m.group(1), category)
            m2 = re.search(r'"target_age"\s*:\s*"([^"]+)"', result)
            if m2:
                out["target_age"] = m2.group(1)
            matches = re.findall(r'"([^"]+)"', result)
            out["hashtags"] = [x for x in matches if x.startswith("#")][:12]
    # Final fallback: if still empty, try keyword detection on title+description
    if not out["gender"]:
        out["gender"] = _resolve_gender("", category)
    return out


def _score_viral(p: UnifiedProduct) -> float:
    score = (
        min(1.0, p.sold_total / 10000) * 30 +
        min(1.0, p.rating / 5.0) * 20 +
        min(1.0, (p.sold_week / max(1, p.sold_total))) * 20 +
        min(1.0, p.influencer_count / 50) * 15 +
        min(1.0, p.sales_gmv_7d / max(1, p.sales_gmv_30d)) * 15
    )
    return round(min(100, max(0, score)), 2)

# ─── Pipeline Entry Points ────────────────────────────────────────────────────

async def analyze_product(raw_data: dict, source: str = "") -> dict:
    """Single product: Normalize → Enrich → Export"""
    try:
        normalized = await ProductNormalizer.normalize(raw_data, source)
        enriched = await ProductEnricher.enrich(normalized)
        return ProductExporter.export_for_tus([enriched])
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return {"tus_ready": False, "error": str(e), "products": [], "count": 0, "timestamp": datetime.utcnow().isoformat()}

async def batch_analyze(raw_data_list: list, source: str = "", filters: dict = None) -> dict:
    """Batch: Normalize → Enrich → Export with filters"""
    try:
        normalized = [await ProductNormalizer.normalize(d, source) for d in raw_data_list]
        enriched = [await ProductEnricher.enrich(p) for p in normalized]
        return ProductExporter.export_for_tus(enriched, filters)
    except Exception as e:
        logger.error(f"Batch pipeline failed: {e}")
        return {"tus_ready": False, "error": str(e), "products": [], "count": 0, "timestamp": datetime.utcnow().isoformat()}

# DB-backed store — see analyzer_db.py
from product.analyzer_db import store_analyzed as _store_analyzed, get_analyzed_stats as _get_stats, get_analyzed_products as _get_products
from product.analyzer_db import store_analyzed_batch

async def store_analyzed(product: dict):
    await _store_analyzed(product)

async def get_analyzed_stats() -> dict:
    return await _get_stats()

async def get_analyzed_products(
    min_rating: Optional[float] = None,
    min_sold: Optional[int] = None,
    commission: Optional[float] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    seller_id: Optional[str] = None,
    seller_name: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    return await _get_products(
        min_rating=min_rating or 0,
        min_sold=min_sold or 0,
        commission=commission or 0,
        category=category,
        source=source,
        seller_id=seller_id,
        seller_name=seller_name,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )
