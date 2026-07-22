-- Migration Script: Product Lifecycle & Platform Post Lock Schema Update
-- Target DB: PostgreSQL (erp_stack) on Remote Cloud Server (calm-noether-db-1)

-- 1. Update scraped_products table
ALTER TABLE scraped_products 
ADD COLUMN IF NOT EXISTS lifecycle_stage VARCHAR(30) DEFAULT 'SCRAPED_STAGING',
ADD COLUMN IF NOT EXISTS usage_count INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS max_usage_limit INT DEFAULT 5,
ADD COLUMN IF NOT EXISTS cooldown_until TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_scraped_products_lifecycle_stage ON scraped_products(lifecycle_stage);

-- 2. Update analyzed_products table
ALTER TABLE analyzed_products 
ADD COLUMN IF NOT EXISTS lifecycle_stage VARCHAR(30) DEFAULT 'ANALYZED',
ADD COLUMN IF NOT EXISTS usage_count INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS max_usage_limit INT DEFAULT 5,
ADD COLUMN IF NOT EXISTS cooldown_until TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_analyzed_products_lifecycle_stage ON analyzed_products(lifecycle_stage);

-- 3. Create platform_post_locks table
CREATE TABLE IF NOT EXISTS platform_post_locks (
    id VARCHAR(64) PRIMARY KEY,
    content_id VARCHAR(100) NOT NULL,
    product_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    account_id VARCHAR(100) NOT NULL,
    post_status VARCHAR(30) DEFAULT 'POSTED',
    posted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    repost_requested_at TIMESTAMP WITH TIME ZONE,
    repost_approved_at TIMESTAMP WITH TIME ZONE,
    repost_count INT DEFAULT 0,
    repost_reason TEXT DEFAULT '',
    content_reedited BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_post_locks_content_id ON platform_post_locks(content_id);
CREATE INDEX IF NOT EXISTS idx_post_locks_product_id ON platform_post_locks(product_id);
CREATE INDEX IF NOT EXISTS idx_post_locks_user_id ON platform_post_locks(user_id);
CREATE INDEX IF NOT EXISTS idx_post_locks_platform_acc ON platform_post_locks(platform, account_id);
