import os
import sys
from playwright.sync_api import sync_playwright

PROFILES_DIR = os.path.abspath("browser_profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)

def open_browser(platform):
    profile_dir = os.path.join(PROFILES_DIR, platform)
    print(f"Opening browser for '{platform}'...")
    print(f"Profile directory: {profile_dir}")
    print("\n[ACTION REQUIRED] Please log in to your account in the browser window.")
    print("Once logged in, simply close the browser window. The session will be saved automatically.")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        # Guide URLs for easy login
        urls = {
            "tiktok": "https://www.tiktok.com/login",
            "facebook": "https://www.facebook.com/",
            "youtube": "https://studio.youtube.com/",
            "pinterest": "https://www.pinterest.com/login/",
            "x": "https://x.com/login",
            "instagram": "https://www.instagram.com/",
            "threads": "https://www.threads.net/login",
            "linkedin": "https://www.linkedin.com/login",
            "shopee": "https://creator.shopee.co.th/"
        }
        
        target_url = urls.get(platform, "https://www.google.com")
        page.goto(target_url)
        
        # Loop to keep the browser open until user manually closes the window
        while True:
            try:
                page.wait_for_timeout(1000)
                if not context.pages or len(context.pages) == 0:
                    break
            except Exception:
                break
                
        print(f"\n[SUCCESS] Session saved for {platform}!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python open_profile.py <platform>")
        print("Available platforms: facebook, tiktok, youtube, pinterest, x, instagram, threads, linkedin, shopee")
        sys.exit(1)
        
    open_browser(sys.argv[1].lower())
