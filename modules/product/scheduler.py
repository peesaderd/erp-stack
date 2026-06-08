"""Simple background scheduler for recurring scrapes.
Checks every 60 seconds for due jobs and executes them."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from shared.database import async_session_factory
from product.db_models import ScheduledScrape
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


async def check_due_jobs():
    """Find and execute due scheduled scrapes."""
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
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
                # Update next_run based on schedule
                if job.schedule == "hourly":
                    job.next_run = now + timedelta(hours=1)
                elif job.schedule == "daily":
                    job.next_run = now + timedelta(days=1)
                elif job.schedule == "weekly":
                    job.next_run = now + timedelta(weeks=1)
                elif job.schedule == "monthly":
                    job.next_run = now + timedelta(days=30)
                else:
                    job.next_run = now + timedelta(days=1)
                job.last_run = now
                await session.commit()
            except Exception as e:
                logger.error(f"Scheduled scrape job {job.id} failed: {e}")
                job.status = "error"
                await session.commit()


async def start_scheduler():
    """Entry point for the background scheduler task."""
    await run_scheduler_loop()
