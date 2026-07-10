import os
import time
from playwright.sync_api import sync_playwright

def main():
    profile_dir = os.path.abspath(".tiktok_profile")
    print(f"Loading persistent profile from: {profile_dir}")
    
    with sync_playwright() as p:
        # Launch Chromium in headed mode (visible to user)
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Opening TikTok Shop Seller Center in HEADED mode...")
        page.goto("https://seller-th.tiktok.com/homepage")
        
        print("Browser window is visible. Please check if you are logged in automatically.")
        print("Waiting for 15 seconds before closing...")
        time.sleep(15)
        
        context.close()
        print("Browser closed.")

if __name__ == "__main__":
    main()
