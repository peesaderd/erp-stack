import os
import sys
import json
import time
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
        
    urls_to_test = [
        "https://seller-th.tiktok.com/affiliate/order?shop_region=TH",
        "https://seller-th.tiktok.com/connection/affiliate/order?shop_region=TH",
        "https://seller-th.tiktok.com/affiliate/order",
        "https://seller-th.tiktok.com/connection/affiliate/order"
    ]
    
    with sync_playwright() as p:
        context = p.firefox.launch_persistent_context(
            user_data_dir=os.path.abspath(".firefox_scratch_test"),
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
        )
        context.add_cookies(cookies)
        page = context.pages[0] if context.pages else context.new_page()
        
        for idx, url in enumerate(urls_to_test):
            print(f"\n[{idx}] Navigating to: {url}")
            try:
                page.goto(url)
                page.wait_for_timeout(10000)  # Wait 10s for page load & redirect
                print(f"  -> Current URL: {page.url}")
                print(f"  -> Title: {page.title()}")
                
                # Check for iframes
                iframes = page.frames
                print(f"  -> Number of frames: {len(iframes)}")
                for f_idx, f in enumerate(iframes):
                    print(f"     Frame {f_idx}: Name='{f.name}', URL='{f.url[:120]}'")
                    
                # Take screenshot
                safe_name = url.replace("https://", "").replace("/", "_").replace(":", "_").replace("?", "_")
                page.screenshot(path=f"test_nav_{safe_name}.png")
                print(f"  -> Saved test_nav_{safe_name}.png")
            except Exception as e:
                print(f"  -> Error: {e}")
                
        context.close()

if __name__ == "__main__":
    main()
