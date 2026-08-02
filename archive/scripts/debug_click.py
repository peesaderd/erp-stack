import os
import time
from playwright.sync_api import sync_playwright

def main():
    profile_dir = os.path.abspath(".tiktok_profile")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        # Listen for console messages and page errors
        page.on("console", lambda msg: print(f"Browser Console [{msg.type}]: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Browser Page Error: {err}"))
        
        print("Navigating...")
        page.goto("https://seller-th.tiktok.com/affiliate/landing?shop_region=TH")
        time.sleep(8)
        
        print("Clicking Go to Affiliate Center Home...")
        try:
            btn = page.locator("text=Go to Affiliate Center Home").first
            if btn.is_visible():
                btn.click()
                print("Clicked button. Waiting 10 seconds...")
                time.sleep(10)
            else:
                print("Button not visible.")
        except Exception as e:
            print(f"Click error: {e}")
            
        context.close()

if __name__ == "__main__":
    main()
