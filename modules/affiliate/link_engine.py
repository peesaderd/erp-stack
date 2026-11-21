import time
import uuid
import urllib.parse
from typing import Dict, Any, Optional
from .models import get_db

def generate_affiliate_link(user_code: str, original_url: str) -> Dict[str, Any]:
    """
    Transforms any raw shopping URL into an affiliate deep link with tracked Sub-ID.
    """
    raw_url = original_url.strip()
    if not raw_url.startswith("http"):
        raw_url = "https://" + raw_url

    conn = get_db()
    cursor = conn.cursor()

    # Find matching campaign by domain
    cursor.execute("SELECT * FROM affiliate_campaigns WHERE is_active = 1")
    campaigns = [dict(row) for row in cursor.fetchall()]

    matched = None
    # Intelligent domain and affiliate short-link detection
    if any(k in raw_url for k in ["atth.me", "s.shopee.co.th", "shope.ee", "shopee.co.th", "0041fn002a0a"]):
        cursor.execute("SELECT * FROM affiliate_campaigns WHERE store_key = 'shopee'")
        row = cursor.fetchone()
        if row: matched = dict(row)
    elif any(k in raw_url for k in ["7eleven", "allonline"]):
        cursor.execute("SELECT * FROM affiliate_campaigns WHERE store_key = '7eleven'")
        row = cursor.fetchone()
        if row: matched = dict(row)
    else:
        for camp in campaigns:
            if camp["domain"] in raw_url:
                matched = camp
                break

    # Fallback to Shopee if atth.me, else Lotus
    if not matched:
        target = "shopee" if "atth.me" in raw_url else "lotus"
        cursor.execute(f"SELECT * FROM affiliate_campaigns WHERE store_key = '{target}'")
        row = cursor.fetchone()
        if row: matched = dict(row)

    # Build unique sub_id: sb_{user_code}_{timestamp}_{hex}
    click_id = f"sb_{user_code}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    encoded_dest = urllib.parse.quote(raw_url, safe='')

    if "atth.me" in raw_url:
        sep = "&" if "?" in raw_url else "?"
        tracking_url = f"{raw_url}{sep}sub_id={click_id}"
    else:
        # Check if offer is a verified live campaign
        offer_id = matched.get("offer_id", "")
        is_live = offer_id and not offer_id.startswith("pending_") and offer_id not in ["10928", "10502", "12300", "13410", "14821", "8910", "9812"]

        if matched["network"] == "accesstrade":
            if is_live:
                tracking_url = f"https://click.accesstrade.in.th/adv.php?rk={offer_id}&sub_id={click_id}&url={encoded_dest}"
            else:
                sep = "&" if "?" in raw_url else "?"
                tracking_url = f"{raw_url}{sep}utm_source=smartback&aff_sub={click_id}"
        else: # Involve Asia
            if is_live:
                tracking_url = f"https://invol.co/aff_m?offer_id={offer_id}&aff_sub={click_id}&url={encoded_dest}"
            else:
                sep = "&" if "?" in raw_url else "?"
                tracking_url = f"{raw_url}{sep}utm_source=smartback&aff_sub={click_id}"

    # Log click to DB
    cursor.execute("""
    INSERT INTO clicks (click_id, user_code, store_key, original_url, tracking_url)
    VALUES (?, ?, ?, ?, ?)
    """, (click_id, user_code, matched["store_key"], raw_url, tracking_url))
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "click_id": click_id,
        "store_key": matched["store_key"],
        "store_name": matched["store_name"],
        "network": matched["network"],
        "commission_rate": matched["commission_rate"],
        "cashback_share": matched["cashback_share"],
        "estimated_cashback_pct": f"{round(matched['commission_rate'] * matched['cashback_share'] * 100, 2)}%",
        "original_url": raw_url,
        "tracking_url": tracking_url
    }
