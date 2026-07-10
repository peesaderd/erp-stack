import os
import sys
import time
from playwright.sync_api import sync_playwright

def main():
    profile_dir = os.path.abspath(".tiktok_profile")
    print(f"Using persistent profile in: {profile_dir}")
    
    # Ensure profile directory exists
    os.makedirs(profile_dir, exist_ok=True)
    
    with sync_playwright() as p:
        print("Launching browser...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
            no_viewport=True
        )
        
        # Close default page if any
        pages = context.pages
        if pages:
            page = pages[0]
        else:
            page = context.new_page()
            
        print("Opening TikTok Shop Seller Center...")
        try:
            page.goto("https://seller-th.tiktok.com/")
        except Exception as e:
            print(f"Error loading Seller Center: {e}")
        
        # Open TikTok Shop Affiliate/Creator portal
        print("Opening TikTok Shop Creator page...")
        page2 = context.new_page()
        try:
            page2.goto("https://shop.tiktok.com/")
        except Exception as e:
            print(f"Error loading TikTok Shop Creator page: {e}")
        
        print("\n" + "="*60)
        print("INSTRUCTIONS:")
        print("1. A browser window has opened on your screen.")
        print("2. Please log in to your TikTok Shop / Affiliate account in either tab.")
        print("3. Once you have logged in successfully and see your dashboard,")
        print("   type 'done' or press ENTER in the terminal to save your session and exit.")
        print("="*60 + "\n")
        
        # Keep printing status periodically to let the AI know the current URL
        last_url1 = ""
        last_url2 = ""
        
        # Let's loop until user inputs something in stdin
        # We use a non-blocking check or standard input
        print("Monitoring browser tabs. Press ENTER or send 'done' to save & exit...")
        
        # Make stdin non-blocking on Windows is tricky, so we just run a loop and check
        # if there's any file flag or if we get stdin. Since this is Python, input() blocks.
        # So we'll check if a file named 'exit_flag.txt' is created as well, which is safer!
        exit_flag_file = "exit_flag.txt"
        if os.path.exists(exit_flag_file):
            os.remove(exit_flag_file)
            
        while True:
            # Check if exit flag file exists (created by us when the user tells us they are done)
            if os.path.exists(exit_flag_file):
                print("Exit flag detected, closing browser...")
                break
                
            try:
                # We can print current URLs if they change
                url1 = page.url
                url2 = page2.url
                if url1 != last_url1 or url2 != last_url2:
                    print(f"Current URLs -> Tab 1: {url1} | Tab 2: {url2}")
                    last_url1 = url1
                    last_url2 = url2
            except Exception as e:
                # Browser might be closed manually by user
                print(f"Browser window closed or error occurred: {e}")
                break
                
            time.sleep(2)
            
        print("Closing browser and saving session...")
        context.close()
        print("Session saved successfully!")

if __name__ == "__main__":
    main()
