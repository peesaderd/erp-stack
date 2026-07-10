import os
import sys
import time
from playwright.sync_api import sync_playwright

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    profile_dir = os.path.abspath(".tiktok_profile")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        # Listen for request failures
        page.on("requestfailed", lambda req: print(f"Request Failed: {req.url} | Error: {req.failure}"))
        
        # Listen for frame navigations
        page.on("framenavigated", lambda frame: print(f"Frame Navigated -> URL: {frame.url}"))
        
        print("Navigating to Affiliate Order page...")
        page.goto("https://seller-th.tiktok.com/affiliate/order?shop_region=TH")
        
        time.sleep(20)
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
