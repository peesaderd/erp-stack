"""Scraper service layer — auth, caching, billing, usage tracking."""
import os, json, logging, hashlib, secrets, asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import async_session_factory
from product.db_models import (
    ApiKey, ScrapedProduct, ScrapeLog, CreditUsage,
    SCRAPE_TIERS, get_tier_config, calculate_scrape_cost,
    _hash_url, _uuid,
)
from product.scraper import scrape_url as _scrape_url

logger = logging.getLogger("product_scraper_service")

# ─── Constants ──────────────────────────────────────────────────────────

CACHE_DURATION = timedelta(hours=24)  # default cache TTL
COST_PER_SCRAPE = 1.0  # THB per scrape default


# ═══════════════════════════════════════════════════════════════════════════
# API Key Management
# ═══════════════════════════════════════════════════════════════════════════

async def create_api_key(user_id: str, name: str = "API Key") -> dict:
    """Create a new API key for user. Returns (api_key_display, full_key)."""
    async with async_session_factory() as session:
        raw_key = f"scp_{secrets.token_hex(20)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        prefix = raw_key[:12] + "..."

        now = datetime.now(timezone.utc)
        import calendar
        # Reset to first of next month (works safely for all months)
        _, days_in_month = calendar.monthrange(now.year, now.month)
        safe_day = min(28, days_in_month)
        next_month = now.replace(day=safe_day) + timedelta(days=4)
        monthly_reset = next_month.replace(day=1, hour=0, minute=0, second=0, tzinfo=timezone.utc)

        api_key = ApiKey(
            user_id=user_id,
            key_prefix=prefix,
            key_hash=key_hash,
            name=name,
            monthly_reset=monthly_reset,
        )

        session.add(api_key)
        await session.commit()

        return {
            "id": api_key.id,
            "key": raw_key,           # show once only!
            "prefix": prefix,
            "name": name,
            "created_at": api_key.created_at.isoformat(),
        }


async def validate_api_key(raw_key: str) -> Optional[Dict]:
    """Validate API key and return user info. Returns None if invalid."""
    if not raw_key.startswith("scp_"):
        return None

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    async with async_session_factory() as session:
        result = await session.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,
            )
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            return None

        # Check monthly limit
        now = datetime.now(timezone.utc)
        # Handle offset-naive vs offset-aware comparison (SQLite stores naive)
        mr = api_key.monthly_reset
        if mr is not None and mr.tzinfo is None:
            mr = mr.replace(tzinfo=timezone.utc)
        if mr and now > mr:
            api_key.used_this_month = 0
            import calendar
            _, days_in_month = calendar.monthrange(now.year, now.month)
            safe_day = min(28, days_in_month)
            next_month = now.replace(day=safe_day) + timedelta(days=4)
            api_key.monthly_reset = next_month.replace(day=1, hour=0, minute=0, second=0, tzinfo=timezone.utc)

        if api_key.used_this_month >= api_key.monthly_limit:
            logger.warning(f"API key {api_key.key_prefix} exceeded monthly limit")
            return None

        # Update usage
        api_key.used_this_month += 1
        api_key.last_used_at = now
        await session.commit()

        return {
            "id": api_key.id,
            "user_id": api_key.user_id,
            "key_prefix": api_key.key_prefix,
        }


async def list_api_keys(user_id: str) -> List[Dict]:
    """List all API keys for a user (without full keys)."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
        )
        keys = result.scalars().all()
        return [
            {
                "id": k.id,
                "prefix": k.key_prefix,
                "name": k.name,
                "is_active": k.is_active,
                "monthly_limit": k.monthly_limit,
                "used_this_month": k.used_this_month,
                "created_at": k.created_at.isoformat(),
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            }
            for k in keys
        ]


async def revoke_api_key(key_id: str, user_id: str) -> bool:
    """Deactivate an API key."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
        )
        key = result.scalar_one_or_none()
        if not key:
            return False
        key.is_active = False
        await session.commit()
        return True


# ═══════════════════════════════════════════════════════════════════════════
# Caching
# ═══════════════════════════════════════════════════════════════════════════

async def get_cached_product(url: str) -> Optional[Dict]:
    """Check if URL was scraped recently. Returns cached product or None."""
    url_hash = _hash_url(url)
    async with async_session_factory() as session:
        result = await session.execute(
            select(ScrapedProduct).where(
                ScrapedProduct.url_hash == url_hash,
                ScrapedProduct.expires_at > datetime.now(timezone.utc) if True else True,
            )
        )
        cached = result.scalar_one_or_none()
        if cached and cached.expires_at and cached.expires_at > datetime.now(timezone.utc):
            return _product_to_dict(cached)
    return None


async def cache_product(url: str, data: Dict, tier: str = "free") -> str:
    """Store scraped data in cache. Returns product_id."""
    url_hash = _hash_url(url)
    cfg = get_tier_config(tier)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=cfg["cache_duration_hours"])

    images = data.get("images", [])
    if isinstance(images, str):
        images = [images]

    async with async_session_factory() as session:
        # Check if exists
        result = await session.execute(
            select(ScrapedProduct).where(ScrapedProduct.url_hash == url_hash)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.name = data.get("name") or existing.name
            existing.price = data.get("price") or existing.price
            existing.images = images or existing.images
            existing.description = data.get("description") or existing.description
            existing.sku = data.get("sku") or existing.sku
            existing.brand = data.get("brand") or existing.brand
            existing.source_site = data.get("source_site") or existing.source_site
            existing.method = data.get("method") or existing.method
            existing.expires_at = expires_at
            existing.scraped_at = datetime.now(timezone.utc)
            await session.commit()
            return existing.id
        else:
            product = ScrapedProduct(
                url_hash=url_hash,
                url=url,
                source_site=data.get("source_site", ""),
                name=data.get("name", ""),
                price=data.get("price"),
                currency=data.get("currency", "THB"),
                images=images,
                description=data.get("description", ""),
                sku=data.get("sku", ""),
                brand=data.get("brand", ""),
                raw_data=data.get("raw_data", {}),
                method=data.get("method", ""),
                proxy_used=data.get("proxy_used", ""),
                duration_ms=data.get("duration_ms", 0),
                expires_at=expires_at,
            )
            session.add(product)
            await session.commit()
            return product.id


def _product_to_dict(p: ScrapedProduct) -> Dict:
    return {
        "id": p.id,
        "name": p.name,
        "price": p.price,
        "currency": p.currency,
        "images": p.images or [],
        "description": p.description,
        "sku": p.sku,
        "brand": p.brand,
        "source_url": p.url,
        "source_site": p.source_site,
        "method": p.method,
        "scraped_at": p.scraped_at.isoformat() if p.scraped_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Usage & Billing
# ═══════════════════════════════════════════════════════════════════════════

async def log_scrape(
    user_id: str,
    url: str,
    success: bool,
    method: str,
    duration_ms: int,
    product_id: Optional[str] = None,
    api_key_id: Optional[str] = None,
    proxy_used: str = "",
    ip_address: str = "",
    cost: float = 0.0,
):
    """Log a scrape attempt for billing."""
    async with async_session_factory() as session:
        log = ScrapeLog(
            user_id=user_id,
            api_key_id=api_key_id,
            product_id=product_id,
            url=url,
            method=method,
            success=success,
            duration_ms=duration_ms,
            proxy_used=proxy_used,
            cost=cost,
            ip_address=ip_address,
        )
        session.add(log)

        # Update credit usage summary
        now = datetime.now(timezone.utc)
        ym = now.strftime("%Y-%m")
        result = await session.execute(
            select(CreditUsage).where(
                CreditUsage.user_id == user_id,
                CreditUsage.year_month == ym,
            )
        )
        usage = result.scalar_one_or_none()
        if usage:
            usage.total_scrapes += 1
            usage.total_cost += cost
            if product_id:
                usage.unique_urls += 1  # approximate, real dedup needs more logic
        else:
            usage = CreditUsage(
                user_id=user_id,
                year_month=ym,
                total_scrapes=1,
                total_cost=cost,
                unique_urls=1 if product_id else 0,
            )
            session.add(usage)

        await session.commit()


async def get_user_usage(user_id: str) -> Dict:
    """Get usage summary for user."""
    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)
        ym = now.strftime("%Y-%m")

        result = await session.execute(
            select(CreditUsage).where(
                CreditUsage.user_id == user_id,
                CreditUsage.year_month == ym,
            )
        )
        usage = result.scalar_one_or_none()
        if not usage:
            return {
                "total_scrapes": 0,
                "total_cost": 0.0,
                "unique_urls": 0,
            }

        # Get recent logs
        logs_result = await session.execute(
            select(ScrapeLog)
            .where(ScrapeLog.user_id == user_id)
            .order_by(ScrapeLog.created_at.desc())
            .limit(20)
        )
        recent_logs = [
            {
                "url": log.url[:80],
                "method": log.method,
                "success": log.success,
                "cost": log.cost,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs_result.scalars().all()
        ]

        return {
            "total_scrapes": usage.total_scrapes,
            "total_cost": usage.total_cost,
            "unique_urls": usage.unique_urls,
            "recent_logs": recent_logs,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Main Scrape Orchestrator
# ═══════════════════════════════════════════════════════════════════════════

async def scrape_with_tracking(
    url: str,
    user_id: Optional[str] = None,
    api_key_id: Optional[str] = None,
    use_vision: bool = False,
    proxy_url: Optional[str] = None,
    rotate_proxy: bool = True,
    user_tier: str = "free",
    ip_address: str = "",
) -> Dict:
    """Full scrape pipeline: check cache → scrape → store → log → return."""
    import time

    # Check cache first
    cached = await get_cached_product(url)
    if cached:
        logger.info(f"Cache hit: {url}")

        # Still log it (free, from cache)
        await log_scrape(
            user_id=user_id or "anonymous",
            url=url,
            success=True,
            method="cache",
            duration_ms=0,
            product_id=cached.get("id"),
            api_key_id=api_key_id,
            cost=0.0,
            ip_address=ip_address,
        )

        return {
            "success": True,
            "method": "cache",
            "product": cached,
            "error": None,
            "cached": True,
        }

    # Calculate cost
    usage_result = await get_user_usage(user_id or "anonymous")
    current_count = usage_result.get("total_scrapes", 0) if isinstance(usage_result, dict) else 0
    scrape_cost = calculate_scrape_cost(user_tier, current_count)
    logger.info(f"Scrape cost: {scrape_cost} THB (tier={user_tier}, used={current_count})")

    # Scrape
    start = time.time()
    result = await _scrape_url(url, proxy_url=proxy_url, rotate_proxy=rotate_proxy)
    duration_ms = int((time.time() - start) * 1000)

    # Cache product data
    product_id = None
    if result.get("product"):
        product_data = result["product"]
        product_data["method"] = result.get("method", "")
        product_data["duration_ms"] = duration_ms
        product_data["proxy_used"] = proxy_url or "none"
        product_id = await cache_product(url, product_data, tier=user_tier)

    # Log for billing
    await log_scrape(
        user_id=user_id or "anonymous",
        url=url,
        success=result["success"],
        method=result.get("method", "failed"),
        duration_ms=duration_ms,
        product_id=product_id,
        api_key_id=api_key_id,
        proxy_used=proxy_url or "none",
        ip_address=ip_address,
        cost=scrape_cost,
    )

    # Add cost info to result
    result["cost"] = scrape_cost
    result["cached"] = False

    return result
