"""
Publisher Scheduler — Check queue, post due videos.
Random timing ±30min for natural-looking posting pattern.
"""

import os
import json
import random
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .post_queue import get_due_posts, mark_posting, mark_posted, mark_failed, enqueue, get_stats

logger = logging.getLogger("publisher-scheduler")

CHECK_INTERVAL_SECONDS = int(os.environ.get("PUBLISHER_CHECK_INTERVAL", "300"))  # 5 min
RANDOM_WINDOW_MINUTES = int(os.environ.get("PUBLISHER_RANDOM_WINDOW", "30"))      # ±30 min

STORAGE_DIR = Path(__file__).parent.parent / "storage"


class PublisherScheduler:
    """Background scheduler that checks queue and posts due videos."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._poster = None  # Lazy-load TikTokPoster
        self._running = False
        self._last_check: Optional[datetime] = None
        self._stats = {"posted": 0, "failed": 0, "last_error": None}

    @property
    def poster(self):
        if self._poster is None:
            from connect.tiktok_poster import poster as _poster
            self._poster = _poster
        return self._poster

    def start(self):
        """Start the background scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self.scheduler.add_job(
            self._check_and_post,
            IntervalTrigger(seconds=CHECK_INTERVAL_SECONDS),
            id="publisher_tick",
            name="Publisher Queue Checker",
            replace_existing=True,
        )
        self.scheduler.start()
        self._running = True
        logger.info(f"🕐 Publisher scheduler started — checks every {CHECK_INTERVAL_SECONDS}s, random window ±{RANDOM_WINDOW_MINUTES}min")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        self._running = False
        logger.info("Publisher scheduler stopped")

    @property
    def running(self) -> bool:
        return self._running

    async def _check_and_post(self):
        """Called by APScheduler — process due posts."""
        self._last_check = datetime.utcnow()

        due = get_due_posts()
        if not due:
            return

        logger.info(f"📋 Found {len(due)} due posts")
        stats = get_stats()
        logger.debug(f"   Queue: {stats['pending']}P {stats['scheduled']}S {stats['posted']}✓ {stats['failed']}✗")

        for post in due:
            # Random delay to look natural (0-RANDOM_WINDOW mins)
            delay = self._random_delay(post)
            if delay > 0:
                logger.info(f"   ⏳ {post['id']}: delaying {delay//60}m{delay%60}s")
                await asyncio.sleep(delay)

            await self._post_one(post)

    def _random_delay(self, post: dict) -> int:
        """Calculate random delay for natural posting pattern.
        - pending (immediate): 0-5 min
        - scheduled: 0-RANDOM_WINDOW min around schedule time
        - failed retry: 1-3 min
        """
        if post["status"] == "failed":
            return random.randint(60, 180)  # 1-3 min
        if post["status"] == "pending":
            return random.randint(0, 300)    # 0-5 min
        # scheduled — already passed schedule_at, add small random delay
        return random.randint(0, min(RANDOM_WINDOW_MINUTES * 60, 600))

    async def _post_one(self, post: dict):
        """Post a single video to TikTok."""
        post_id = post["id"]
        video_path = post["video_path"]
        caption = post.get("caption", "")
        hashtags = json.loads(post.get("hashtags", "[]")) if post.get("hashtags") else []

        # Resolve video path
        if not os.path.exists(video_path):
            # Try relative to storage
            alt = STORAGE_DIR / "videos" / os.path.basename(video_path)
            if alt.exists():
                video_path = str(alt)
            else:
                mark_failed(post_id, f"Video not found: {video_path}")
                self._stats["failed"] += 1
                return

        mark_posting(post_id)
        logger.info(f"📤 Posting {post_id}: {os.path.basename(video_path)}")

        try:
            result = await self.poster.post(
                video_path=video_path,
                caption=caption,
                hashtags=hashtags,
            )

            if result.get("success"):
                mark_posted(post_id, result.get("post_id", ""), result.get("post_url", ""))
                self._stats["posted"] += 1
                logger.info(f"✅ {post_id} posted via {result.get('method', '?')}")
            else:
                mark_failed(post_id, result.get("error", "Unknown error"))
                self._stats["failed"] += 1
                self._stats["last_error"] = result.get("error", "")
                logger.error(f"❌ {post_id} failed: {result.get('error', '?')}")
        except Exception as e:
            mark_failed(post_id, str(e))
            self._stats["failed"] += 1
            self._stats["last_error"] = str(e)
            logger.exception(f"❌ {post_id} exception")

    def enqueue_completed_video(
        self,
        job_id: str,
        video_path: str,
        caption: str = "",
        hashtags: list = None,
        affiliate_link: str = "",
        schedule_at: str = None,
    ) -> str:
        """Enqueue a completed pipeline video for posting."""
        return enqueue(
            job_id=job_id,
            video_path=video_path,
            caption=caption,
            hashtags=hashtags,
            affiliate_link=affiliate_link,
            schedule_at=schedule_at,
        )

    def get_status(self) -> dict:
        """Get current scheduler status."""
        return {
            "running": self._running,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "check_interval_seconds": CHECK_INTERVAL_SECONDS,
            "random_window_minutes": RANDOM_WINDOW_MINUTES,
            "stats": dict(self._stats),
            "queue_stats": get_stats(),
        }


# Singleton
scheduler = PublisherScheduler()
