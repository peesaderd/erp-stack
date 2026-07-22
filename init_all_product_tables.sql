-- Comprehensive SQL Schema Setup for Product Scraper, Analyzer, Lifecycle & Platform Post Locks
-- Target DB: PostgreSQL (erp_stack) on container 'db'

-- 1. Scraped Products
CREATE TABLE IF NOT EXISTS scraped_products (
    id VARCHAR(64) PRIMARY KEY,
    url_hash VARCHAR(16) UNIQUE NOT NULL,
    url TEXT NOT NULL,
    source_site VARCHAR(50) DEFAULT '',
    name TEXT DEFAULT '',
    price DOUBLE PRECISION,
    currency VARCHAR(3) DEFAULT 'THB',
    images JSONB DEFAULT '[]'::jsonb,
    description TEXT DEFAULT '',
    sku VARCHAR(100) DEFAULT '',
    brand VARCHAR(200) DEFAULT '',
    raw_data JSONB DEFAULT '{}'::jsonb,
    method VARCHAR(20) DEFAULT '',
    proxy_used VARCHAR(100) DEFAULT '',
    duration_ms INT DEFAULT 0,
    lifecycle_stage VARCHAR(30) DEFAULT 'SCRAPED_STAGING',
    usage_count INT DEFAULT 0,
    max_usage_limit INT DEFAULT 5,
    cooldown_until TIMESTAMP WITH TIME ZONE,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_scraped_url_hash ON scraped_products(url_hash);
CREATE INDEX IF NOT EXISTS idx_scraped_lifecycle ON scraped_products(lifecycle_stage);

-- 2. Analyzed Products
CREATE TABLE IF NOT EXISTS analyzed_products (
    id VARCHAR(64) PRIMARY KEY,
    product_id VARCHAR(100) DEFAULT '',
    title TEXT DEFAULT '',
    title_th TEXT DEFAULT '',
    description TEXT DEFAULT '',
    price_min DOUBLE PRECISION DEFAULT 0.0,
    price_max DOUBLE PRECISION DEFAULT 0.0,
    price_avg DOUBLE PRECISION DEFAULT 0.0,
    currency VARCHAR(3) DEFAULT 'THB',
    rating DOUBLE PRECISION DEFAULT 0.0,
    review_count INT DEFAULT 0,
    sold_total INT DEFAULT 0,
    sold_week INT DEFAULT 0,
    sold_month INT DEFAULT 0,
    sales_gmv_7d DOUBLE PRECISION DEFAULT 0.0,
    sales_gmv_30d DOUBLE PRECISION DEFAULT 0.0,
    sales_gmv_total DOUBLE PRECISION DEFAULT 0.0,
    sales_gmv_7d_usd DOUBLE PRECISION DEFAULT 0.0,
    sales_gmv_30d_usd DOUBLE PRECISION DEFAULT 0.0,
    sales_gmv_total_usd DOUBLE PRECISION DEFAULT 0.0,
    gmv_total DOUBLE PRECISION DEFAULT 0.0,
    url TEXT DEFAULT '',
    seller_name VARCHAR(200) DEFAULT '',
    seller_id VARCHAR(100) DEFAULT '',
    categories JSONB DEFAULT '[]'::jsonb,
    category VARCHAR(100) DEFAULT '',
    images JSONB DEFAULT '[]'::jsonb,
    commission_rate DOUBLE PRECISION DEFAULT 0.0,
    influencer_count INT DEFAULT 0,
    video_count INT DEFAULT 0,
    rank INT DEFAULT 0,
    source VARCHAR(50) DEFAULT '',
    scrape_timestamp VARCHAR(50) DEFAULT '',
    viral_score DOUBLE PRECISION DEFAULT 0.0,
    trending BOOLEAN DEFAULT FALSE,
    keywords JSONB DEFAULT '[]'::jsonb,
    enriched BOOLEAN DEFAULT FALSE,
    variants JSONB DEFAULT '[]'::jsonb,
    lifecycle_stage VARCHAR(30) DEFAULT 'ANALYZED',
    usage_count INT DEFAULT 0,
    max_usage_limit INT DEFAULT 5,
    cooldown_until TIMESTAMP WITH TIME ZONE,
    created_at VARCHAR(50) DEFAULT '',
    updated_at VARCHAR(50) DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_analyzed_prod_id ON analyzed_products(product_id);
CREATE INDEX IF NOT EXISTS idx_analyzed_source ON analyzed_products(source);
CREATE INDEX IF NOT EXISTS idx_analyzed_lifecycle ON analyzed_products(lifecycle_stage);

-- 3. Platform Post Locks Matrix
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
