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
        
    profile_dir = os.path.abspath(".firefox_scratch_tabs_click")
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
        
        captured_requests = []
        
        def handle_response(response):
            try:
                url = response.url
                if "oec/pay/statement/order/seller/orders/list" in url:
                    request = response.request
                    post_data = request.post_data
                    try:
                        res_json = response.json()
                    except Exception:
                        res_json = None
                    captured_requests.append({
                        "url": url,
                        "request_body": post_data,
                        "response_data": res_json
                    })
                    print(f"Captured orders/list: Body={post_data} | ResponseCount={res_json.get('data', {}).get('total_count', 'N/A') if res_json else 'N/A'}")
            except Exception as e:
                pass
                
        context.on("response", handle_response)
        
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navigating to landing page...")
        page.goto("https://seller-th.tiktok.com/affiliate/landing?shop_region=TH")
        page.wait_for_timeout(8000)
        
        btn = page.locator("button:has-text('Go to Open Collaboration')").first
        if btn.is_visible():
            btn.click()
            page.wait_for_timeout(8000)
            
            pages = context.pages
            if len(pages) > 1:
                target_page = pages[1]
                print("Clicking 'Affiliate orders'...")
                orders_menu = target_page.locator("text=Affiliate orders").first
                if orders_menu.count() > 0 and orders_menu.is_visible():
                    orders_menu.click()
                    page.wait_for_timeout(10000)
                    
                    # Screenshot initial state
                    target_page.screenshot(path="tabs_1_initial.png")
                    
                    # Try clicking "Affiliate creator" tab
                    print("\nClicking 'Affiliate creator'...")
                    creator_tab = target_page.locator("text=Affiliate creator").first
                    if creator_tab.is_visible():
                        creator_tab.click()
                        page.wait_for_timeout(5000)
                        target_page.screenshot(path="tabs_2_creator.png")
                    else:
                        print("Affiliate creator tab not found")
                        
                    # Try clicking "Affiliate partner" tab
                    print("\nClicking 'Affiliate partner'...")
                    partner_tab = target_page.locator("text=Affiliate partner").first
                    if partner_tab.is_visible():
                        partner_tab.click()
                        page.wait_for_timeout(5000)
                        target_page.screenshot(path="tabs_3_partner.png")
                    else:
                        print("Affiliate partner tab not found")
                else:
                    print("Menu link not found")
            else:
                print("Second tab not opened")
        else:
            print("Button not found")
            
        print("\n=== Captured Request Details ===")
        for req in captured_requests:
            print(f"Body: {req['request_body']}")
            print(f"Response: {json.dumps(req['response_data'], indent=2)}")
            print("-" * 50)
            
        context.close()

if __name__ == "__main__":
    main()
