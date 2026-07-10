import os
import sys
import json
import time
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
        
    print(f"Loaded {len(cookies)} cookies from cookies.json")
    
    with sync_playwright() as p:
        # Launch headed to avoid bot flags and allow rendering
        context = p.chromium.launch_persistent_context(
            user_data_dir=os.path.abspath(".tiktok_scratch_profile"),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        # Inject the cookies
        print("Injecting cookies into browser context...")
        context.add_cookies(cookies)
        
        page = context.pages[0] if context.pages else context.new_page()
        
        captured_data = []
        
        # Listen for all network responses to capture raw JSON data
        def handle_response(response):
            try:
                url = response.url
                # Filter for API requests that might contain order or affiliate data
                if "api" in url or "graphql" in url or "rpc" in url:
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        status = response.status
                        print(f"Intercepted API Call: {status} | {url[:100]}...")
                        
                        try:
                            res_json = response.json()
                            captured_data.append({
                                "url": url,
                                "status": status,
                                "data": res_json
                            })
                        except Exception:
                            # Might not be valid JSON or empty
                            pass
            except Exception as e:
                pass
                
        page.on("response", handle_response)
        
        print("Navigating to Affiliate Order page...")
        page.goto("https://seller-th.tiktok.com/affiliate/order?shop_region=TH")
        
        # Wait for 25 seconds to let the dashboard render and trigger all API calls
        print("Waiting 25 seconds for orders list to load and APIs to trigger...")
        time.sleep(25)
        
        # Save captured API responses to a file
        output_file = "captured_orders_api.json"
        with open(output_file, 'w', encoding='utf-8') as f_out:
            json.dump(captured_data, f_out, indent=4, ensure_ascii=False)
            
        print(f"\nSaved {len(captured_data)} API responses to {output_file}")
        
        # Take a final screenshot to see if the table rendered visually
        page.screenshot(path="order_page_cookies_injected.png")
        print("Saved order_page_cookies_injected.png")
        
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
