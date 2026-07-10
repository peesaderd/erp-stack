import os
import sys
import json
import time
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
        
    print(f"Loaded {len(cookies)} cookies from cookies.json")
    
    profile_dir = os.path.abspath(".tiktok_scratch_profile")
    
    # Force clean up profile directory to prevent lock/singleton issues
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
            print("Cleaned up existing scratch profile directory.")
        except Exception as e:
            print(f"Warning: Could not clean profile directory: {e}")
            
    with sync_playwright() as p:
        # Launch in headless mode for background task stability
        print("Launching Chromium in HEADLESS mode...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--no-sandbox"
            ],
            viewport={"width": 1920, "height": 1080}
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
                        try:
                            res_json = response.json()
                            print(f"Intercepted API Call (Success): {status} | {url[:80]}...")
                            captured_data.append({
                                "url": url,
                                "status": status,
                                "data": res_json
                            })
                        except Exception:
                            # Not JSON or empty body
                            pass
            except Exception:
                pass
                
        page.on("response", handle_response)
        
        print("Navigating to Affiliate Order page...")
        page.goto("https://seller-th.tiktok.com/affiliate/order?shop_region=TH")
        
        # Wait for 30 seconds to let the dashboard render and trigger all API calls
        print("Waiting 30 seconds for orders list to load and APIs to trigger...")
        time.sleep(30)
        
        # Save captured API responses to a file
        output_file = "captured_orders_api.json"
        with open(output_file, 'w', encoding='utf-8') as f_out:
            json.dump(captured_data, f_out, indent=4, ensure_ascii=False)
            
        print(f"\nSaved {len(captured_data)} API responses to {output_file}")
        
        # Take a final screenshot to verify what was loaded
        page.screenshot(path="order_page_headless_result.png")
        print("Saved order_page_headless_result.png")
        
        # Dump page text to see if there is any message
        visible_text = page.evaluate("() => document.body.innerText")
        print("\n=== Visible Text on Page ===")
        print(visible_text[:1500])
        print("============================\n")
        
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
