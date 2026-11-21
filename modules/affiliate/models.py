import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

DB_PATH = os.environ.get("SMARTBACK_DB_PATH", "/home/openhands/smartback_backend/smartback.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_affiliate_tables():
    """Ensure ERP Affiliate tables exist in SQLite database."""
    conn = get_db()
    cursor = conn.cursor()

    # 1. Affiliate Networks
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS affiliate_networks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL, -- 'accesstrade', 'involve_asia', 'shopee'
        name TEXT NOT NULL,
        api_key TEXT,
        api_secret TEXT,
        webhook_secret TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Store Campaigns Master
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS affiliate_campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_key TEXT UNIQUE NOT NULL,
        store_name TEXT NOT NULL,
        domain TEXT NOT NULL,
        network TEXT NOT NULL,
        offer_id TEXT NOT NULL,
        commission_rate REAL NOT NULL,
        cashback_share REAL NOT NULL,
        category TEXT DEFAULT 'general',
        icon TEXT DEFAULT '🛒',
        is_active INTEGER DEFAULT 1
    );
    """)

    # 3. Double-entry Financial Ledger
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS affiliate_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id TEXT UNIQUE NOT NULL,
        order_ref TEXT NOT NULL,
        user_code TEXT NOT NULL,
        debit_account TEXT NOT NULL,  -- e.g. '1120-Network-Receivable'
        credit_account TEXT NOT NULL, -- e.g. '2120-Member-Cashback-Liability' or '4110-Commission-Revenue'
        amount REAL NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed Default Networks if empty
    cursor.execute("SELECT COUNT(*) FROM affiliate_networks")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO affiliate_networks (slug, name, api_key, api_secret, is_active)
        VALUES 
        ('accesstrade', 'AccessTrade Thailand (Interspace)', 'at_pub_live_98124', 'sec_at_98124', 1),
        ('involve_asia', 'Involve Asia SE Asia', 'inv_pub_live_77215', 'sec_inv_77215', 1),
        ('shopee', 'Shopee Open Platform', 'shp_aff_88129', 'sec_shp_88129', 1)
        """)

    # Seed Default Campaigns if empty
    cursor.execute("SELECT COUNT(*) FROM affiliate_campaigns")
    if cursor.fetchone()[0] == 0:
        campaigns = [
            ('lotus', "Lotus's Online", 'lotuss.com', 'accesstrade', '10928', 0.055, 0.70, 'groceries', '🛒'),
            ('makro', "Makro PRO", 'makro.pro', 'involve_asia', '14821', 0.040, 0.75, 'wholesale', '📦'),
            ('agoda', "Agoda", 'agoda.com', 'involve_asia', '8910', 0.085, 0.70, 'travel', '🏨'),
            ('trip', "Trip.com", 'trip.com', 'involve_asia', '9812', 0.070, 0.70, 'travel', '✈️'),
            ('central', "Central Online", 'central.co.th', 'accesstrade', '12300', 0.060, 0.70, 'department', '🏬'),
            ('bigc', "Big C Online", 'bigc.co.th', 'accesstrade', '10502', 0.040, 0.70, 'groceries', '🛍️'),
            ('advice', "Advice IT", 'advice.co.th', 'accesstrade', '13410', 0.025, 0.70, 'it_gadgets', '💻')
        ]
        cursor.executemany("""
        INSERT INTO affiliate_campaigns (store_key, store_name, domain, network, offer_id, commission_rate, cashback_share, category, icon)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, campaigns)

    conn.commit()
    conn.close()

# Pydantic Schemas for API
class NetworkConfigUpdate(BaseModel):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    webhook_secret: Optional[str] = None
    is_active: Optional[bool] = None

class CampaignUpdate(BaseModel):
    commission_rate: Optional[float] = None
    cashback_share: Optional[float] = None
    is_active: Optional[bool] = None

class PostbackPayload(BaseModel):
    network: str # 'accesstrade' or 'involve_asia'
    sub_id: str
    order_id: str
    store_name: Optional[str] = None
    sale_amount: float
    commission: float
    status: str = "pending" # 'pending', 'approved', 'cancelled'
    event_time: Optional[str] = None
