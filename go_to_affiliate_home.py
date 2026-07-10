import os
import time
from playwright.sync_api import sync_playwright

def main():
    profile_dir = os.path.abspath(".tiktok_profile")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://seller-th.tiktok.com/affiliate/landing?shop_region=TH")
        time.sleep(10)
        
        print(f"Current URL: {page.url}")
        
        # Click the button "Go to Affiliate Center Home" or first button
        try:
            # We locate by text
            btn = page.locator("text=Go to Affiliate Center Home").first
            if not btn.is_visible():
                # Fallback to the first button on page
                btn = page.locator("button").first
                
            if btn.is_visible():
                print(f"Clicking button: '{btn.inner_text()}'...")
                btn.click()
                print("Clicked! Waiting 10 seconds for Affiliate Center to load...")
                time.sleep(10)
                
                print(f"New URL: {page.url}")
                print(f"Page Title: {page.title()}")
                
                # Take screenshot
                page.screenshot(path="affiliate_center_home.png")
                print("Saved affiliate_center_home.png")
                
                # Extract links on this new page
                links = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a')).map(a => ({
                        text: a.innerText.trim(),
                        href: a.href
                    }));
                }""")
                print("\nLinks on Affiliate Center Home Page:")
                for l in links:
                    if l['text'] or l['href']:
                        print(f"- Text: '{l['text']}' | Href: {l['href']}")
            else:
                print("No button found to click.")
        except Exception as e:
            print(f"Error: {e}")
            
        context.close()

if __name__ == "__main__":
    main()
