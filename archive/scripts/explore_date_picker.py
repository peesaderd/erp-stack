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
        
    profile_dir = os.path.abspath(".firefox_scratch_datepicker")
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
                print("Navigating to orders page...")
                orders_menu = target_page.locator("text=Affiliate orders").first
                if orders_menu.count() > 0 and orders_menu.is_visible():
                    orders_menu.click()
                    page.wait_for_timeout(10000)
                    
                    # Print picker info
                    print("Inspecting picker elements...")
                    picker_elements = target_page.evaluate("""() => {
                        return Array.from(document.querySelectorAll('*'))
                            .map(el => {
                                const textVal = el.innerText ? el.innerText.trim() : '';
                                return {
                                    tagName: el.tagName,
                                    className: el.className || '',
                                    text: textVal,
                                    placeholder: el.getAttribute('placeholder') || ''
                                };
                            })
                            .filter(item => item.className.includes('picker') || item.text.includes('2026') || item.placeholder.includes('Date'));
                    }""")
                    print("Found picker elements:", picker_elements[:15])
                    
                    # Try to click on the date range selector.
                    # Usually, there is a date range element containing "Order creation date" or a picker class
                    # Let's locate elements by class name like 'arco-picker' or text 'Order creation date'
                    picker = target_page.locator("[class*='picker']").first
                    if picker.is_visible():
                        print("Clicking picker element...")
                        picker.click()
                        page.wait_for_timeout(3000)
                        
                        target_page.screenshot(path="datepicker_opened.png")
                        print("Saved datepicker_opened.png")
                        
                        # Print overlay text/elements using double quotes for selector
                        overlay_text = target_page.evaluate("""() => {
                            const selector = "[class*='popover'], [class*='trigger'], [class*='picker'], [class*='overlay'], [class*='dropdown']";
                            return Array.from(document.querySelectorAll(selector))
                                .map(el => el.innerText ? el.innerText.trim() : '')
                                .filter(t => t.length > 0 && t.length < 200);
                        }""")
                        print("Overlay / Dropdown elements found text:", list(set(overlay_text))[:25])
                    else:
                        print("Picker element not found.")
                else:
                    print("Menu link not found")
            else:
                print("Second tab not opened")
        else:
            print("Button not found")
            
        context.close()

if __name__ == "__main__":
    main()
