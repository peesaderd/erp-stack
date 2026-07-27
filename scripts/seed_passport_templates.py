"""Seed passport templates into Schema Engine"""
import requests

templates = [
    ("us_passport", "US Passport", "United States", "passport", 51, 51, "#FFFFFF", 300, 0.7),
    ("us_visa", "US Visa", "United States", "visa", 51, 51, "#FFFFFF", 300, 0.7),
    ("uk_passport", "UK Passport", "United Kingdom", "passport", 35, 45, "#FFFFFF", 300, 0.65),
    ("eu_passport", "EU Passport", "European Union", "passport", 35, 45, "#FFFFFF", 300, 0.65),
    ("thai_passport", "หนังสือเดินทางไทย", "Thailand", "passport", 45, 35, "#FFFFFF", 300, 0.65),
    ("thai_id", "บัตรประชาชนไทย", "Thailand", "id_card", 86, 54, "#FFFFFF", 300, 0.6),
    ("japan_passport", "Japan Passport", "Japan", "passport", 45, 35, "#FFFFFF", 300, 0.65),
    ("japan_visa", "Japan Visa", "Japan", "visa", 45, 45, "#FFFFFF", 300, 0.65),
    ("korea_passport", "Korea Passport", "South Korea", "passport", 35, 45, "#FFFFFF", 300, 0.65),
    ("china_passport", "China Passport", "China", "passport", 33, 48, "#FFFFFF", 300, 0.6),
    ("china_visa", "China Visa", "China", "visa", 33, 48, "#FFFFFF", 300, 0.6),
    ("india_passport", "India Passport", "India", "passport", 35, 35, "#FFFFFF", 300, 0.7),
    ("australia_passport", "Australia Passport", "Australia", "passport", 35, 45, "#FFFFFF", 300, 0.65),
    ("canada_passport", "Canada Passport", "Canada", "passport", 50, 70, "#FFFFFF", 300, 0.6),
    ("vietnam_passport", "Vietnam Passport", "Vietnam", "passport", 40, 60, "#FFFFFF", 300, 0.65),
    ("myanmar_passport", "Myanmar Passport", "Myanmar", "passport", 40, 60, "#FFFFFF", 300, 0.65),
    ("laos_passport", "Laos Passport", "Laos", "passport", 40, 60, "#FFFFFF", 300, 0.65),
    ("cambodia_passport", "Cambodia Passport", "Cambodia", "passport", 40, 60, "#FFFFFF", 300, 0.65),
    ("singapore_passport", "Singapore Passport", "Singapore", "passport", 35, 45, "#FFFFFF", 300, 0.65),
    ("malaysia_passport", "Malaysia Passport", "Malaysia", "passport", 35, 50, "#FFFFFF", 300, 0.65),
    ("indonesia_passport", "Indonesia Passport", "Indonesia", "passport", 35, 45, "#FFFFFF", 300, 0.65),
    ("philippines_passport", "Philippines Passport", "Philippines", "passport", 35, 45, "#FFFFFF", 300, 0.65),
    ("germany_id", "Germany ID Card", "Germany", "id_card", 86, 54, "#FFFFFF", 300, 0.6),
    ("france_id", "France ID Card", "France", "id_card", 86, 54, "#FFFFFF", 300, 0.6),
    ("hongkong_id", "Hong Kong ID Card", "Hong Kong", "id_card", 86, 54, "#FFFFFF", 300, 0.6),
]

ok = 0
fail = 0
for code, name, country, doc_type, w, h, bg, dpi, head_pct in templates:
    payload = {
        "code": code, "name": name, "country": country,
        "doc_type": doc_type, "width_mm": w, "height_mm": h,
        "bg_color": bg, "dpi": dpi, "head_height_pct": head_pct,
        "active": True,
    }
    r = requests.post("http://localhost:8100/api/v1/data/passport_template", json=payload)
    data = r.json()
    if data.get("success"):
        ok += 1
        print(f"  ✅ {code:25s} {name}")
    else:
        fail += 1
        print(f"  ❌ {code:25s} {data.get('error','')}")

print(f"\n✅ {ok} seeded | ❌ {fail} failed")
