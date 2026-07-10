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
        
        # Test paths starting with /affiliate/
        urls_to_test = [
            "https://seller-th.tiktok.com/affiliate/homepage",
            "https://seller-th.tiktok.com/affiliate/order",
            "https://seller-th.tiktok.com/affiliate/plan",
            "https://seller-th.tiktok.com/affiliate/creator",
            "https://seller-th.tiktok.com/affiliate/dashboard",
            "https://seller-th.tiktok.com/affiliate/collaboration"
        ]
        
        for url in urls_to_test:
            print(f"\nNavigating directly to: {url}")
            try:
                page.goto(url)
                time.sleep(8)
                print(f"Result URL: {page.url}")
                print(f"Title: {page.title()}")
                
                # Take screenshot
                safe_name = url.replace("https://", "").replace("/", "_").replace(":", "_")
                page.screenshot(path=f"nav_new_{safe_name}.png")
                print(f"Saved nav_new_{safe_name}.png")
            except Exception as e:
                print(f"Failed to navigate to {url}: {e}")
                
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
