"""Unit test for Product Lifecycle & Platform Post Locking Service."""
import unittest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.database import Base
from modules.product.db_models import AnalyzedProduct, ScrapedProduct, PlatformPostLock
from modules.product.lifecycle_service import ProductLifecycleManager


class TestProductLifecycleManager(unittest.TestCase):
    def setUp(self):
        # In-memory SQLite for fast testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()

        # Create test product
        self.product = AnalyzedProduct(
            id="prod_test_100",
            product_id="prod_test_100",
            title="Test Skincare Product",
            lifecycle_stage="TUS_READY",
            usage_count=0,
            max_usage_limit=2
        )
        self.db.add(self.product)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_stage_transition(self):
        success, msg = ProductLifecycleManager.transition_stage(
            self.db, "prod_test_100", "IN_PRODUCTION", is_analyzed_product=True
        )
        self.assertTrue(success)
        self.assertEqual(self.product.lifecycle_stage, "IN_PRODUCTION")

    def test_quota_claim_and_cooldown(self):
        # Claim 1
        success, msg, claim = ProductLifecycleManager.claim_product_for_user(
            self.db, "prod_test_100", "user_01"
        )
        self.assertTrue(success)
        self.assertEqual(claim["usage_count"], 1)

        # Claim 2
        success, msg, claim = ProductLifecycleManager.claim_product_for_user(
            self.db, "prod_test_100", "user_02"
        )
        self.assertTrue(success)
        self.assertEqual(claim["usage_count"], 2)

        # Claim 3 (Should exceed limit 2 -> Cooldown)
        success, msg, claim = ProductLifecycleManager.claim_product_for_user(
            self.db, "prod_test_100", "user_03"
        )
        self.assertFalse(success)
        self.assertEqual(self.product.lifecycle_stage, "COOLDOWN")
        self.assertIsNotNone(self.product.cooldown_until)

    def test_post_lock_matrix(self):
        content_id = "content_video_001"
        product_id = "prod_test_100"
        user_id = "user_01"
        platform = "tiktok"
        account_id = "tiktok_channel_alpha"

        # 1. Check lock before post -> Allowed
        allowed, reason, lock = ProductLifecycleManager.check_post_lock(
            self.db, content_id, platform, account_id
        )
        self.assertTrue(allowed)

        # 2. Record post
        rec = ProductLifecycleManager.record_post(
            self.db, content_id, product_id, user_id, platform, account_id
        )
        self.assertEqual(rec.post_status, "POSTED")

        # 3. Check lock after post -> Blocked
        allowed, reason, lock = ProductLifecycleManager.check_post_lock(
            self.db, content_id, platform, account_id
        )
        self.assertFalse(allowed)

        # 4. Request repost with content_reedited = True -> Auto Approved
        approved, msg, lock_info = ProductLifecycleManager.request_repost_permission(
            self.db, content_id, platform, account_id, reason="Re-edited with new music", content_reedited=True
        )
        self.assertTrue(approved)

        # 5. Check post lock again -> Allowed now
        allowed, reason, lock = ProductLifecycleManager.check_post_lock(
            self.db, content_id, platform, account_id
        )
        self.assertTrue(allowed)


if __name__ == "__main__":
    unittest.main()
