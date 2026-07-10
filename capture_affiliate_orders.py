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
        
    profile_dir = os.path.abspath(".firefox_scratch_capture_orders")
    if os.path.exists(profile_dir):
        try:
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
        
        captured_data = []
        
        # Listen on the context level so we catch all tabs!
        def handle_response(response):
            try:
                url = response.url
                if "api" in url or "graphql" in url or "rpc" in url:
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        status = response.status
                        try:
                            res_json = response.json()
                            print(f"Intercepted (Tab URL {response.frame.page.url[:40]}...): {status} | {url[:90]}")
                            captured_data.append({
                                "tab_url": response.frame.page.url,
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
        
        print("Navigating to Affiliate landing page...")
        page.goto("https://seller-th.tiktok.com/affiliate/landing?shop_region=TH")
        page.wait_for_timeout(8000)
        
        btn = page.locator("button:has-text('Go to Open Collaboration')").first
        if btn.is_visible():
            print("Clicking 'Go to Open Collaboration'...")
            btn.click()
            page.wait_for_timeout(10000)
            
            pages = context.pages
            if len(pages) > 1:
                target_page = pages[1]
                print(f"Clicking 'Affiliate orders' in tab 1...")
                orders_menu = target_page.locator("text=Affiliate orders").first
                if orders_menu.count() > 0 and orders_menu.is_visible():
                    orders_menu.click()
                    print("Waiting 20 seconds for orders page to load and trigger APIs...")
                    target_page.wait_for_timeout(20000)
                    
                    target_page.screenshot(path="orders_captured_state.png")
                    print("Saved orders_captured_state.png")
                else:
                    print("Could not find 'Affiliate orders' menu link.")
            else:
                print("Affiliate tab did not open.")
        else:
            print("Go to Open Collaboration button not found.")
            
        # Save captured data
        output_file = "captured_affiliate_orders.json"
        with open(output_file, 'w', encoding='utf-8') as f_out:
            json.dump(captured_data, f_out, indent=4, ensure_ascii=False)
        print(f"\nSaved {len(captured_data)} API responses to {output_file}")
        
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
