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
        
    profile_dir = os.path.abspath(".firefox_scratch_add_products")
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
                            print(f"Intercepted: {status} | {url[:90]}...")
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
                print(f"Opened Affiliate URL: {target_page.url}")
                
                # Check for "Add products" button
                add_btn = target_page.locator("button:has-text('Add products')").first
                if add_btn.is_visible():
                    print("Found 'Add products' button! Clicking it...")
                    add_btn.click()
                    page.wait_for_timeout(8000)
                    
                    target_page.screenshot(path="add_products_clicked.png")
                    print("Saved add_products_clicked.png")
                    
                    # Print visible text on screen
                    visible_text = target_page.evaluate("() => document.body.innerText")
                    print("\n=== Visible Text after clicking Add Products ===")
                    print(visible_text[:2000])
                    print("================================================\n")
                else:
                    print("Add products button not visible.")
                    # Try clicking "Not added" tab
                    not_added_tab = target_page.locator("text=Not added").first
                    if not_added_tab.is_visible():
                        print("Clicking 'Not added' tab...")
                        not_added_tab.click()
                        page.wait_for_timeout(8000)
                        target_page.screenshot(path="not_added_tab_clicked.png")
                        
                        visible_text = target_page.evaluate("() => document.body.innerText")
                        print("\n=== Visible Text after clicking Not Added ===")
                        print(visible_text[:2000])
                        print("=============================================\n")
            else:
                print("Second tab not opened")
        else:
            print("Button not found")
            
        with open("captured_add_products.json", "w", encoding="utf-8") as f_out:
            json.dump(captured_data, f_out, indent=4, ensure_ascii=False)
            
        context.close()

if __name__ == "__main__":
    main()
