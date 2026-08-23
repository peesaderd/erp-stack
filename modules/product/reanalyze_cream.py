"""Re-analyze the 5 cream products from tmp_cream_import.json using the NEW
4-field enrichment (body_part / usage_howto / special_target / ingredient_highlight).

Reads raw Apify items -> analyze_product (Mistral) -> store_analyzed (persists new cols).
"""
import asyncio, json, sys, os
sys.path.insert(0, "/home/openhands/erp-stack/modules")

from product.analyze_pipeline import analyze_product
from product.analyzer_db import store_analyzed


async def run():
    with open("/home/openhands/erp-stack/modules/product/.tmp_cream_import.json") as f:
        items = json.load(f)

    print(f"พบสินค้าในไฟล์: {len(items)} ตัว")
    print("=" * 90)

    for it in items:
        pid = it.get("productId", "?")
        title = (it.get("title") or "")[:50]
        print(f"\n▶ วิเคราะห์: {pid}\n   {title}")

        try:
            result = await analyze_product(it, "apify")
            products = result.get("products", [])
            if not products:
                print("   ⚠️ ไม่มี products output")
                continue
            prod = products[0]

            # store_analyzed ใช้ hasattr(AnalyzedProduct, k) -> field ใหม่บันทึกได้ (column migrate แล้ว)
            saved = await store_analyzed(prod)
            print(f"   ✅ บันทึกแล้ว (id={saved})")
            print(f"   gender        : {prod.get('gender','')}")
            print(f"   target_age    : {prod.get('target_age','')}")
            print(f"   body_part     : {prod.get('body_part','(ว่าง)')}")
            print(f"   usage_howto   : {prod.get('usage_howto','(ว่าง)')}")
            print(f"   special_target: {prod.get('special_target','(ว่าง)')}")
            print(f"   ingredient    : {prod.get('ingredient_highlight','(ว่าง)')}")
            print(f"   hashtags      : {prod.get('hashtags','')}")
        except Exception as e:
            print(f"   ❌ error: {e}")


if __name__ == "__main__":
    asyncio.run(run())
