import os
import sys
import time
from playwright.sync_api import sync_playwright

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    profile_dir = os.path.abspath(".firefox_tiktok_profile")
    print(f"Loading persistent Firefox profile from: {profile_dir}")
    
    with sync_playwright() as p:
        context = p.firefox.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navigating to Affiliate Order page...")
        page.goto("https://seller-th.tiktok.com/affiliate/order?shop_region=TH")
        time.sleep(15)
        
        # Print details safely
        try:
            print(f"Final URL: {page.url}")
        except Exception as e:
            print(f"Failed to get URL: {e}")
            
        try:
            print(f"Title: {page.title()}")
        except Exception as e:
            print(f"Failed to get title: {e}")
            
        try:
            page.screenshot(path="firefox_order_debug.png")
            print("Saved firefox_order_debug.png")
        except Exception as e:
            print(f"Failed to save screenshot: {e}")
        
        visible_text = page.evaluate("() => document.body.innerText")
        print("\n=== Visible Text on Page ===")
        print(visible_text[:1500])  # print first 1500 characters
        print("============================\n")
        
        context.close()

if __name__ == "__main__":
    main()
