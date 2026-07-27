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

    async def _get_all_platform_items(self) -> List[Dict]:
        """Get publish items for all connected active platforms."""
        try:
            accounts = await self.poster.aitoearn.list_accounts()
            items = []
            for a in accounts:
                if a.get("status") == 1:
                    items.append({
                        "platform": a.get("type", ""),
                        "accountId": a.get("id", ""),
                        "nickname": a.get("nickname", ""),
                    })
            return items
        except Exception as e:
            logger.warning(f"Failed to get platform accounts: {e}")
            return []

    async def _post_one(self, post: dict):
        """Post a single video to ALL connected platforms (multi-platform)."""
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
            # Build multi-platform items from all connected accounts
            items = await self._get_all_platform_items()
            if not items:
                # Fallback: use queue platform
                items = None
                logger.info("No platform items found — using queue platform only")

            result = await self.poster.post(
                video_path=video_path,
                caption=caption,
                title=post.get("title", ""),
                description=post.get("description", ""),
                items=items,
                platform=post.get("platform", "tiktok"),
                account_id=post.get("account_id", ""),
                hashtags=hashtags,
            )

            if result.get("success"):
                flow_id = result.get("flow_id", "")
                platforms = result.get("platforms", [])
                mark_posted(post_id, flow_id, "")
                self._stats["posted"] += 1
                logger.info(f"✅ {post_id} posted to {platforms} via {result.get('method', '?')} — flow={flow_id}")
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
        title: str = "",
        description: str = "",
        caption: str = "",
        hashtags: list = None,
        affiliate_link: str = "",
        platform: str = "tiktok",
        account_id: str = "",
        schedule_at: str = None,
    ) -> str:
        """Enqueue a completed pipeline video for posting."""
        return enqueue(
            job_id=job_id,
            video_path=video_path,
            title=title,
            description=description,
            caption=caption,
            hashtags=hashtags,
            affiliate_link=affiliate_link,
            platform=platform,
            account_id=account_id,
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

    def bulk_schedule(
        self,
        video_ids: List[str],
        date_range_start: str = None,
        date_range_end: str = None,
        count_per_day: int = 3,
        mode: str = "random",  # random | fixed | sequential
        time_window_start: str = "08:00",
        time_window_end: str = "22:00",
        platform: str = "tiktok",
    ) -> List[str]:
        """Bulk schedule multiple videos across a date range.
        
        Mode:
        - random: random time within window each day
        - fixed: same time each day (time_window_start)
        - sequential: evenly spaced within window
        
        Returns list of post IDs created.
        """
        import random as _rand
        
        if not video_ids:
            return []
        
        # Parse date range (default: next 7 days)
        today = datetime.utcnow().date()
        start_date = datetime.fromisoformat(date_range_start).date() if date_range_start else today
        end_date = datetime.fromisoformat(date_range_end).date() if date_range_end else today + timedelta(days=7)
        
        if end_date < start_date:
            raise ValueError("end_date must be >= start_date")
        
        # Parse time window
        tw_start_h, tw_start_m = map(int, time_window_start.split(":"))
        tw_end_h, tw_end_m = map(int, time_window_end.split(":"))
        tw_start_min = tw_start_h * 60 + tw_start_m
        tw_end_min = tw_end_h * 60 + tw_end_m
        window_minutes = tw_end_min - tw_start_min
        
        if window_minutes <= 0:
            raise ValueError("time_window_end must be after time_window_start")
        
        total_days = (end_date - start_date).days + 1
        total_slots = total_days * count_per_day
        
        # Distribute videos across slots (cycle through if more videos than slots)
        posts = []
        for i, vid_info in enumerate(video_ids):
            if isinstance(vid_info, str):
                vid_info = {"job_id": vid_info, "video_path": vid_info}
            
            slot_idx = i % total_slots
            day_offset = slot_idx // count_per_day
            slot_in_day = slot_idx % count_per_day
            post_date = start_date + timedelta(days=day_offset)
            
            # Calculate time based on mode
            if mode == "random":
                minute_offset = _rand.randint(0, window_minutes)
                
            elif mode == "fixed":
                minute_offset = 0  # use time_window_start
                
            elif mode == "sequential":
                # Evenly spaced within window
                if count_per_day > 1:
                    minute_offset = (window_minutes // (count_per_day - 1)) * slot_in_day if count_per_day > 1 else 0
                else:
                    minute_offset = window_minutes // 2
            else:
                minute_offset = 0
            
            total_minutes = tw_start_min + minute_offset
            post_h = total_minutes // 60
            post_m = total_minutes % 60
            schedule_dt = datetime(post_date.year, post_date.month, post_date.day, post_h, post_m, 0)
            
            # Enqueue
            post_id = enqueue(
                job_id=vid_info.get("job_id", ""),
                video_path=vid_info.get("video_path", ""),
                title=vid_info.get("title", ""),
                description=vid_info.get("description", ""),
                caption=vid_info.get("caption", ""),
                hashtags=vid_info.get("hashtags", []),
                platform=vid_info.get("platform", platform),
                account_id=vid_info.get("account_id", ""),
                schedule_at=schedule_dt.isoformat(),
            )
            posts.append(post_id)
        
        logger.info(f"📅 Bulk scheduled {len(posts)} posts across {total_days} days ({count_per_day}/day, mode={mode})")
        return posts


# Singleton
scheduler = PublisherScheduler()
