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
            user_data_dir=os.path.abspath(".firefox_scratch_find_links"),
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            viewport={"width": 1920, "height": 1080}
        )
        context.add_cookies(cookies)
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navigating to Affiliate landing page...")
        page.goto("https://seller-th.tiktok.com/affiliate/landing?shop_region=TH")
        page.wait_for_timeout(8000)
        
        # Click "Go to Open Collaboration"
        btn = page.locator("button:has-text('Go to Open Collaboration')").first
        if btn.is_visible():
            print("Clicking 'Go to Open Collaboration'...")
            btn.click()
            page.wait_for_timeout(8000)
            
            pages = context.pages
            if len(pages) > 1:
                target_page = pages[1]
                print(f"Inspecting new tab: {target_page.url}")
                
                # Get all links
                links = target_page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a')).map(a => {
                        return {
                            text: a.innerText.trim(),
                            href: a.getAttribute('href'),
                            class: a.className
                        };
                    }).filter(item => item.text || item.href);
                }""")
                
                print("\n=== Links found on the Affiliate Portal ===")
                for l in links:
                    print(f"Text: '{l['text']}' | Href: '{l['href']}'")
            else:
                print("Failed to open a second tab!")
        else:
            print("Go to Open Collaboration button not found!")
            
        context.close()

if __name__ == "__main__":
    main()
