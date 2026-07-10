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
        
    profile_dir = os.path.abspath(".firefox_scratch_details")
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
                    headers = request.headers
                    status = response.status
                    try:
                        res_json = response.json()
                    except Exception:
                        res_json = None
                        
                    print(f"Captured orders/list API call! Status: {status}")
                    captured_requests.append({
                        "url": url,
                        "method": request.method,
                        "request_headers": headers,
                        "request_body": post_data,
                        "status": status,
                        "response_data": res_json
                    })
            except Exception as e:
                print(f"Error in handler: {e}")
                
        context.on("response", handle_response)
        
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navigating...")
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
                else:
                    print("Menu link not found")
            else:
                print("Second tab not opened")
        else:
            print("Button not found")
            
        print("\n=== Captured Request Details ===")
        for req in captured_requests:
            print(f"Method: {req['method']}")
            print(f"Headers: {json.dumps(req['request_headers'], indent=2)}")
            print(f"Body: {req['request_body']}")
            print(f"Response: {json.dumps(req['response_data'], indent=2)}")
            print("=" * 50)
            
        # Write to file
        with open("orders_list_payload.json", "w", encoding="utf-8") as f_out:
            json.dump(captured_requests, f_out, indent=4, ensure_ascii=False)
            
        context.close()

if __name__ == "__main__":
    main()
