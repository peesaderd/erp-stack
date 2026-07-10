import os
import sys
import json
import time
from playwright.sync_api import sync_playwright

def post_reel(video_path, caption):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    if not os.path.exists(video_path):
        print(f"Error: Video file {video_path} not found!")
        return False
        
    profile_dir = os.path.abspath(".facebook_profile")
    print(f"Loading persistent profile: {profile_dir}")
    print(f"Post Video: {video_path}")
    print(f"Caption: {caption[:60]}...")
    
    # We use asset_id = 1074710242401773 from M2L Gen page
    asset_id = "1074710242401773"
    composer_url = f"https://business.facebook.com/latest/reels_composer/?asset_id={asset_id}"
    
    with sync_playwright() as p:
        # Launch headed to avoid bot flags and allow video uploads to render
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False, # Headed is crucial for upload rendering & security checks
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = context.pages[0] if context.pages else context.new_page()
        print(f"Navigating to Reels Composer: {composer_url}")
        page.goto(composer_url, wait_until="domcontentloaded", timeout=60000)
        
        # Wait for page to render
        page.wait_for_timeout(8000)
        
        # Dismiss any 'Got it' popup that might block clicks
        got_it = page.locator("text=Got it").first
        if got_it.is_visible():
            print("Dismissing 'Got it' popup...")
            got_it.click()
            page.wait_for_timeout(2000)
            
        # Expect file chooser and click Add video button
        print("Uploading video file...")
        try:
            with page.expect_file_chooser(timeout=20000) as fc_info:
                # Click the Add video button
                page.locator("text=Add video").first.click()
            file_chooser = fc_info.value
            file_chooser.set_files(video_path)
            print("Video file attached.")
        except Exception as e:
            print(f"Error selecting file: {e}")
            context.close()
            return False
            
        # Wait for video upload and processing to complete
        # We look for the 'Next' button to become enabled
        print("Waiting for video to upload and process (checking 'Next' button)...")
        next_btn = page.locator("button:has-text('Next')").first
        
        uploaded = False
        # Limit wait to 5 minutes (300 seconds)
        for attempt in range(60):
            page.wait_for_timeout(5000)
            if next_btn.is_visible() and next_btn.is_enabled():
                print("Video upload finished! Next button is now active.")
                uploaded = True
                break
            else:
                # Print progress percentage if visible
                progress = page.locator("text=%").first
                if progress.is_visible():
                    print(f"Upload progress: {progress.inner_text()}")
                else:
                    print("Uploading...")
                    
        if not uploaded:
            print("Error: Upload timeout or failed.")
            page.screenshot(path="facebook_upload_failed.png")
            context.close()
            return False
            
        # Fill in the description/caption
        print("Entering Reel caption...")
        # Look for textbox (div with role="textbox" or contenteditable="true" or textarea)
        caption_box = page.locator("div[role='textbox'], [contenteditable='true'], textarea").first
        if caption_box.is_visible():
            caption_box.click()
            # Clear if any existing
            caption_box.fill(caption)
            page.wait_for_timeout(2000)
        else:
            print("Warning: Caption input field not found. Trying fallback selectors...")
            # Fallback
            page.keyboard.type(caption)
            
        page.screenshot(path="facebook_reel_details_filled.png")
        print("Saved details screenshot: facebook_reel_details_filled.png")
        
        # Step 1: Click Next
        print("Clicking Next (to Edit step)...")
        next_btn.click()
        page.wait_for_timeout(4000)
        
        # Step 2: Click Next again (to Share step)
        next_btn2 = page.locator("button:has-text('Next')").first
        if next_btn2.is_visible() and next_btn2.is_enabled():
            print("Clicking Next (to Share step)...")
            next_btn2.click()
            page.wait_for_timeout(4000)
        else:
            # Try general selector
            page.locator("button:has-text('Next')").first.click()
            page.wait_for_timeout(4000)
            
        page.screenshot(path="facebook_reel_share_step.png")
        print("Saved share step screenshot: facebook_reel_share_step.png")
        
        # Step 3: Click Share / Publish button
        share_btn = page.locator("button:has-text('Share'), button:has-text('Publish'), button:has-text('Post')").first
        if share_btn.is_visible() and share_btn.is_enabled():
            print("Clicking Share/Publish button...")
            share_btn.click()
            print("Publishing Reel... Waiting 15 seconds to settle.")
            page.wait_for_timeout(15000)
            page.screenshot(path="facebook_reel_published.png")
            print("Saved final confirmation: facebook_reel_published.png")
            context.close()
            return True
        else:
            print("Error: Share/Publish button not found or not active.")
            context.close()
            return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python auto_post_facebook.py <video_path> <caption_text>")
        sys.exit(1)
        
    vid = sys.argv[1]
    cap = sys.argv[2]
    success = post_reel(vid, cap)
    if success:
        print("Facebook Reel posted successfully!")
        sys.exit(0)
    else:
        print("Failed to post Facebook Reel.")
        sys.exit(1)
