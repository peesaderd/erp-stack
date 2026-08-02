import os
import time
from playwright.sync_api import sync_playwright

def main():
    profile_dir = os.path.abspath(".tiktok_profile")
    print(f"Loading persistent profile from: {profile_dir}")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navigating to Seller Center Homepage...")
        page.goto("https://seller-th.tiktok.com/homepage")
        
        print("Waiting for page load...")
        time.sleep(8)
        
        print(f"Current URL: {page.url}")
        
        # Look for the Affiliate menu item. We can use playwright's locator.
        # From screenshot we can see the text is "Affiliate"
        print("Looking for 'Affiliate' menu item...")
        
        # We can find text "Affiliate" and click it
        try:
            # Let's try locating by text
            affiliate_menu = page.locator("text=Affiliate").first
            if affiliate_menu.is_visible():
                print("Affiliate menu found! Clicking it...")
                affiliate_menu.click()
                print("Clicked Affiliate menu, waiting for load...")
                time.sleep(8)
                
                print(f"New URL after clicking: {page.url}")
                print(f"New Page Title: {page.title()}")
                
                # Take a screenshot of the affiliate page
                page.screenshot(path="affiliate_page.png")
                print("Saved affiliate_page.png")
            else:
                print("Affiliate menu not visible or not found using simple text locator.")
                # Let's try listing all texts on the page to debug
                texts = page.evaluate("() => Array.from(document.querySelectorAll('*')).map(el => el.innerText).filter(t => t && t.includes('Affiliate'))")
                print(f"Elements containing 'Affiliate': {texts[:5]}")
        except Exception as e:
            print(f"Error clicking Affiliate menu: {e}")
            
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
