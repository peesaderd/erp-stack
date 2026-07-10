import os
import time
from playwright.sync_api import sync_playwright

def main():
    profile_dir = os.path.abspath(".tiktok_profile")
    print(f"Loading persistent profile from: {profile_dir}")
    
    with sync_playwright() as p:
        # We MUST use headless=False to bypass anti-bot detection and use the active login
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        
        print("Navigating to Seller Center Homepage...")
        page.goto("https://seller-th.tiktok.com/homepage")
        
        # Wait for page load and any redirections
        print("Waiting for page load (10 seconds)...")
        time.sleep(10)
        
        print(f"Loaded URL: {page.url}")
        print(f"Page Title: {page.title()}")
        
        # Take a screenshot
        page.screenshot(path="homepage_dashboard.png")
        print("Saved homepage_dashboard.png")
        
        # Extract all links
        links = page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('a').forEach(a => {
                result.push({
                    text: a.innerText.trim(),
                    href: a.href
                });
            });
            return result;
        }""")
        
        print("\nAll Links Found on Page:")
        for link in links:
            if link['text'] or link['href']:
                print(f"- Text: '{link['text']}' | Href: {link['href']}")
                
        # Let's search for "Affiliate" links specifically
        print("\nFiltering for Affiliate-related links:")
        affiliate_links = [l for l in links if 'affiliate' in l['href'].lower() or 'affiliate' in l['text'].lower() or 'connection' in l['href'].lower()]
        for l in affiliate_links:
            print(f"- [FOUND] Text: '{l['text']}' | Href: {l['href']}")
            
        context.close()
        print("Done!")

if __name__ == "__main__":
    main()
