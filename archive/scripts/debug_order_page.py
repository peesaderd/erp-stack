import os
import sys
import time
from playwright.sync_api import sync_playwright

def main():
    # Force stdout/stderr to use UTF-8 to prevent CP874 decoding errors on Windows
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    profile_dir = os.path.abspath(".tiktok_profile")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        # Log console messages and errors safely
        def safe_log(type_str, text):
            # Encode and decode as ascii to replace non-encodable chars, or print safely
            try:
                print(f"{type_str}: {text}")
            except Exception:
                try:
                    clean_text = text.encode('ascii', errors='replace').decode('ascii')
                    print(f"{type_str} (Cleaned): {clean_text}")
                except Exception:
                    pass
                    
        page.on("console", lambda msg: safe_log(f"Console [{msg.type}]", msg.text))
        page.on("pageerror", lambda err: safe_log("Page Error", str(err)))
        
        # Log network responses
        def handle_response(response):
            url = response.url
            if "/api/" in url or "graphql" in url or "rpc" in url:
                safe_log("Response", f"{response.status} | {url}")
                if response.status >= 400:
                    try:
                        safe_log("Error Body", response.text()[:200])
                    except Exception:
                        pass
                        
        page.on("response", handle_response)
        
        print("Navigating to Affiliate Order page...")
        page.goto("https://seller-th.tiktok.com/affiliate/order?shop_region=TH")
        
        # Wait longer to see if more API calls occur
        time.sleep(25)
        
        context.close()
        print("Completed successfully!")

if __name__ == "__main__":
    main()
