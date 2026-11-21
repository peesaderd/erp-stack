import sqlite3
import os
import uuid
from datetime import datetime

DB_PATH = os.environ.get("SMARTBACK_DB_PATH", "/home/openhands/smartback_backend/smartback.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        promptpay_id TEXT,
        provider TEXT DEFAULT 'guest', -- 'line', 'google', 'guest'
        provider_id TEXT,
        avatar_url TEXT,
        token TEXT,
        vip_tier TEXT DEFAULT 'VIP Gold',
        bonus_multiplier REAL DEFAULT 1.2,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Check and add columns if upgrading existing table
    cursor.execute("PRAGMA table_info(users)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    for col_name, col_type in [
        ("email", "TEXT"),
        ("provider", "TEXT DEFAULT 'guest'"),
        ("provider_id", "TEXT"),
        ("avatar_url", "TEXT"),
        ("token", "TEXT"),
        ("last_login", "TEXT")
    ]:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                print(f"Column {col_name} alter notice: {e}")

    # 2. Clicks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clicks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        click_id TEXT UNIQUE NOT NULL,
        user_code TEXT NOT NULL,
        store_key TEXT NOT NULL,
        original_url TEXT NOT NULL,
        tracking_url TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Cashback Orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cashback_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT UNIQUE NOT NULL,
        user_code TEXT NOT NULL,
        store_name TEXT NOT NULL,
        order_amount REAL NOT NULL,
        commission_total REAL NOT NULL,
        cashback_rate REAL NOT NULL,
        cashback_amount REAL NOT NULL,
        our_profit REAL NOT NULL,
        status TEXT NOT NULL, -- 'pending', 'approved', 'rejected'
        network TEXT DEFAULT 'involve_asia',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Withdrawals table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref_code TEXT UNIQUE NOT NULL,
        user_code TEXT NOT NULL,
        promptpay_id TEXT NOT NULL,
        amount REAL NOT NULL,
        status TEXT NOT NULL, -- 'completed', 'pending'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # --- Seed Default User: user_pw_9821 (คุณพีรวัฒน์) ---
    cursor.execute("SELECT id FROM users WHERE user_code = 'user_pw_9821'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO users (user_code, name, phone, email, promptpay_id, provider, avatar_url, token, vip_tier, bonus_multiplier)
        VALUES ('user_pw_9821', 'คุณพีรวัฒน์', '089-123-4567', 'peerawat@example.com', '089-123-4567', 'guest', 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150', 'tok_pw_9821', 'VIP Gold (1.2x)', 1.2)
        """)

        # Seed Initial Historical Transactions
        cursor.execute("""
        INSERT INTO cashback_orders (order_id, user_code, store_name, order_amount, commission_total, cashback_rate, cashback_amount, our_profit, status, network, notes, created_at)
        VALUES 
        ('ORD-LTS-9811', 'user_pw_9821', "Lotus's Online", 1150.00, 69.00, 4.5, 51.75, 17.25, 'approved', 'accesstrade', 'ของสดและของใช้ในบ้าน', datetime('now', '-2 days')),
        ('ORD-MKR-4420', 'user_pw_9821', "Makro PRO", 2450.00, 98.00, 3.0, 73.50, 24.50, 'approved', 'involve_asia', 'สั่งวัตถุดิบและของใช้ยกลัง', datetime('now', '-1 days')),
        ('ORD-AGD-1029', 'user_pw_9821', "Agoda", 16500.00, 1800.00, 8.0, 1324.75, 475.25, 'approved', 'involve_asia', 'ทริปเชียงใหม่ 4 วัน 3 คืน', datetime('now', '-15 days')),
        ('ORD-AGD-5512', 'user_pw_9821', "Agoda", 4200.00, 450.00, 8.0, 336.00, 114.00, 'pending', 'involve_asia', 'จองโรงแรมพัทยา 2 คืน', datetime('now', '-2 hours')),
        ('ORD-LTS-6632', 'user_pw_9821', "Lotus's Online", 3780.00, 380.00, 7.5, 284.00, 96.00, 'pending', 'accesstrade', 'สั่งของกินของใช้รอบสุดสัปดาห์', datetime('now', '-5 hours'))
        """)

    # --- Seed Sample LINE User: user_line_somchai ---
    cursor.execute("SELECT id FROM users WHERE user_code = 'user_line_somchai'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO users (user_code, name, phone, email, promptpay_id, provider, provider_id, avatar_url, token, vip_tier, bonus_multiplier)
        VALUES (
            'user_line_somchai', 
            'คุณสมชาย ช้อปเพลิน (LINE)', 
            '081-998-7766', 
            'somchai.line@smartback.me', 
            '081-998-7766', 
            'line', 
            'U9821387654129', 
            'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150', 
            'tok_line_somchai_2026', 
            'VIP Platinum (1.5x)', 
            1.5
        )
        """)
        # Seed LINE user orders
        cursor.execute("""
        INSERT INTO cashback_orders (order_id, user_code, store_name, order_amount, commission_total, cashback_rate, cashback_amount, our_profit, status, network, notes, created_at)
        VALUES 
        ('ORD-LN-001', 'user_line_somchai', "Lotus's Online", 2890.00, 158.95, 5.5, 127.16, 31.79, 'approved', 'accesstrade', 'ซื้อของเข้าบ้านผ่าน LINE', datetime('now', '-3 days')),
        ('ORD-LN-002', 'user_line_somchai', "Agoda", 12500.00, 1062.50, 8.5, 850.00, 212.50, 'approved', 'involve_asia', 'จองรีสอร์ทหัวหิน', datetime('now', '-7 days')),
        ('ORD-LN-003', 'user_line_somchai', "Makro PRO", 4200.00, 168.00, 4.0, 134.40, 33.60, 'pending', 'involve_asia', 'วัตถุดิบทำขนมยกลัง', datetime('now', '-4 hours'))
        """)

    # --- Seed Sample Google User: user_google_somchai ---
    cursor.execute("SELECT id FROM users WHERE user_code = 'user_google_somchai'")
    if not cursor.fetchone():
        cursor.execute("""
        INSERT INTO users (user_code, name, phone, email, promptpay_id, provider, provider_id, avatar_url, token, vip_tier, bonus_multiplier)
        VALUES (
            'user_google_somchai', 
            'Somchai Shopkru (Google)', 
            '086-554-3322', 
            'somchai.shopkru@gmail.com', 
            '086-554-3322', 
            'google', 
            '1098237192837465', 
            'https://images.unsplash.com/photo-1570295999919-56ceb5ecca61?w=150', 
            'tok_google_somchai_2026', 
            'VIP Diamond (2.0x)', 
            2.0
        )
        """)
        # Seed Google user orders
        cursor.execute("""
        INSERT INTO cashback_orders (order_id, user_code, store_name, order_amount, commission_total, cashback_rate, cashback_amount, our_profit, status, network, notes, created_at)
        VALUES 
        ('ORD-GG-001', 'user_google_somchai', "Advice IT", 24900.00, 622.50, 2.5, 498.00, 124.50, 'approved', 'accesstrade', 'ซื้อจอคอมพิวเตอร์และอุปกรณ์ไอที', datetime('now', '-5 days')),
        ('ORD-GG-002', 'user_google_somchai', "Trip.com", 8500.00, 595.00, 7.0, 476.00, 119.00, 'approved', 'involve_asia', 'ตั๋วเครื่องบินไป-กลับภูเก็ต', datetime('now', '-10 days')),
        ('ORD-GG-003', 'user_google_somchai', "Lotus's Online", 1850.00, 101.75, 5.5, 81.40, 20.35, 'pending', 'accesstrade', 'ของใช้ทั่วไป', datetime('now', '-1 hours'))
        """)

    conn.commit()
    conn.close()
    print("Database schema checked and initialized at", DB_PATH)

if __name__ == '__main__':
    init_db()
