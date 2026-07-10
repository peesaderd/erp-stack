import os
import sys
import time
from playwright.sync_api import sync_playwright

def main():
    profile_dir = os.path.abspath(".firefox_tiktok_profile")
    print(f"Using persistent Firefox profile in: {profile_dir}")
    
    os.makedirs(profile_dir, exist_ok=True)
    
    with sync_playwright() as p:
        print("Launching Firefox...")
        context = p.firefox.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
            
        print("Opening TikTok Shop Seller Center...")
        try:
            page.goto("https://seller-th.tiktok.com/")
        except Exception as e:
            print(f"Error loading Seller Center: {e}")
            
        print("Opening TikTok Shop Creator page...")
        page2 = context.new_page()
        try:
            page2.goto("https://shop.tiktok.com/")
        except Exception as e:
            print(f"Error loading TikTok Shop Creator page: {e}")
            
        print("\n" + "="*60)
        print("INSTRUCTIONS:")
        print("1. A Firefox window has opened on your screen.")
        print("2. Please log in to your TikTok Shop / Creator account in either tab.")
        print("3. Once you have logged in successfully and see your dashboard,")
        print("   simply CLOSE the Firefox window to save your session and exit.")
        print("="*60 + "\n")
        
        while True:
            try:
                # Just query active pages to detect if browser is closed
                _ = page.url
                _ = page2.url
            except Exception:
                print("Firefox window closed by user.")
                break
            time.sleep(2)
            
        context.close()
        print("Session saved successfully!")

if __name__ == "__main__":
    main()
