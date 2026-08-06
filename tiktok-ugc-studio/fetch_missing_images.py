"""Fetch product images from TikTok shop for products with empty images field."""
import asyncio, os, base64, json, sqlite3
from playwright.async_api import async_playwright

TUS_DB = "/home/openhands/erp-stack/tiktok-ugc-studio/tus_products.db"
IMAGE_DIR = "/home/openhands/erp-stack/tiktok-ugc-studio/storage/product_images"
os.makedirs(IMAGE_DIR, exist_ok=True)

async def fetch_images():
    conn = sqlite3.connect(TUS_DB)
    rows = conn.execute("SELECT product_id, url FROM tus_products WHERE (gender=\x27\x27 OR gender IS NULL) AND (images=\x27[]\x27 OR images IS NULL OR images=\x27\x27)").fetchall()
    print(f"Found {len(rows)} products missing images")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for product_id, url in rows:
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=20000)
                await page.wait_for_timeout(6000)
                imgs = await page.query_selector_all("img[src*=\x27ibyteimg\x27]")
                saved = []
                for i, img in enumerate(imgs[:3]):
                    src = await img.get_attribute("src")
                    if not src:
                        continue
                    js_code = """
                    async () => {
                        const resp = await fetch("PLACEHOLDER_SRC");
                        const blob = await resp.blob();
                        return await new Promise((resolve, reject) => {
                            const fr = new FileReader();
                            fr.onload = () => resolve(fr.result.split(",")[1]);
                            fr.readAsDataURL(blob);
                        });
                    }
                    """.replace("PLACEHOLDER_SRC", src)
                    try:
                        b64 = await page.evaluate(js_code)
                        if b64:
                            fname = f"{product_id}_{i}.jpeg"
                            fpath = os.path.join(IMAGE_DIR, fname)
                            with open(fpath, "wb") as f:
                                f.write(base64.b64decode(b64))
                            saved.append(f"/tiktok/storage/product_images/{fname}")
                            print(f"OK {product_id}_{i} ({os.path.getsize(fpath)} bytes)")
                    except Exception as e:
                        print(f"  fetch fail {product_id}_{i}: {e}")
                if saved:
                    conn.execute("UPDATE tus_products SET images=? WHERE product_id=?", (json.dumps(saved), product_id))
                    conn.commit()
                    print(f"UPDATED {product_id}: {saved}")
                else:
                    print(f"NO IMAGES for {product_id}")
            except Exception as e:
                print(f"FAIL {product_id}: {e}")
            await page.close()
        await browser.close()
    conn.close()

asyncio.run(fetch_images())
