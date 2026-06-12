"""Analyzer Database CRUD — async PostgreSQL, replaces in-memory store.

Uses AnalyzedProduct model from db_models.py and shared async database session.
"""
import os, logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from sqlalchemy import func, select, and_, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from product.db_models import AnalyzedProduct

logger = logging.getLogger("analyzer_db")

DB_URL = os.environ.get(
    "ANALYZER_DB_URL",
    "postgresql+asyncpg://openhands:OpenHands%40ERP2026@127.0.0.1:5432/erp_stack"
)

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(DB_URL, echo=False, pool_size=5, max_overflow=10)
    return _engine

async def _run(fn):
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        try:
            result = await fn(session)
            await session.commit()
            return result
        except Exception as e:
            await session.rollback()
            raise

async def store_analyzed(product: dict) -> str:
    """Store/update an analyzed product. Returns product id."""
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        try:
            pid = product.get("product_id", "")
            src = product.get("source", "")
            existing = None
            if pid and src:
                result = await session.execute(
                    select(AnalyzedProduct).where(
                        and_(
                            AnalyzedProduct.product_id == pid,
                            AnalyzedProduct.source == src,
                        )
                    )
                )
                existing = result.scalar_one_or_none()

            now_str = datetime.now(timezone.utc).isoformat()

            if existing:
                for key, val in product.items():
                    if val is not None and hasattr(existing, key):
                        setattr(existing, key, val)
                existing.updated_at = now_str
                record_id = existing.id
            else:
                import uuid; _uuid = lambda: str(uuid.uuid4())
                record = AnalyzedProduct(
                    id=_uuid(),
                    created_at=now_str,
                    updated_at=now_str,
                    **{k: v for k, v in product.items()
                       if hasattr(AnalyzedProduct, k) and k != "id"}
                )
                session.add(record)
                await session.flush()
                record_id = record.id

            await session.commit()
            return record_id
        except Exception as e:
            await session.rollback()
            logger.error(f"store_analyzed failed: {e}")
            return ""


async def get_analyzed_stats() -> dict:
    """Aggregate stats from all analyzed products."""
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        try:
            total = (await session.execute(
                select(func.count(AnalyzedProduct.id))
            )).scalar() or 0

            avg_rating = (await session.execute(
                select(func.avg(AnalyzedProduct.rating))
            )).scalar() or 0.0

            avg_viral = (await session.execute(
                select(func.avg(AnalyzedProduct.viral_score))
            )).scalar() or 0.0

            trending = (await session.execute(
                select(func.count(AnalyzedProduct.id)).where(
                    AnalyzedProduct.trending == True
                )
            )).scalar() or 0

            rows = (await session.execute(
                text("""
                    SELECT category, COUNT(*) as count
                    FROM analyzed_products
                    WHERE category != '' AND category IS NOT NULL
                    GROUP BY category
                    ORDER BY count DESC
                    LIMIT 5
                """)
            )).fetchall()

            top_categories = [{"category": r[0], "count": r[1]} for r in rows]

            return {
                "total": total,
                "avg_rating": round(float(avg_rating), 2),
                "avg_viral_score": round(float(avg_viral), 2),
                "trending_count": trending,
                "top_categories": top_categories,
            }
        except Exception as e:
            logger.error(f"get_analyzed_stats failed: {e}")
            return {"total": 0, "avg_rating": 0, "avg_viral_score": 0,
                    "trending_count": 0, "top_categories": []}


async def get_analyzed_products(
    min_rating: float = 0,
    min_sold: int = 0,
    commission: float = 0,
    category: str = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Query analyzed products with filters."""
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        try:
            stmt = select(AnalyzedProduct)
            if min_rating > 0:
                stmt = stmt.where(AnalyzedProduct.rating >= min_rating)
            if min_sold > 0:
                stmt = stmt.where(AnalyzedProduct.sold_total >= min_sold)
            if commission > 0:
                stmt = stmt.where(AnalyzedProduct.commission_rate >= commission)
            if category:
                stmt = stmt.where(AnalyzedProduct.category == category)

            result = await session.execute(stmt)
            all_records = result.scalars().all()
            total = len(all_records)

            records = sorted(
                all_records,
                key=lambda r: r.viral_score or 0,
                reverse=True
            )[offset:offset + limit]

            products = []
            for r in records:
                products.append({
                    "product_id": r.product_id,
                    "title": r.title,
                    "title_th": r.title_th,
                    "price_thb": r.price_avg,
                    "rating": r.rating,
                    "sold_total": r.sold_total,
                    "viral_score": r.viral_score,
                    "trending": r.trending,
                    "category": r.category,
                    "keywords": r.keywords or [],
                    "images": r.images or [],
                    "commission": f"{r.commission_rate}%",
                    "source": r.source,
                    "seller_name": r.seller_name,
                    "enriched": r.enriched,
                })

            return {
                "tus_ready": True,
                "products": products,
                "count": len(products),
                "total": total,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"get_analyzed_products failed: {e}")
            return {
                "tus_ready": False, "products": [], "count": 0,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


async def store_analyzed_batch(products: list) -> int:
    """Store multiple products. Returns count stored."""
    count = 0
    for p in products:
        if await store_analyzed(p):
            count += 1
    return count


async def init_db():
    """Create tables if not exists. Run on service startup."""
    from shared.database import Base
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Analyzer DB tables ready")
