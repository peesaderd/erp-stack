import os
import sys
import json
import time
import requests
import urllib3
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# UTF-8 Encoding on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Server Endpoint Configs
SERVER_URL = "https://openhands.m2igen.com"
GET_JOBS_API = f"{SERVER_URL}/api/tiktok/ugc/posts"
UPDATE_STATUS_API = f"{SERVER_URL}/api/tiktok/ugc/webhook/pfm"
PFM_FALLBACK_API = f"{SERVER_URL}/pfm/post"

# Local Playwright profile paths
PROFILES_DIR = os.path.abspath("browser_profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)

def fetch_pending_jobs():
    """Poll server for pending post jobs across all platforms."""
    print("Polling server for pending posts across all platforms...")
    try:
        response = requests.get(GET_JOBS_API, params={"status": "pending"}, verify=False, timeout=15)
        response.raise_for_status()
        res_data = response.json()
        if res_data.get("success"):
            posts = res_data.get("posts", [])
            pending = [p for p in posts if p.get("status") == "pending"]
            return pending
    except Exception as e:
        print(f"Error fetching jobs: {e}")
    return []

def download_video(media_url, save_path):
    """Download the media video locally for upload."""
    full_url = media_url
    if media_url.startswith("/"):
        full_url = urljoin(SERVER_URL, media_url)
    print(f"Downloading video: {full_url} -> {save_path}")
    try:
        response = requests.get(full_url, verify=False, stream=True, timeout=90)
        response.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print("Download completed.")
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False

def update_status(post_id, platform, status, error_msg=""):
    """Update status of the job on the server."""
    payload = {
        "event": "post.status",
        "post_id": post_id,
        "status": status,
        "platform": platform,
        "data": {"error": error_msg} if error_msg else {}
    }
    try:
        res = requests.post(UPDATE_STATUS_API, json=payload, verify=False, timeout=15)
        res.raise_for_status()
        print(f"Updated status for {post_id} on server to: {status}")
        return True
    except Exception as e:
        print(f"Failed to update status on server: {e}")
        return False

def trigger_pfm_fallback(job):
    """Fallback: triggers Post For Me API on the server to make the post."""
    post_id = job.get("post_id")
    platform = job.get("platform", "").lower()
    
    # Shopee is not supported by PFM, so we must report failure directly
    if platform == "shopee":
        print("Shopee is not supported by Post For Me fallback. Marking job as failed.")
        update_status(post_id, platform, "failed", "Shopee is not supported by Post For Me fallback.")
        return False
        
    print(f"Triggering Post For Me fallback for post {post_id}...")
    payload = {
        "account_id": job.get("account_id"),
        "caption": job.get("caption"),
        "media_urls": job.get("media_urls"),
        "schedule_at": job.get("scheduled_at")
    }
    try:
        res = requests.post(PFM_FALLBACK_API, json=payload, verify=False, timeout=30)
        res.raise_for_status()
        res_data = res.json()
        if res_data.get("success"):
            print("Post For Me fallback successfully created the post!")
            update_status(post_id, platform, "success")
            return True
    except Exception as e:
        print(f"Post For Me fallback failed: {e}")
    
    update_status(post_id, platform, "failed", "Both Local and Post For Me fallback failed.")
    return False

# ─── Platform Automations ──────────────────────────────────────────────────

def post_facebook(video_path, caption):
    """Automate Facebook Reels upload via Playwright."""
    from auto_post_facebook import post_reel
    return post_reel(video_path, caption)

def post_tiktok(video_path, caption):
    """Automate TikTok upload via Playwright."""
    profile_dir = os.path.join(PROFILES_DIR, "tiktok")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        page = context.pages[0] if context.pages else context.new_page()
        print("Navigating to TikTok upload page...")
        page.goto("https://www.tiktok.com/creator-center/upload?lang=en", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        
        # Check if login is needed
        if "login" in page.url:
            print("Action Required: Please log in to TikTok in the browser window.")
            page.wait_for_timeout(60000)
            
        try:
            iframe = page.frame_locator("iframe[src*='upload']").first
            target = iframe.locator("button:has-text('Select file')").first
            if not target.is_visible():
                target = page.locator("text=Select file, select file").first
                
            with page.expect_file_chooser(timeout=20000) as fc_info:
                target.click()
            file_chooser = fc_info.value
            file_chooser.set_files(video_path)
            print("Video attached to TikTok.")
            page.wait_for_timeout(10000)
            
            # Fill caption
            caption_box = page.locator("div[role='textbox'], [contenteditable='true']").first
            if caption_box.is_visible():
                caption_box.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Delete")
                caption_box.fill(caption)
                page.wait_for_timeout(2000)
                
            # Click Publish
            publish_btn = page.locator("button:has-text('Post'), button:has-text('Publish')").first
            if publish_btn.is_visible() and publish_btn.is_enabled():
                publish_btn.click()
                print("Clicked Post on TikTok.")
                page.wait_for_timeout(15000)
                context.close()
                return True
        except Exception as e:
            print(f"TikTok upload automation error: {e}")
            
        context.close()
    return False

def post_youtube(video_path, caption):
    """Automate YouTube Shorts upload via Playwright."""
    profile_dir = os.path.join(PROFILES_DIR, "youtube")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        
        try:
            # Click Create -> Upload
            page.locator("#create-icon").first.click()
            page.wait_for_timeout(2000)
            
            with page.expect_file_chooser(timeout=15000) as fc_info:
                page.locator("text=Upload videos").first.click()
            file_chooser = fc_info.value
            file_chooser.set_files(video_path)
            print("Video attached to YouTube.")
            page.wait_for_timeout(8000)
            
            # Fill details (title/caption)
            title_input = page.locator("#textbox[role='textbox']").first
            if title_input.is_visible():
                title_input.click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Delete")
                title_input.fill(caption[:100]) # Youtube title limit 100
                page.wait_for_timeout(2000)
                
            # Click Next 3 times
            for _ in range(3):
                next_btn = page.locator("#next-button").first
                if next_btn.is_visible():
                    next_btn.click()
                    page.wait_for_timeout(3000)
                    
            # Choose Public
            page.locator("tp-yt-paper-radio-button[name='PUBLIC']").first.click()
            page.wait_for_timeout(2000)
            
            # Publish
            done_btn = page.locator("#done-button").first
            if done_btn.is_visible():
                done_btn.click()
                print("Clicked Publish on YouTube.")
                page.wait_for_timeout(10000)
                context.close()
                return True
        except Exception as e:
            print(f"YouTube upload error: {e}")
            
        context.close()
    return False

def post_pinterest(video_path, caption):
    """Automate Pinterest Pin creation via Playwright."""
    profile_dir = os.path.join(PROFILES_DIR, "pinterest")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.pinterest.com/pin-builder/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        
        try:
            with page.expect_file_chooser(timeout=15000) as fc_info:
                page.locator("input[type='file']").first.click()
            file_chooser = fc_info.value
            file_chooser.set_files(video_path)
            page.wait_for_timeout(5000)
            
            # Fill title and description
            title = page.locator("input[placeholder*='title']").first
            if title.is_visible():
                title.fill(caption[:60])
            desc = page.locator("textarea[placeholder*='tell everyone']").first
            if desc.is_visible():
                desc.fill(caption)
                
            publish = page.locator("button:has-text('Publish'), button:has-text('Save')").first
            if publish.is_visible():
                publish.click()
                print("Published on Pinterest.")
                page.wait_for_timeout(10000)
                context.close()
                return True
        except Exception as e:
            print(f"Pinterest error: {e}")
            
        context.close()
    return False

def post_x(video_path, caption):
    """Automate X (Twitter) posting via Playwright."""
    profile_dir = os.path.join(PROFILES_DIR, "x")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        
        try:
            box = page.locator("div[role='textbox'], [contenteditable='true']").first
            if box.is_visible():
                box.click()
                box.fill(caption)
                page.wait_for_timeout(2000)
                
            with page.expect_file_chooser(timeout=15000) as fc_info:
                page.locator("div[aria-label*='media'], div[data-testid='fileInput']").first.click()
            file_chooser = fc_info.value
            file_chooser.set_files(video_path)
            page.wait_for_timeout(8000)
            
            post_btn = page.locator("div[data-testid='tweetButton'], span:has-text('Post')").first
            if post_btn.is_visible():
                post_btn.click()
                print("Clicked Post on X.")
                page.wait_for_timeout(10000)
                context.close()
                return True
        except Exception as e:
            print(f"X (Twitter) posting error: {e}")
            
        context.close()
    return False

def post_instagram(video_path, caption):
    """Automate Instagram Reels/Post upload via Playwright."""
    profile_dir = os.path.join(PROFILES_DIR, "instagram")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        
        try:
            create_btn = page.locator("svg[aria-label='New post'], span:has-text('Create')").first
            create_btn.click()
            page.wait_for_timeout(3000)
            
            with page.expect_file_chooser(timeout=15000) as fc_info:
                page.locator("button:has-text('Select from computer')").first.click()
            file_chooser = fc_info.value
            file_chooser.set_files(video_path)
            page.wait_for_timeout(5000)
            
            for _ in range(2):
                next_btn = page.locator("div[role='button']:has-text('Next')").first
                if next_btn.is_visible():
                    next_btn.click()
                    page.wait_for_timeout(3000)
                    
            caption_box = page.locator("div[aria-label*='Write a caption']").first
            if caption_box.is_visible():
                caption_box.click()
                caption_box.fill(caption)
                page.wait_for_timeout(2000)
                
            share_btn = page.locator("div[role='button']:has-text('Share')").first
            if share_btn.is_visible():
                share_btn.click()
                print("Clicked Share on Instagram.")
                page.wait_for_timeout(15000)
                context.close()
                return True
        except Exception as e:
            print(f"Instagram upload error: {e}")
            
        context.close()
    return False

def post_threads(video_path, caption):
    """Automate Threads posting via Playwright."""
    profile_dir = os.path.join(PROFILES_DIR, "threads")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.threads.net/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        
        try:
            create_btn = page.locator("text=Start a thread..., New thread").first
            if create_btn.is_visible():
                create_btn.click()
                page.wait_for_timeout(2000)
                
            page.keyboard.type(caption)
            page.wait_for_timeout(2000)
            
            with page.expect_file_chooser(timeout=15000) as fc_info:
                page.locator("svg[aria-label='Attach media']").first.click()
            file_chooser = fc_info.value
            file_chooser.set_files(video_path)
            page.wait_for_timeout(5000)
            
            post_btn = page.locator("button:has-text('Post')").first
            if post_btn.is_visible():
                post_btn.click()
                print("Clicked Post on Threads.")
                page.wait_for_timeout(10000)
                context.close()
                return True
        except Exception as e:
            print(f"Threads upload error: {e}")
            
        context.close()
    return False

def post_linkedin(video_path, caption):
    """Automate LinkedIn posting via Playwright."""
    profile_dir = os.path.join(PROFILES_DIR, "linkedin")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        
        try:
            page.locator("button:has-text('Start a post')").first.click()
            page.wait_for_timeout(3000)
            
            with page.expect_file_chooser(timeout=15000) as fc_info:
                page.locator("button[aria-label*='Add media'], button[aria-label*='Add a photo']").first.click()
            file_chooser = fc_info.value
            file_chooser.set_files(video_path)
            page.wait_for_timeout(5000)
            
            done_btn = page.locator("button:has-text('Done'), button:has-text('Next')").first
            if done_btn.is_visible():
                done_btn.click()
                page.wait_for_timeout(2000)
                
            editor = page.locator("div[role='textbox'], div[aria-label*='editor']").first
            if editor.is_visible():
                editor.click()
                editor.fill(caption)
                page.wait_for_timeout(2000)
                
            post_btn = page.locator("button:has-text('Post')").first
            if post_btn.is_visible():
                post_btn.click()
                print("Clicked Post on LinkedIn.")
                page.wait_for_timeout(10000)
                context.close()
                return True
        except Exception as e:
            print(f"LinkedIn posting error: {e}")
            
        context.close()
    return False

def post_shopee(video_path, caption):
    """Automate Shopee Video upload via Playwright."""
    profile_dir = os.path.join(PROFILES_DIR, "shopee")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://creator.shopee.co.th/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        
        try:
            if "login" in page.url:
                print("Action Required: Please log in to Shopee Creator Center in the browser.")
                page.wait_for_timeout(60000)
                
            upload_menu = page.locator("text=Shopee Video, วิดีโอ, Upload, อัปโหลด").first
            if upload_menu.is_visible():
                upload_menu.click()
                page.wait_for_timeout(3000)
                
            with page.expect_file_chooser(timeout=15000) as fc_info:
                page.locator("input[type='file'], .upload-area, text=Select file").first.click()
            file_chooser = fc_info.value
            file_chooser.set_files(video_path)
            page.wait_for_timeout(8000)
            
            desc = page.locator("textarea, input[placeholder*='description']").first
            if desc.is_visible():
                desc.fill(caption)
                page.wait_for_timeout(2000)
                
            publish = page.locator("button:has-text('Publish'), button:has-text('โพสต์')").first
            if publish.is_visible():
                publish.click()
                print("Published on Shopee Video.")
                page.wait_for_timeout(10000)
                context.close()
                return True
        except Exception as e:
            print(f"Shopee upload error: {e}")
            
        context.close()
    return False

# ─── Orchestrator Loop ──────────────────────────────────────────────────────

AUTOMATION_HANDLERS = {
    "facebook": post_facebook,
    "tiktok": post_tiktok,
    "tiktok_business": post_tiktok,
    "youtube": post_youtube,
    "pinterest": post_pinterest,
    "x": post_x,
    "instagram": post_instagram,
    "threads": post_threads,
    "linkedin": post_linkedin,
    "shopee": post_shopee
}

def process_job(job):
    post_id = job.get("post_id")
    platform = job.get("platform", "").lower()
    caption = job.get("caption", "")
    media_urls = job.get("media_urls", [])
    
    print(f"\n==========================================")
    print(f"Handling job {post_id} for Platform: {platform}")
    print(f"==========================================")
    
    if not media_urls:
        print("No media URLs provided. Triggering Post For Me fallback...")
        trigger_pfm_fallback(job)
        return
        
    os.makedirs("temp_downloads", exist_ok=True)
    local_video_path = os.path.join("temp_downloads", f"{post_id}.mp4")
    if not download_video(media_urls[0], local_video_path):
        print("Media download failed. Triggering Post For Me fallback...")
        trigger_pfm_fallback(job)
        return
        
    handler = AUTOMATION_HANDLERS.get(platform)
    success = False
    
    if handler:
        try:
            print(f"Dispatching to local Playwright handler for: {platform}")
            success = handler(local_video_path, caption)
        except Exception as e:
            print(f"Local handler crashed: {e}")
    else:
        print(f"No local automation handler written for '{platform}' yet.")
        
    try:
        if os.path.exists(local_video_path):
            os.remove(local_video_path)
    except Exception:
        pass
        
    if success:
        print(f"Success! Job {post_id} posted locally.")
        update_status(post_id, platform, "success")
    else:
        print(f"Local upload failed or unavailable. Falling back to Post For Me...")
        trigger_pfm_fallback(job)

def main_loop():
    print("==================================================")
    print("      M2I Cross-Platform Auto Poster Active       ")
    print("==================================================")
    print(f"Target: {GET_JOBS_API}")
    print("Press Ctrl+C to stop.")
    
    while True:
        jobs = fetch_pending_jobs()
        if jobs:
            print(f"Found {len(jobs)} pending jobs.")
            for job in jobs:
                process_job(job)
                time.sleep(5)
        else:
            print("No pending jobs. Waiting 60 seconds...")
            
        time.sleep(60)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\nService stopped.")
