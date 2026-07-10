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
        
        # Test navigation to affiliate.tiktok.com
        print("Navigating to affiliate.tiktok.com...")
        try:
            page.goto("https://affiliate.tiktok.com/")
            time.sleep(10)
            print(f"Result URL: {page.url}")
            print(f"Title: {page.title()}")
            page.screenshot(path="affiliate_tiktok_com.png")
            print("Saved affiliate_tiktok_com.png")
            
            # Print visible text
            visible_text = page.evaluate("() => document.body.innerText")
            print("\n=== Visible Text ===")
            print(visible_text[:1000])
        except Exception as e:
            print(f"Error navigating: {e}")
            
        context.close()

if __name__ == "__main__":
    main()
