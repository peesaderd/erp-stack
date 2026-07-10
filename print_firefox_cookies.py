import os
import sys
from playwright.sync_api import sync_playwright

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    profile_dir = os.path.abspath(".firefox_tiktok_profile")
    
    with sync_playwright() as p:
        context = p.firefox.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            no_viewport=True
        )
        
        # Open a page to fetch cookies (we need to open at least one page to get cookies)
        page = context.new_page()
        page.goto("https://www.tiktok.com")
        
        cookies = context.cookies()
        print(f"Total Firefox cookies: {len(cookies)}")
        
        # Group cookies by domain
        by_domain = {}
        for c in cookies:
            domain = c['domain']
            by_domain.setdefault(domain, []).append(c['name'])
            
        print("\nCookies grouped by domain:")
        for domain, names in sorted(by_domain.items()):
            print(f"- {domain}: {len(names)} cookies ({', '.join(names[:5])}...)")
            
        context.close()

if __name__ == "__main__":
    main()
