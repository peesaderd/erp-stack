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
        page.goto("https://seller-th.tiktok.com/affiliate/landing?shop_region=TH")
        time.sleep(8)
        
        # Listen for popup tabs
        popups = []
        context.on("page", lambda p: popups.append(p))
        
        # Find and click "Go to Affiliate Center Home"
        btn = page.locator("text=Go to Affiliate Center Home").first
        if btn.is_visible():
            print("Clicking 'Go to Affiliate Center Home'...")
            btn.click()
            
            # Wait for any new page/tab to load
            print("Waiting 10 seconds for tabs to load...")
            time.sleep(10)
            
            print(f"Total pages open: {len(context.pages)}")
            for idx, p_page in enumerate(context.pages):
                try:
                    p_page.wait_for_load_state("networkidle", timeout=5000)
                except:
                    pass
                print(f"Page {idx} URL: {p_page.url}")
                print(f"Page {idx} Title: {p_page.title()}")
                
                # Take screenshot of every page
                p_page.screenshot(path=f"page_{idx}.png")
                print(f"Saved page_{idx}.png")
        else:
            print("Button not found.")
            
        context.close()

if __name__ == "__main__":
    main()
