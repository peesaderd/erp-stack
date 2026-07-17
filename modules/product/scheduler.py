"""Simple background scheduler for recurring scrapes.
Checks every 60 seconds for due jobs and executes them."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from shared.database import async_session_factory
from product.db_models import ScheduledScrape, ProductWatch
from product.scraper_service import run_scheduled_scrape

logger = logging.getLogger("product_scheduler")


async def run_scheduler_loop():
    """Main scheduler loop."""
    while True:
        try:
            await check_due_jobs()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(60)


def _last_run_window(schedule: str, now: datetime) -> datetime:
    """Return datetime before which a job should be re-run."""
    if schedule == "hourly":
        return now - timedelta(hours=1)
    elif schedule == "daily":
        return now - timedelta(days=1)
    elif schedule == "weekly":
        return now - timedelta(weeks=1)
    elif schedule == "monthly":
        return now - timedelta(days=30)
    else:
        return now - timedelta(days=1)


async def check_due_jobs():
    """Find and execute due scheduled scrapes and keyword watches."""
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        # ── Scheduled URL Scrapes ──
        result = await session.execute(
            select(ScheduledScrape).where(
                ScheduledScrape.status == "active",
                ScheduledScrape.next_run <= now,
            )
        )
        jobs = result.scalars().all()
        for job in jobs:
            logger.info(f"Running scheduled scrape job {job.id} ({job.name})")
            try:
                await run_scheduled_scrape(job.id)
                job.next_run = now + timedelta(hours=1) if job.schedule == "hourly" \
                    else now + timedelta(days=1) if job.schedule == "daily" \
                    else now + timedelta(weeks=1) if job.schedule == "weekly" \
                    else now + timedelta(days=30) if job.schedule == "monthly" \
                    else now + timedelta(days=1)
                job.last_run = now
                await session.commit()
            except Exception as e:
                logger.error(f"Scheduled scrape job {job.id} failed: {e}")
                job.status = "error"
                await session.commit()

        # ── Keyword Watches ──
        watch_window = now - timedelta(hours=23)  # daily = run once per ~24h
        result = await session.execute(
            select(ProductWatch).where(
                ProductWatch.active == True,
                ProductWatch.schedule != "manual",
            )
        )
        watches = result.scalars().all()
        for watch in watches:
            last_run = watch.last_run_at or datetime.min.replace(tzinfo=timezone.utc)
            window = _last_run_window(watch.schedule, now)
            if last_run < window:
                logger.info(f"Running keyword watch {watch.id} ({watch.name})")
                try:
                    from product.main import _run_watch
                    result = await _run_watch(watch.id)
                    logger.info(f"Watch {watch.name}: {result.get('new_found', 0)} new, {result.get('total_tracked', 0)} total")
                except Exception as e:
                    logger.error(f"Keyword watch {watch.id} failed: {e}")


async def start_scheduler():
    """Entry point for the background scheduler task."""
    await run_scheduler_loop()
