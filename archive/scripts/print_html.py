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
        time.sleep(10)
        
        # Get all text elements on page
        elements_info = page.evaluate("""() => {
            const elms = [];
            // Let's look at buttons, links, and divs with clickable styles or key words
            document.querySelectorAll('button, a, div[role="button"], .arco-btn').forEach(el => {
                elms.push({
                    tagName: el.tagName,
                    text: el.innerText.trim(),
                    className: el.className,
                    id: el.id
                });
            });
            return elms;
        }""")
        
        print("\nAll clickable elements found:")
        for idx, el in enumerate(elements_info):
            if el['text']:
                print(f"[{idx}] {el['tagName']} -> Text: '{el['text']}' | Class: '{el['className']}' | ID: '{el['id']}'")
                
        context.close()

if __name__ == "__main__":
    main()
