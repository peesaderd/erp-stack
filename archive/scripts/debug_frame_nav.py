import os
import time
from playwright.sync_api import sync_playwright

def main():
    profile_dir = os.path.abspath(".tiktok_profile")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        # Log frame navigations
        page.on("framenavigated", lambda frame: print(f"Frame Navigated -> Name: '{frame.name}' | URL: {frame.url}"))
        
        # Log console messages
        page.on("console", lambda msg: print(f"Console: {msg.text}"))
        
        print("Navigating to Affiliate Order page...")
        try:
            page.goto("https://seller-th.tiktok.com/affiliate/order?shop_region=TH")
        except Exception as e:
            print(f"Main navigation error: {e}")
            
        # Wait 20 seconds to log all sub-frame navigations
        time.sleep(20)
        
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
