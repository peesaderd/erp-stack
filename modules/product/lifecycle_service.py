"""Product Lifecycle & Platform Post Locking Service.

Handles stage transitions (LOCAL_RAW -> SCRAPED_STAGING -> ANALYZED -> TUS_READY -> IN_PRODUCTION -> PUBLISHED -> COOLDOWN),
multi-user product usage quota allocation, and platform post locking matrix (repost permissions).
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from modules.product.db_models import AnalyzedProduct, ScrapedProduct, PlatformPostLock, _uuid, _utcnow

VALID_STAGES = {
    "LOCAL_RAW",
    "SCRAPED_STAGING",
    "ANALYZED",
    "TUS_READY",
    "IN_PRODUCTION",
    "PUBLISHED",
    "COOLDOWN"
}


class ProductLifecycleManager:
    """Manages state transitions and posting permissions for products."""

    @staticmethod
    def transition_stage(
        db: Session,
        product_id: str,
        new_stage: str,
        is_analyzed_product: bool = True
    ) -> Tuple[bool, str]:
        """Safely transition a product's lifecycle stage."""
        if new_stage not in VALID_STAGES:
            return False, f"Invalid stage '{new_stage}'. Valid stages: {', '.join(VALID_STAGES)}"

        if is_analyzed_product:
            product = db.query(AnalyzedProduct).filter(
                (AnalyzedProduct.id == product_id) | (AnalyzedProduct.product_id == product_id)
            ).first()
        else:
            product = db.query(ScrapedProduct).filter(ScrapedProduct.id == product_id).first()

        if not product:
            return False, f"Product {product_id} not found"

        product.lifecycle_stage = new_stage
        db.commit()
        return True, f"Product stage transitioned to '{new_stage}'"

    @staticmethod
    def claim_product_for_user(
        db: Session,
        product_id: str,
        user_id: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Attempt to claim a product for content production under multi-user quota."""
        product = db.query(AnalyzedProduct).filter(
            (AnalyzedProduct.id == product_id) | (AnalyzedProduct.product_id == product_id)
        ).first()

        if not product:
            return False, f"Product {product_id} not found", {}

        # Check cooldown
        now = datetime.now(timezone.utc)
        if product.cooldown_until and product.cooldown_until > now:
            return False, f"Product is in cooldown until {product.cooldown_until.isoformat()}", {}

        # Check quota limit
        if product.usage_count >= product.max_usage_limit:
            # Set to cooldown for 14 days
            product.lifecycle_stage = "COOLDOWN"
            product.cooldown_until = now + timedelta(days=14)
            db.commit()
            return False, f"Product reached max usage quota ({product.usage_count}/{product.max_usage_limit}). Placed in 14-day cooldown.", {}

        # Grant claim
        product.usage_count += 1
        product.lifecycle_stage = "IN_PRODUCTION"
        db.commit()

        claim_info = {
            "product_id": product.id,
            "user_id": user_id,
            "usage_count": product.usage_count,
            "max_limit": product.max_usage_limit,
            "unique_seed": f"{product.id}_{user_id}_{product.usage_count}",
            "lifecycle_stage": product.lifecycle_stage
        }
        return True, "Product successfully claimed for production", claim_info

    @staticmethod
    def check_post_lock(
        db: Session,
        content_id: str,
        platform: str,
        account_id: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Check if content is locked for posting to specific (Platform, Account).

        Returns:
            (allowed: bool, reason: str, lock_record: dict)
        """
        lock = db.query(PlatformPostLock).filter(
            PlatformPostLock.content_id == content_id,
            PlatformPostLock.platform == platform.lower(),
            PlatformPostLock.account_id == account_id
        ).first()

        if not lock:
            # No previous post lock found -> allowed to post
            return True, "No prior post found on target account", None

        if lock.post_status == "REPOST_APPROVED":
            return True, "Repost explicitly approved for this account", {
                "lock_id": lock.id,
                "post_status": lock.post_status,
                "posted_at": lock.posted_at.isoformat() if lock.posted_at else None,
                "repost_count": lock.repost_count
            }

        # Otherwise locked (POSTED / REPOST_REQUESTED)
        return False, f"Content already posted to {platform} account '{account_id}' at {lock.posted_at}. Repost request required.", {
            "lock_id": lock.id,
            "post_status": lock.post_status,
            "posted_at": lock.posted_at.isoformat() if lock.posted_at else None,
            "repost_count": lock.repost_count
        }

    @staticmethod
    def record_post(
        db: Session,
        content_id: str,
        product_id: str,
        user_id: str,
        platform: str,
        account_id: str
    ) -> PlatformPostLock:
        """Record a successful post in the PlatformPostLock matrix."""
        existing = db.query(PlatformPostLock).filter(
            PlatformPostLock.content_id == content_id,
            PlatformPostLock.platform == platform.lower(),
            PlatformPostLock.account_id == account_id
        ).first()

        if existing:
            existing.post_status = "POSTED"
            existing.posted_at = datetime.now(timezone.utc)
            existing.repost_count += 1
            existing.repost_approved_at = None
            db.commit()
            return existing

        new_lock = PlatformPostLock(
            id=_uuid(),
            content_id=content_id,
            product_id=product_id,
            user_id=user_id,
            platform=platform.lower(),
            account_id=account_id,
            post_status="POSTED",
            posted_at=datetime.now(timezone.utc),
            repost_count=0
        )
        db.add(new_lock)
        db.commit()
        return new_lock

    @staticmethod
    def request_repost_permission(
        db: Session,
        content_id: str,
        platform: str,
        account_id: str,
        reason: str = "",
        content_reedited: bool = False
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Request permission to repost content on a previously used account.

        Auto-approves if:
        1. Content was re-edited (new TTS, BGM, or scene swap)
        2. OR 30 days have elapsed since previous post.
        """
        lock = db.query(PlatformPostLock).filter(
            PlatformPostLock.content_id == content_id,
            PlatformPostLock.platform == platform.lower(),
            PlatformPostLock.account_id == account_id
        ).first()

        if not lock:
            return False, "No post record found to request repost for", None

        now = datetime.now(timezone.utc)
        days_since_post = (now - lock.posted_at.replace(tzinfo=timezone.utc)).days if lock.posted_at else 999

        auto_approved = False
        approval_reason = ""

        if content_reedited:
            auto_approved = True
            approval_reason = "Auto-approved: Content was re-edited (unique video stream)"
        elif days_since_post >= 30:
            auto_approved = True
            approval_reason = f"Auto-approved: 30-day cooldown period elapsed ({days_since_post} days)"
        else:
            approval_reason = f"Pending manual review: Only {days_since_post}/30 days elapsed and content not re-edited"

        lock.repost_requested_at = now
        lock.repost_reason = reason
        lock.content_reedited = content_reedited

        if auto_approved:
            lock.post_status = "REPOST_APPROVED"
            lock.repost_approved_at = now
        else:
            lock.post_status = "REPOST_REQUESTED"

        db.commit()

        result = {
            "lock_id": lock.id,
            "post_status": lock.post_status,
            "auto_approved": auto_approved,
            "days_since_last_post": days_since_post,
            "message": approval_reason
        }
        return auto_approved, approval_reason, result
