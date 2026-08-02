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
        
    profile_dir = os.path.abspath(".firefox_scratch_interact")
    if os.path.exists(profile_dir):
        try:
            shutil.rmtree(profile_dir)
            print("Cleaned up existing profile directory.")
        except Exception as e:
            print(f"Warning: {e}")
            
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
                
        page.on("response", handle_response)
        
        print("Navigating to Affiliate Order page...")
        page.goto("https://seller-th.tiktok.com/affiliate/order?shop_region=TH")
        
        print("Waiting 10 seconds for initial load...")
        page.wait_for_timeout(10000)
        
        page.screenshot(path="interact_1_initial.png")
        print("Saved interact_1_initial.png")
        
        # Check for "Got it" button
        print("Checking for popups/buttons...")
        try:
            # Let's find all buttons and click them if they say "Got it"
            got_it_buttons = page.locator("text=Got it")
            count = got_it_buttons.count()
            print(f"Found {count} 'Got it' buttons.")
            for i in range(count):
                btn = got_it_buttons.nth(i)
                if btn.is_visible():
                    print(f"Clicking 'Got it' button {i}...")
                    btn.click()
                    page.wait_for_timeout(2000)
        except Exception as e:
            print(f"Error handling 'Got it' buttons: {e}")
            
        # Let's also look for general buttons with class arco-btn or text like "Close" or "Confirm"
        try:
            # Let's print out all button texts to see what's on the screen
            buttons = page.evaluate("() => Array.from(document.querySelectorAll('button')).map(b => b.innerText)")
            print(f"Visible buttons: {buttons}")
        except Exception as e:
            print(f"Error listing buttons: {e}")
            
        print("Waiting another 20 seconds for affiliate order list API to trigger...")
        page.wait_for_timeout(20000)
        
        page.screenshot(path="interact_2_after_wait.png")
        print("Saved interact_2_after_wait.png")
        
        # Print visible text
        visible_text = page.evaluate("() => document.body.innerText")
        print("\n=== Visible Text on Page ===")
        print(visible_text[:2000])
        print("============================\n")
        
        # Save captured data
        output_file = "captured_orders_api_firefox.json"
        with open(output_file, 'w', encoding='utf-8') as f_out:
            json.dump(captured_data, f_out, indent=4, ensure_ascii=False)
        print(f"Saved {len(captured_data)} API calls to {output_file}")
        
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
