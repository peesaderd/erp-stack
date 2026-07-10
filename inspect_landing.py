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
            user_data_dir=os.path.abspath(".firefox_scratch_inspect_landing"),
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            viewport={"width": 1920, "height": 1080}
        )
        context.add_cookies(cookies)
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navigating to Affiliate landing page...")
        page.goto("https://seller-th.tiktok.com/affiliate/landing?shop_region=TH")
        page.wait_for_timeout(8000)
        
        # Extract HTML and details of links and buttons
        elements_info = page.evaluate("""() => {
            const results = [];
            document.querySelectorAll('a, button').forEach(el => {
                results.push({
                    tagName: el.tagName,
                    text: el.innerText.trim(),
                    href: el.getAttribute('href'),
                    target: el.getAttribute('target'),
                    id: el.id,
                    className: el.className,
                    outerHTML: el.outerHTML.slice(0, 300)
                });
            });
            return results;
        }""")
        
        print("\n=== Elements Info ===")
        for el in elements_info:
            if el['text'] or el['href']:
                print(f"[{el['tagName']}] Text: '{el['text']}' | Href: '{el['href']}' | Target: '{el['target']}' | OuterHTML: {el['outerHTML']}")
                
        # Also print frame URLs
        print("\n=== Frame URLs ===")
        for idx, f in enumerate(page.frames):
            print(f"Frame {idx}: name='{f.name}', url='{f.url}'")
            
        context.close()

if __name__ == "__main__":
    main()
