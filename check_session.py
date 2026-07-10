import os
from playwright.sync_api import sync_playwright

def main():
    profile_dir = os.path.abspath(".tiktok_profile")
    print(f"Loading persistent profile from: {profile_dir}")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        # Check Tab 1 (Seller Center TH)
        print("Checking Seller Center (TH)...")
        page.goto("https://seller-th.tiktok.com/homepage")
        page.wait_for_timeout(3000) # wait a bit for redirects
        print(f"Current Seller Center URL: {page.url}")
        print(f"Page Title: {page.title()}")
        
        # Take a screenshot to verify login state visually
        page.screenshot(path="seller_status.png")
        print("Saved seller_status.png")
        
        # Check Tab 2 (TikTok Creator Marketplace / TikTok Shop)
        print("\nChecking TikTok Shop Creator page...")
        page2 = context.new_page()
        page2.goto("https://shop.tiktok.com/")
        page2.wait_for_timeout(3000)
        print(f"Current Shop URL: {page2.url}")
        print(f"Page Title: {page2.title()}")
        
        page2.screenshot(path="shop_status.png")
        print("Saved shop_status.png")
        
        # Print cookies count
        cookies = context.cookies()
        print(f"\nNumber of cookies saved: {len(cookies)}")
        
        context.close()

if __name__ == "__main__":
    main()
