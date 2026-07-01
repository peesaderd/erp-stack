"""
content_gen.py — AI สร้าง Content ด้วย OpenCode API
- Caption ไทย/อังกฤษ
- Script review
- ข้อความ affiliate
- Hashtags
"""

import json
import requests
import re
from pathlib import Path
from datetime import datetime

# OpenCode API
OPENCODE_API = "https://api.opencode.ai/v1/chat/completions"
API_KEY = "sk-LTP...ngi0"  # TODO: load from config.json
MODEL = "opencode-go/deepseek-v4-flash"


def _call_opencode(prompt, system_prompt=None):
    """เรียก OpenCode API"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            OPENCODE_API,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": messages,
                "max_tokens": 1000,
                "temperature": 0.8,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            print(f"⚠️ OpenCode API error: {resp.status_code} {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ OpenCode API call failed: {e}")
        return None


def generate_caption(product, language="thai+english"):
    """
    สร้าง caption สำหรับโพสต์
    product: dict เช่น {product_name, price, description, rating, category}
    """
    system_prompt = f"""คุณคือ Content Creator ไทย ที่เชี่ยวชาญการเขียนโพสต์ขายของบน Social Media
เขียน Caption ให้สั้น กระชับ ดึงดูดความสนใจ ใช้ภาษาไทยปนอังกฤษได้ (ตามสไตล์คนไทย)
ความยาว 100-150 คำ มี Emoji เล็กน้อย ลงท้ายด้วย Call to Action (เช่น สั่งเลย! ลิงก์ใน Bio)"""

    prompt = f"""
Product: {product.get('product_name', '')}
Price: {product.get('price', '')} {product.get('currency', 'THB')}
Category: {product.get('category', '')}
Description: {product.get('description', '')}
Rating: {product.get('rating', '')}/5
Sold: {product.get('sold_count', 0)} ชิ้น

สร้าง Caption ขายของ ภาษาไทย+อังกฤษ
"""

    result = _call_opencode(prompt, system_prompt)
    return result or _caption_fallback(product)


def generate_review_script(product, style="honest"):
    """
    สร้างสคริปต์รีวิวสินค้า (สำหรับวิดีโอ)
    style: honest / funny / luxury / educational
    """
    system_prompt = f"""คุณคือ Creator TikTok ที่รีวิวสินค้าจริงใจ
เขียนสคริปต์รีวิวความยาว 30-45 วินาที (50-80 คำ)
มี Hook น่าสนใจ, ประสบการณ์ใช้จริง, ข้อดี, แล้ว Call to Action"""

    prompt = f"""
Product: {product.get('product_name', '')}
Price: {product.get('price', '')} {product.get('currency', 'THB')}
Description: {product.get('description', '')}
Style: {style}

เขียนสคริปต์รีวิว:
"""

    result = _call_opencode(prompt, system_prompt)
    return result or _script_fallback(product)


def generate_hashtags(product, count=5):
    """สร้าง hashtags ที่เกี่ยวข้อง"""
    prompt = f"""Generate {count} hashtags for this product (mix English and Thai):
Product: {product.get('product_name', '')}
Category: {product.get('category', '')}

Return ONLY the hashtags, separated by spaces, no numbers."""
    
    result = _call_opencode(prompt)
    if result:
        tags = result.strip().split()
        tags = [t for t in tags if t.startswith("#")]
        return " ".join(tags[:count])
    return "#สินค้าดี #รีวิวสินค้า #ของดีบอกต่อ #affiliate #productreview"


def generate_affiliate_caption(product):
    """สร้างข้อความ Affiliate สั้นๆ"""
    prompt = f"""สร้างข้อความ Affiliate ขาย {product.get('product_name', '')}
สั้นๆ 1 ประโยค + แฮชแท็ก 3 อัน"""
    result = _call_opencode(prompt)
    return result or f"🔥 {product.get('product_name', '')} ราคา{product.get('price', '')}.- ห้ามพลาด! #affiliate"


def translate_mixed(text, target_lang="thai"):
    """แปลข้อความ/ผสมภาษา"""
    prompt = f"""Translate this text to {target_lang}. Keep any brand names English.
Text: {text}"""
    result = _call_opencode(prompt)
    return result or text


# ─── Fallbacks (เมื่อ AI ไม่ตอบ) ─────────────────────────

def _caption_fallback(product):
    name = product.get("product_name", "สินค้าชิ้นนี้")
    price = product.get("price", "")
    return (
        f"🔥 {name} มาถึงแล้ว! คุณภาพดี ราคาแค่ {price}.- เท่านั้น!\n"
        f"📍 รีวิวโดยทีมงาน ลองแล้วชอบจริง\n"
        f"👇 สั่งเลย! ลิงก์ใน Bio หรือ DM สอบถาม\n\n"
        f"#productreview #{_category_tag(product.get('category', ''))} #ของดีบอกต่อ"
    )

def _script_fallback(product):
    name = product.get("product_name", "สินค้าชิ้นนี้")
    return (
        f"สวัสดีครับ! วันนี้จะมารีวิว {name} ให้ดูกัน\n"
        f"ของจริงน้าา ใช้มาหลายวันแล้ว ดีจริง!\n\n"
        f"ตัวนี้ {product.get('description', '')[:80]}...\n"
        f"ราคาแค่ {product.get('price', '')}.- ถือว่าคุ้มมาก\n"
        f"ใครสนใจสั่งผ่านลิงก์ใน Bio ได้เลยครับ 🔥"
    )

def _category_tag(category):
    tags = {"skincare": "สกินแคร์", "beauty": "ความงาม", "gadget": "แกดเจ็ต", "lifestyle": "ไลฟ์สไตล์", "food": "อาหาร"}
    return tags.get(category, "สินค้าดี")


# ─── Main Test ────────────────────────────────────────────

def main():
    print("🧪 Content Gen Test\n")

    mock_product = {
        "product_name": "เซรั่มบำรุงผิวหน้า Vitamin C",
        "price": 299,
        "currency": "THB",
        "description": "เซรั่มวิตามินซีเข้มข้น ลดจุดด่างดำ กระจ่างใสใน 7 วัน",
        "category": "skincare",
        "rating": 4.5,
        "sold_count": 15200,
    }

    print("📝 Caption:")
    caption = generate_caption(mock_product)
    print(caption or "[fallback]")
    print()

    print("🎬 Review Script:")
    script = generate_review_script(mock_product)
    print(script or "[fallback]")
    print()

    print("#️⃣ Hashtags:")
    print(generate_hashtags(mock_product))
    print()

    print("🔗 Affiliate:")
    print(generate_affiliate_caption(mock_product))


if __name__ == "__main__":
    main()
