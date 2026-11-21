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
    for camp in campaigns:
        if camp["domain"] in raw_url:
            matched = camp
            break

    # Fallback to Lotus's if domain not matched directly
    if not matched:
        cursor.execute("SELECT * FROM affiliate_campaigns WHERE store_key = 'lotus'")
        matched = dict(cursor.fetchone())

    # Build unique sub_id: sb_{user_code}_{timestamp}_{hex}
    click_id = f"sb_{user_code}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    encoded_dest = urllib.parse.quote(raw_url, safe='')

    if matched["network"] == "accesstrade":
        tracking_url = f"https://click.accesstrade.in.th/adv.php?rk={matched['offer_id']}&sub_id={click_id}&url={encoded_dest}"
    else: # Involve Asia
        tracking_url = f"https://invol.co/aff_m?offer_id={matched['offer_id']}&aff_sub={click_id}&url={encoded_dest}"

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
