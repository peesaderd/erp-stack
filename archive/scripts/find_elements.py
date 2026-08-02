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
        
    profile_dir = os.path.abspath(".firefox_scratch_find")
    if os.path.exists(profile_dir):
        try:
            import shutil
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
        context.add_cookies(cookies)
        page = context.pages[0] if context.pages else context.new_page()
        
        # Intercept and log all APIs
        def handle_response(response):
            url = response.url
            if "api" in url or "graphql" in url or "rpc" in url:
                if response.status == 200:
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        print(f"Intercepted API: {url[:100]}")
                        
        page.on("response", handle_response)
        
        print("Navigating to Homepage...")
        page.goto("https://seller-th.tiktok.com/homepage")
        page.wait_for_timeout(10000)
        
        page.screenshot(path="find_1_home.png")
        print(f"Home URL: {page.url}")
        
        # Find Affiliate sidebar link
        print("Finding 'Affiliate' menu link...")
        # Let's search for an element containing text "Affiliate"
        affiliate_el = page.locator("text=Affiliate").first
        if affiliate_el.is_visible():
            print("Affiliate menu element is visible! Clicking it...")
            affiliate_el.click()
            page.wait_for_timeout(10000)
            
            print(f"URL after click: {page.url}")
            page.screenshot(path="find_2_affiliate.png")
            
            # Print frames
            frames = page.frames
            print(f"Frames count: {len(frames)}")
            for idx, f in enumerate(frames):
                print(f"  Frame {idx}: name='{f.name}', url='{f.url[:120]}'")
                
            # Print text
            visible_text = page.evaluate("() => document.body.innerText")
            print("\n=== Visible Text after Click ===")
            print(visible_text[:2000])
            print("================================\n")
        else:
            print("Affiliate menu element NOT visible.")
            
        context.close()

if __name__ == "__main__":
    main()
