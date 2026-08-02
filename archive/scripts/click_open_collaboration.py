import os
import time
from playwright.sync_api import sync_playwright

def main():
    profile_dir = os.path.abspath(".tiktok_profile")
    print(f"Loading persistent profile from: {profile_dir}")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navigating to Affiliate landing...")
        page.goto("https://seller-th.tiktok.com/affiliate/landing")
        
        print("Waiting for page load...")
        time.sleep(8)
        
        print(f"Current URL: {page.url}")
        
        # Click the "Go to Open Collaboration" button
        print("Looking for 'Go to Open Collaboration' button...")
        try:
            button = page.locator("text=Go to Open Collaboration").first
            if button.is_visible():
                print("Button found! Clicking it...")
                button.click()
                print("Clicked, waiting for page load (8 seconds)...")
                time.sleep(8)
                
                print(f"New URL: {page.url}")
                print(f"Page Title: {page.title()}")
                
                # Take screenshot
                page.screenshot(path="collaboration_page.png")
                print("Saved collaboration_page.png")
                
                # Let's check if there are other sub-pages or links
                links = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a')).map(a => ({
                        text: a.innerText.trim(),
                        href: a.href
                    }));
                }""")
                print("\nLinks on Collaboration Page:")
                for l in links:
                    if l['text'] or l['href']:
                        print(f"- Text: '{l['text']}' | Href: {l['href']}")
            else:
                print("Button not found or not visible.")
        except Exception as e:
            print(f"Error: {e}")
            
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
