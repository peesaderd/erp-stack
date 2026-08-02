import os
import sys
import json
import shutil
from playwright.sync_api import sync_playwright

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    cookies_file = os.path.abspath("cookies.json")
    if not os.path.exists(cookies_file):
        print(f"Error: {cookies_file} not found!")
        sys.exit(1)
        
    with open(cookies_file, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
        
    profile_dir = os.path.abspath(".firefox_scratch_compass")
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
        except Exception:
            pass
            
    with sync_playwright() as p:
        print("Launching Firefox...")
        context = p.firefox.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            viewport={"width": 1920, "height": 1080}
        )
        context.add_cookies(cookies)
        page = context.pages[0] if context.pages else context.new_page()
        
        # Intercept and log all APIs to find product ranking or market trends APIs
        captured_data = []
        def handle_response(response):
            try:
                url = response.url
                if "api" in url or "graphql" in url or "rpc" in url:
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        status = response.status
                        try:
                            res_json = response.json()
                            print(f"Intercepted: {status} | {url[:90]}")
                            captured_data.append({
                                "url": url,
                                "status": status,
                                "data": res_json
                            })
                        except Exception:
                            pass
            except Exception:
                pass
        context.on("response", handle_response)
        
        # Target the Data Compass Product Analytics or Market Analysis page
        # In Seller Center, the Analytics URL is typically:
        # https://seller-th.tiktok.com/compass/market/product-rank
        # or similar. Let's try some common URLs!
        urls_to_try = [
            "https://seller-th.tiktok.com/compass/market/product-rank?shop_region=TH",
            "https://seller-th.tiktok.com/compass/product/ranking?shop_region=TH",
            "https://seller-th.tiktok.com/compass/market-analysis?shop_region=TH"
        ]
        
        for idx, url in enumerate(urls_to_try):
            print(f"\nNavigating to {url}...")
            try:
                page.goto(url)
                page.wait_for_timeout(10000)
                
                # Take screenshot
                page.screenshot(path=f"compass_try_{idx}.png")
                print(f"Saved compass_try_{idx}.png")
                
                # Print page title and text
                print(f"Title: {page.title()}")
                print(f"Current URL: {page.url}")
                visible_text = page.evaluate("() => document.body.innerText")
                print("Text snippet (first 1000 chars):")
                print(visible_text[:1000])
                print("-" * 50)
            except Exception as e:
                print(f"Error navigating: {e}")
                
        with open("compass_captured.json", "w", encoding="utf-8") as f_out:
            json.dump(captured_data, f_out, indent=4, ensure_ascii=False)
            
        context.close()

if __name__ == "__main__":
    main()
