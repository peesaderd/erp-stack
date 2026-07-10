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
        
        print("Navigating to Affiliate landing...")
        page.goto("https://seller-th.tiktok.com/affiliate/landing?shop_region=TH")
        time.sleep(10)
        
        print(f"Main page URL: {page.url}")
        
        # List all frames
        frames = page.frames
        print(f"\nTotal frames found: {len(frames)}")
        for idx, frame in enumerate(frames):
            print(f"Frame {idx}: Name='{frame.name}' | URL='{frame.url}'")
            
            # Try to search for the button inside each frame
            try:
                btn = frame.locator("text=Go to Open Collaboration").first
                if btn.is_visible():
                    print(f"  -> FOUND button in Frame {idx}!")
                    # Try to click it
                    btn.click()
                    print("  -> Clicked button! Waiting for load...")
                    time.sleep(8)
                    print(f"  -> Current main page URL after click: {page.url}")
                    
                    # Take screenshot after click
                    page.screenshot(path="after_iframe_click.png")
                    print("  -> Saved after_iframe_click.png")
                    break
            except Exception as e:
                print(f"  -> Error searching in Frame {idx}: {e}")
                
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
