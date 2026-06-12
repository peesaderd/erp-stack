"""Product scraper database models — usage tracking, caching, API keys."""
import uuid, hashlib, json
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON, BigInteger
from sqlalchemy.orm import relationship
from shared.database import Base


def _utcnow():
    return datetime.now(timezone.utc)

def _uuid():
    return str(uuid.uuid4())

def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


# ──────────────────────────────────────────────
# API Keys (per user)
# ──────────────────────────────────────────────

class ApiKey(Base):
    """API keys for programmatic scraping access."""
    __tablename__ = "scrape_api_keys"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)       # from auth.users
    key_prefix = Column(String(20), nullable=False)            # first 12+ chars for display
    key_hash = Column(String(64), nullable=False, unique=True) # sha256 of full key
    name = Column(String(100), default="Default API Key")
    monthly_limit = Column(Integer, default=1000)
    used_this_month = Column(Integer, default=0)
    monthly_reset = Column(DateTime(timezone=True), nullable=True)  # when usage resets
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    logs = relationship("ScrapeLog", back_populates="api_key", cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# Scraped Product Cache (dedup by URL)
# ──────────────────────────────────────────────

class ScrapedProduct(Base):
    """Cache of scraped product data. Same URL = same cache entry (user-agnostic)."""
    __tablename__ = "scraped_products"

    id = Column(String, primary_key=True, default=_uuid)
    url_hash = Column(String(16), unique=True, nullable=False, index=True)  # sha256[:16]
    url = Column(Text, nullable=False)
    source_site = Column(String(50), default="")        # amazon, shopee, lazada, boots
    name = Column(Text, default="")
    price = Column(Float, nullable=True)
    currency = Column(String(3), default="THB")
    images = Column(JSON, default=list)
    description = Column(Text, default="")
    sku = Column(String(100), default="")
    brand = Column(String(200), default="")
    raw_data = Column(JSON, default=dict)               # full API/HTML response
    method = Column(String(20), default="")             # http, playwright, api_intercept
    proxy_used = Column(String(100), default="")
    duration_ms = Column(Integer, default=0)
    scraped_at = Column(DateTime(timezone=True), default=_utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # cache TTL

    logs = relationship("ScrapeLog", back_populates="cached_product", cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# Scrape Usage Log (billing)
# ──────────────────────────────────────────────

class ScrapeLog(Base):
    """Every scrape attempt = 1 log entry. Used for billing & tracking."""
    __tablename__ = "scrape_logs"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)        # from auth.users
    api_key_id = Column(String, ForeignKey("scrape_api_keys.id"), nullable=True, index=True)
    product_id = Column(String, ForeignKey("scraped_products.id"), nullable=True, index=True)
    url = Column(Text, nullable=False)
    method = Column(String(20), default="")                     # http, playwright, api_intercept
    success = Column(Boolean, default=False)
    duration_ms = Column(Integer, default=0)
    proxy_used = Column(String(100), default="")
    cost = Column(Float, default=0.0)                           # per-scrape cost (credit)
    ip_address = Column(String(45), default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    api_key = relationship("ApiKey", back_populates="logs")
    cached_product = relationship("ScrapedProduct", back_populates="logs")


# ──────────────────────────────────────────────
# Credit Usage Summary (materialized view alternative)
# ──────────────────────────────────────────────

class CreditUsage(Base):
    """Accumulated credit usage per user per month."""
    __tablename__ = "scrape_credit_usage"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    year_month = Column(String(7), nullable=False)              # "2026-06"
    total_scrapes = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    unique_urls = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


# ──────────────────────────────────────────────
# Price History
# ──────────────────────────────────────────────

class PriceHistory(Base):
    """Track price changes over time for scraped products."""
    __tablename__ = "scrape_price_history"

    id = Column(String, primary_key=True, default=_uuid)
    product_id = Column(String, ForeignKey("scraped_products.id"), nullable=False, index=True)
    url_hash = Column(String(16), index=True)
    url = Column(Text, default="")
    price = Column(Float, nullable=True)
    currency = Column(String(3), default="THB")
    source_site = Column(String(50), default="")
    recorded_at = Column(DateTime(timezone=True), default=_utcnow)


# ──────────────────────────────────────────────
# Scheduled Scrapes
# ──────────────────────────────────────────────

class ScheduledScrape(Base):
    """Recurring scrape jobs (cron-like)."""
    __tablename__ = "scrape_scheduled_jobs"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String(100), default="")
    urls = Column(JSON, default=list)
    schedule = Column(String(50), default="daily")  # hourly, daily, weekly, monthly
    next_run = Column(DateTime(timezone=True), nullable=True)
    last_run = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="active")  # active, paused, completed
    export_to_pipeline = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


# ──────────────────────────────────────────────
# Pricing Tiers
# ──────────────────────────────────────────────

SCRAPE_TIERS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "scrapes_per_month": 10,
        "cost_per_scrape": 0,       # free tier, no extra cost
        "proxy_included": False,
        "cache_duration_hours": 24,
    },
    "bronze": {
        "name": "Bronze",
        "price_monthly": 149,       # ~$4 ≈ 150 THB
        "scrapes_per_month": 100,
        "cost_per_scrape": 1.0,     # 1 THB per scrape over limit
        "proxy_included": True,
        "cache_duration_hours": 48,
    },
    "silver": {
        "name": "Silver",
        "price_monthly": 499,       # ~$14 
        "scrapes_per_month": 500,
        "cost_per_scrape": 0.5,     # 0.5 THB per scrape over limit
        "proxy_included": True,
        "cache_duration_hours": 72,
    },
    "gold": {
        "name": "Gold",
        "price_monthly": 1499,      # ~$42
        "scrapes_per_month": 3000,
        "cost_per_scrape": 0.2,     # 0.2 THB per scrape over limit
        "proxy_included": True,
        "cache_duration_hours": 168,
    },
    "ultra": {
        "name": "Ultra",
        "price_monthly": 4999,      # ~$140
        "scrapes_per_month": 15000,
        "cost_per_scrape": 0.1,     # 0.1 THB per scrape over limit
        "proxy_included": True,
        "cache_duration_hours": 720,
    },
}


def get_tier_config(tier: str) -> dict:
    return SCRAPE_TIERS.get(tier, SCRAPE_TIERS["free"])


def calculate_scrape_cost(user_tier: str, current_month_usage: int) -> float:
    """Calculate cost for a scrape based on tier and usage."""
    cfg = get_tier_config(user_tier)
    if current_month_usage < cfg["scrapes_per_month"]:
        return 0.0  # within free quota
    return cfg["cost_per_scrape"]


# ──────────────────────────────────────────────
# Price History
# ──────────────────────────────────────────────



# ──────────────────────────────────────────────
# Analyzed Product (Product Analyzer Module)
# ──────────────────────────────────────────────

class AnalyzedProduct(Base):
    """Analyzed/enriched product data. Written by the Analyzer pipeline."""
    __tablename__ = "analyzed_products"

    id = Column(String, primary_key=True, default=_uuid)
    product_id = Column(String, default="", index=True)
    title = Column(Text, default="")
    title_th = Column(Text, default="")
    description = Column(Text, default="")
    price_min = Column(Float, default=0.0)
    price_max = Column(Float, default=0.0)
    price_avg = Column(Float, default=0.0)
    currency = Column(String(3), default="THB")
    rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)
    sold_total = Column(Integer, default=0)
    sold_week = Column(Integer, default=0)
    sold_month = Column(Integer, default=0)
    sales_gmv_7d = Column(Float, default=0.0)
    sales_gmv_30d = Column(Float, default=0.0)
    sales_gmv_total = Column(Float, default=0.0)
    sales_gmv_7d_usd = Column(Float, default=0.0)
    sales_gmv_30d_usd = Column(Float, default=0.0)
    sales_gmv_total_usd = Column(Float, default=0.0)
    seller_name = Column(String(200), default="")
    seller_id = Column(String(100), default="")
    categories = Column(JSON, default=list)
    category = Column(String(100), default="")
    images = Column(JSON, default=list)
    commission_rate = Column(Float, default=0.0)
    influencer_count = Column(Integer, default=0)
    video_count = Column(Integer, default=0)
    rank = Column(Integer, default=0)
    source = Column(String(50), default="", index=True)
    scrape_timestamp = Column(String(50), default="")
    viral_score = Column(Float, default=0.0)
    trending = Column(Boolean, default=False)
    keywords = Column(JSON, default=list)
    enriched = Column(Boolean, default=False)
    created_at = Column(String(50), default="")
    updated_at = Column(String(50), default="")
