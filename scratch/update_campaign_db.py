import sqlite3
import os

DB_PATH = "/home/openhands/smartback_backend/smartback.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. Add or Update Shopee with user's AccessTrade campaign
cursor.execute("SELECT id FROM affiliate_campaigns WHERE store_key = 'shopee'")
if cursor.fetchone():
    cursor.execute("""
    UPDATE affiliate_campaigns 
    SET offer_id = '0041fn002a0a', network = 'accesstrade', commission_rate = 0.050, cashback_share = 0.70, is_active = 1
    WHERE store_key = 'shopee'
    """)
else:
    cursor.execute("""
    INSERT INTO affiliate_campaigns (store_key, store_name, domain, network, offer_id, commission_rate, cashback_share, category, icon, is_active)
    VALUES ('shopee', 'Shopee Thailand', 'shopee.co.th', 'accesstrade', '0041fn002a0a', 0.050, 0.70, 'ecommerce', '🧡', 1)
    """)

# 2. Add or Update 7-Eleven ALL ONLINE with AccessTrade
cursor.execute("SELECT id FROM affiliate_campaigns WHERE store_key = '7eleven'")
if cursor.fetchone():
    cursor.execute("""
    UPDATE affiliate_campaigns 
    SET offer_id = '0041fn002a0a', network = 'accesstrade', commission_rate = 0.050, cashback_share = 0.70, is_active = 1
    WHERE store_key = '7eleven'
    """)
else:
    cursor.execute("""
    INSERT INTO affiliate_campaigns (store_key, store_name, domain, network, offer_id, commission_rate, cashback_share, category, icon, is_active)
    VALUES ('7eleven', '7-Eleven (ALL ONLINE)', '7eleven.co.th', 'accesstrade', '0041fn002a0a', 0.050, 0.70, 'convenience', '🏪', 1)
    """)

conn.commit()

cursor.execute("SELECT store_key, store_name, domain, network, offer_id, commission_rate FROM affiliate_campaigns WHERE is_active = 1")
print("Active Campaigns:")
for row in cursor.fetchall():
    print(row)

conn.close()
