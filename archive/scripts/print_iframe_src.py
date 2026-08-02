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
        
        # Extract all iframe src attributes from the DOM
        iframes_info = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('iframe')).map(iframe => ({
                src: iframe.src,
                id: iframe.id,
                className: iframe.className
            }));
        }""")
        
        print("\nAll iframes in DOM:")
        for idx, iframe in enumerate(iframes_info):
            print(f"[{idx}] src: '{iframe['src']}' | id: '{iframe['id']}' | class: '{iframe['className']}'")
            
        context.close()

if __name__ == "__main__":
    main()
