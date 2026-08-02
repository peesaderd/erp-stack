import os
import time
from playwright.sync_api import sync_playwright

def main():
    profile_dir = os.path.abspath(".tiktok_profile")
    print(f"Using profile: {profile_dir}")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,  # Headed mode to avoid anti-bot
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navigating to Affiliate Order page...")
        page.goto("https://seller-th.tiktok.com/affiliate/order?shop_region=TH")
        
        # Wait a long time (25 seconds) to make sure it loads everything
        print("Waiting 25 seconds for all APIs and components to load...")
        time.sleep(25)
        
        print(f"Final URL: {page.url}")
        
        # Take screenshot
        page.screenshot(path="order_page_debug.png")
        print("Saved order_page_debug.png")
        
        # Extract all visible text on the page
        visible_text = page.evaluate("() => document.body.innerText")
        print("\n=== Visible Text on Page ===")
        print(visible_text)
        print("============================\n")
        
        context.close()

if __name__ == "__main__":
    main()
