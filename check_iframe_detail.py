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
        page.goto("https://seller-th.tiktok.com/affiliate/order?shop_region=TH")
        time.sleep(12)
        
        print(f"Current URL: {page.url}")
        
        # Check iframes
        frames = page.frames
        print(f"\nTotal frames found: {len(frames)}")
        for idx, f in enumerate(frames):
            print(f"Frame {idx}: Name='{f.name}' | URL='{f.url}'")
            
        # Get outer HTML of the main container
        container_html = page.evaluate("""() => {
            // Find the main content area (often div with class like page-content or container)
            const root = document.getElementById('root') || document.body;
            return root.innerHTML;
        }""")
        
        # Write first 1000 characters of HTML to output
        print("\nPage HTML structure (truncated):")
        print(container_html[:1500])
        
        context.close()

if __name__ == "__main__":
    main()
