import os
import sys
import json
import shutil
from playwright.sync_api import sync_playwright

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    cookies_file = os.path.abspath("shopee_cookies.json")
    if not os.path.exists(cookies_file):
        print(f"Error: {cookies_file} not found!")
        sys.exit(1)
        
    with open(cookies_file, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
        
    print(f"Loaded {len(cookies)} Shopee cookies.")
    
    profile_dir = os.path.abspath(".firefox_scratch_shopee")
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
        except Exception:
            pass
            
    with sync_playwright() as p:
        print("Launching Firefox in HEADLESS mode...")
        context = p.firefox.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            viewport={"width": 1920, "height": 1080}
        )
        context.add_cookies(cookies)
        
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
                            print(f"Intercepted Shopee API: {status} | {url[:90]}")
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
        
        page = context.pages[0] if context.pages else context.new_page()
        
        # Navigate to Shopee Seller Center
        print("Navigating to Shopee Seller Center...")
        page.goto("https://seller.shopee.co.th/")
        
        print("Waiting 20 seconds for dashboard to load...")
        page.wait_for_timeout(20000)
        
        # Take screenshot
        screenshot_path = "shopee_seller_center_result.png"
        page.screenshot(path=screenshot_path)
        print(f"Saved {screenshot_path}")
        
        # Print visible text
        visible_text = page.evaluate("() => document.body.innerText")
        print("\n=== Visible Text on Shopee Seller Center ===")
        print(visible_text[:2000])
        print("============================================\n")
        
        # Save captured data
        with open("captured_shopee_api.json", "w", encoding="utf-8") as f_out:
            json.dump(captured_data, f_out, indent=4, ensure_ascii=False)
        print(f"Saved {len(captured_data)} Shopee API responses to captured_shopee_api.json")
        
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
