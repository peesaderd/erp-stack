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
        
    profile_dir = os.path.abspath(".firefox_scratch_onboard")
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
                            print(f"Intercepted: {status} | {url[:90]}")
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
        
        print("Navigating to Affiliate landing page...")
        page.goto("https://seller-th.tiktok.com/affiliate/landing?shop_region=TH")
        page.wait_for_timeout(8000)
        
        page.screenshot(path="onboard_1_landing.png")
        
        # Check buttons
        buttons = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button')).map((b, idx) => {
                return {
                    idx: idx,
                    text: b.innerText,
                    class: b.className,
                    visible: b.offsetWidth > 0 && b.offsetHeight > 0
                };
            });
        }""")
        print(f"Found buttons: {buttons}")
        
        # Find "Go to Open Collaboration" or similar button and click it
        clicked = False
        for text in ["Go to Open Collaboration", "Get started", "Start", "Open"]:
            button_locator = page.locator(f"button:has-text('{text}')")
            if button_locator.count() > 0 and button_locator.first.is_visible():
                print(f"Found button with text '{text}'. Clicking it...")
                button_locator.first.click()
                page.wait_for_timeout(8000)
                clicked = True
                break
                
        if not clicked:
            # Try finding any visible button inside the main landing page area
            print("Trying to click the first visible button...")
            btn_locator = page.locator("button")
            count = btn_locator.count()
            for i in range(count):
                btn = btn_locator.nth(i)
                if btn.is_visible() and btn.text_content().strip() != "":
                    print(f"Clicking visible button {i}: '{btn.text_content().strip()}'")
                    btn.click()
                    page.wait_for_timeout(8000)
                    clicked = True
                    break
                    
        page.screenshot(path="onboard_2_after_click.png")
        print(f"URL after onboarding interaction: {page.url}")
        
        # Now navigate to Affiliate Order page
        print("Navigating to Affiliate Order page...")
        page.goto("https://seller-th.tiktok.com/affiliate/order?shop_region=TH")
        print("Waiting 20 seconds for order list to load...")
        page.wait_for_timeout(20000)
        
        page.screenshot(path="onboard_3_orders_page.png")
        print(f"Final URL: {page.url}")
        
        # Print visible text
        visible_text = page.evaluate("() => document.body.innerText")
        print("\n=== Visible Text on Order Page ===")
        print(visible_text[:2000])
        print("===================================\n")
        
        # Save captured data
        with open("captured_orders_api_onboard.json", "w", encoding="utf-8") as f_out:
            json.dump(captured_data, f_out, indent=4, ensure_ascii=False)
        print(f"Saved {len(captured_data)} API responses to captured_orders_api_onboard.json")
        
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
