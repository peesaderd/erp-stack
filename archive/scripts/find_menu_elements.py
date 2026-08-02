import os
import sys
import json
from playwright.sync_api import sync_playwright

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    cookies_file = os.path.abspath("cookies.json")
    if not os.path.exists(cookies_file):
        print(f"Error: {cookies_file} not found!")
        sys.exit(1)
        
    with open(cookies_file, 'r', encoding='utf-8') as f:
        cookies = json.load(f)
        
    with sync_playwright() as p:
        context = p.firefox.launch_persistent_context(
            user_data_dir=os.path.abspath(".firefox_scratch_find_menu"),
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            viewport={"width": 1920, "height": 1080}
        )
        context.add_cookies(cookies)
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navigating to Affiliate landing page...")
        page.goto("https://seller-th.tiktok.com/affiliate/landing?shop_region=TH")
        page.wait_for_timeout(8000)
        
        btn = page.locator("button:has-text('Go to Open Collaboration')").first
        if btn.is_visible():
            print("Clicking 'Go to Open Collaboration'...")
            btn.click()
            page.wait_for_timeout(8000)
            
            pages = context.pages
            if len(pages) > 1:
                target_page = pages[1]
                print(f"Inspecting new tab URL: {target_page.url}")
                
                # Check all texts in the sidebar
                print("Looking for 'Affiliate orders' menu item...")
                
                # Find element containing "Affiliate orders"
                orders_menu = target_page.locator("text=Affiliate orders").first
                if orders_menu.count() > 0 and orders_menu.is_visible():
                    print("Found 'Affiliate orders' menu item! Clicking it...")
                    orders_menu.click()
                    print("Waiting for page load after click (8 seconds)...")
                    target_page.wait_for_timeout(8000)
                    
                    print(f"New URL after clicking menu: {target_page.url}")
                    print(f"New Page Title: {target_page.title()}")
                    
                    # Take screenshot
                    target_page.screenshot(path="affiliate_orders_page.png")
                    print("Saved affiliate_orders_page.png")
                    
                    # Print visible text
                    visible_text = target_page.evaluate("() => document.body.innerText")
                    print("\n=== Visible Text on orders tab ===")
                    print(visible_text[:2000])
                    print("==================================\n")
                else:
                    print("Affiliate orders menu item NOT visible or not found!")
                    # Try fuzzy text search
                    texts = target_page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('*'))
                            .map(el => el.innerText ? el.innerText.trim() : '')
                            .filter(t => t.toLowerCase().includes('order'))
                            .slice(0, 10);
                    }""")
                    print(f"Fuzzy matches for 'order': {texts}")
            else:
                print("Second tab not opened.")
        else:
            print("Button not found")
            
        context.close()

if __name__ == "__main__":
    main()
