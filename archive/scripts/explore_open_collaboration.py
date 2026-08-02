import os
import sys
import json
import shutil
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
        
    profile_dir = os.path.abspath(".firefox_scratch_collab_explore")
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
        except Exception:
            pass
            
    with sync_playwright() as p:
        print("Launching Firefox...")
        context = p.firefox.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            viewport={"width": 1920, "height": 1080}
        )
        context.add_cookies(cookies)
        
        captured_data = []
        def handle_response(response):
            try:
                url = response.url
                if "api" in url or "graphql" in url or "rpc" in url:
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        status = response.status
                        try:
                            res_json = response.json()
                            print(f"Intercepted: {status} | {url[:80]}...")
                            captured_data.append({
                                "url": url,
                                "status": status,
                                "data": res_json
                            })
                        except Exception:
                            pass
            except Exception:
                pass
        context.on("response", handle_response)
        
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navigating to landing page...")
        page.goto("https://seller-th.tiktok.com/affiliate/landing?shop_region=TH")
        page.wait_for_timeout(8000)
        
        btn = page.locator("button:has-text('Go to Open Collaboration')").first
        if btn.is_visible():
            btn.click()
            page.wait_for_timeout(10000)
            
            pages = context.pages
            if len(pages) > 1:
                target_page = pages[1]
                print(f"Current Affiliate URL: {target_page.url}")
                
                # Take screenshot
                target_page.screenshot(path="open_collaboration_main.png")
                print("Saved open_collaboration_main.png")
                
                # Print visible text
                visible_text = target_page.evaluate("() => document.body.innerText")
                print("\n=== Visible Text on Open Collaboration ===")
                print(visible_text[:2000])
                print("==========================================\n")
                
                # Let's list all buttons and click the tab or button to show unpromoted products
                # Usually there's a text like "Products not added" or similar, or "Add products" button
                # Let's look for "Add products" or "unpromote" or similar elements
                elements = target_page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('button, div, span'))
                        .map(el => el.innerText ? el.innerText.trim() : '')
                        .filter(t => t.includes('product') || t.includes('add') || t.includes('สินค้า') || t.includes('เพิ่ม') || t.includes('โปรโมท') || t.includes('ตะกร้า'));
                }""")
                print("Found relevant text elements:", list(set(elements))[:30])
            else:
                print("Second tab not opened")
        else:
            print("Button not found")
            
        with open("captured_collab.json", "w", encoding="utf-8") as f_out:
            json.dump(captured_data, f_out, indent=4, ensure_ascii=False)
            
        context.close()

if __name__ == "__main__":
    main()
