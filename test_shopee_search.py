import os
import sys
import json
import shutil
from playwright.sync_api import sync_playwright

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    cookies_file = os.path.abspath("shopee_cookies.json")
    if not os.path.exists(cookies_file):
        print(f"Error: {cookies_file} not found!")
        sys.exit(1)
        
    with open(cookies_file, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
        
    profile_dir = os.path.abspath(".firefox_scratch_shopee_search")
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
        except Exception:
            pass
            
    with sync_playwright() as p:
        print("Launching Firefox...")
        context = p.firefox.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            viewport={"width": 1920, "height": 1080}
        )
        context.add_cookies(cookies)
        page = context.pages[0] if context.pages else context.new_page()
        
        # Search for "ครีมกันแดด" (sunscreen)
        search_url = "https://shopee.co.th/search?keyword=%E0%B8%85%E0%B8%A3%E0%B8%B5%E0%B8%A1%E0%B8%85%E0%B8%B1%E0%B8%99%E0%B9%81%E0%B8%94%E0%B8%94"
        print(f"Navigating to Shopee Search: {search_url}")
        page.goto(search_url)
        
        print("Waiting 15 seconds for search results to load...")
        page.wait_for_timeout(15000)
        
        # Take screenshot
        screenshot_path = "shopee_search_result.png"
        page.screenshot(path=screenshot_path)
        print(f"Saved {screenshot_path}")
        
        # Print page title and url
        print(f"Final URL: {page.url}")
        print(f"Title: {page.title()}")
        
        # Print visible text snippet
        visible_text = page.evaluate("() => document.body.innerText")
        print("\n=== Visible Text on Shopee Search ===")
        print(visible_text[:1000])
        print("=====================================\n")
        
        # Check if we find product titles in text
        if "หน้าแรก" in visible_text or "ตัวกรอง" in visible_text:
            print("Successfully loaded Shopee marketplace search page!")
        else:
            print("Warning: Page structure might not be fully rendered or still blocked.")
            
        context.close()

if __name__ == "__main__":
    main()
