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
        
        # Check TikTok.com
        print("Checking TikTok.com...")
        page.goto("https://www.tiktok.com/")
        page.wait_for_timeout(5000)
        print(f"Current TikTok URL: {page.url}")
        print(f"Page Title: {page.title()}")
        
        # Take screenshot
        page.screenshot(path="tiktok_com_status.png")
        print("Saved tiktok_com_status.png")
        
        # Print cookies count
        cookies = context.cookies()
        print(f"Number of cookies saved: {len(cookies)}")
        for c in cookies[:10]: # print first 10 cookies
            print(f"- {c['name']} (domain: {c['domain']})")
            
        context.close()

if __name__ == "__main__":
    main()
