import os
from playwright.sync_api import sync_playwright

def main():
    profile_dir = os.path.abspath(".tiktok_profile")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            no_viewport=True
        )
        
        cookies = context.cookies()
        print(f"Total cookies: {len(cookies)}")
        
        domains = set()
        for cookie in cookies:
            domains.add(cookie['domain'])
            
        print("\nCookie Domains:")
        for domain in sorted(domains):
            print(f"- {domain}")
            
        context.close()

if __name__ == "__main__":
    main()
