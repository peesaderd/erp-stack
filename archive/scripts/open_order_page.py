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
        
        print("Opening Affiliate Order page in headed mode...")
        page.goto("https://seller-th.tiktok.com/affiliate/order?shop_region=TH")
        
        print("The browser is open. Please check what is displayed on your screen.")
        print("Waiting for 30 seconds before closing...")
        time.sleep(30)
        
        # Take a screenshot at the end
        page.screenshot(path="order_page_final.png")
        print("Saved order_page_final.png")
        
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
