import os
import sys
import shutil
from playwright.sync_api import sync_playwright

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    # We will try to test access to the main platforms
    sites_to_test = {
        "Shopee": "https://shopee.co.th/",
        "Lazada": "https://www.lazada.co.th/",
        "Amazon": "https://www.amazon.com/",
        "Facebook": "https://www.facebook.com/"
    }
    
    profile_dir = os.path.abspath(".firefox_scratch_ecom")
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
        except Exception:
            pass
            
    with sync_playwright() as p:
        print("Launching Firefox in HEADLESS mode...")
        context = p.firefox.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        for name, url in sites_to_test.items():
            print(f"\nNavigating to {name}: {url}...")
            try:
                # Set a timeout of 20s
                response = page.goto(url, timeout=20000)
                page.wait_for_timeout(5000)  # Wait 5s for page rendering
                
                status = response.status if response else "No Response"
                print(f"  -> Response Status: {status}")
                print(f"  -> Title: {page.title()}")
                print(f"  -> Final URL: {page.url}")
                
                # Take screenshot
                screenshot_path = f"access_test_{name.lower()}.png"
                page.screenshot(path=screenshot_path)
                print(f"  -> Saved {screenshot_path}")
                
                # Print a small snippet of text to verify what loaded
                visible_text = page.evaluate("() => document.body.innerText")
                print(f"  -> Text snippet (first 300 chars):")
                print(visible_text[:300].replace('\n', ' '))
            except Exception as e:
                print(f"  -> Error accessing {name}: {e}")
                
        context.close()
        print("\nAll tests completed!")

if __name__ == "__main__":
    main()
