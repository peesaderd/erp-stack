import os
import sys
import json
import time
import requests
import urllib3
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

# Disable SSL warnings for self-signed certificates or proxy issues
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Reconfigure standard output to support UTF-8 on Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Server Base URLs
SERVER_URL = "https://openhands.m2igen.com"
GET_PENDING_POSTS_API = f"{SERVER_URL}/api/tiktok/ugc/posts"
UPDATE_STATUS_API = f"{SERVER_URL}/api/tiktok/ugc/webhook/pfm"

def fetch_pending_jobs():
    """Poll the remote server for pending post jobs."""
    print("Polling server for pending posts...")
    try:
        # Request only pending posts
        response = requests.get(GET_PENDING_POSTS_API, params={"status": "pending"}, verify=False, timeout=15)
        response.raise_for_status()
        res_data = response.json()
        if res_data.get("success"):
            posts = res_data.get("posts", [])
            # Filter posts to find pending ones (in case query param is ignored)
            pending_posts = [p for p in posts if p.get("status") == "pending"]
            return pending_posts
    except Exception as e:
        print(f"Error fetching jobs: {e}")
    return []

def download_video(media_url, save_path):
    """Download video from the remote server locally."""
    # Handle relative URLs (e.g., /tiktok/static/videos/...)
    full_url = media_url
    if media_url.startswith("/"):
        full_url = urljoin(SERVER_URL, media_url)
        
    print(f"Downloading video from {full_url} to {save_path}...")
    try:
        response = requests.get(full_url, verify=False, stream=True, timeout=60)
        response.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print("Download completed successfully!")
        return True
    except Exception as e:
        print(f"Failed to download video: {e}")
        return False

def update_post_status(post_id, platform, status, error_msg=""):
    """Notify the remote server of the job outcome via the webhook endpoint."""
    payload = {
        "event": "post.status",
        "post_id": post_id,
        "status": status,
        "platform": platform,
        "data": {"error": error_msg} if error_msg else {}
    }
    print(f"Updating post {post_id} status on server to: {status}")
    try:
        response = requests.post(UPDATE_STATUS_API, json=payload, verify=False, timeout=15)
        response.raise_for_status()
        print("Server status updated successfully.")
        return True
    except Exception as e:
        print(f"Failed to update server status: {e}")
        return False

def run_facebook_upload_flow(video_path, caption):
    """Reuse our auto_post_facebook automation to upload video to Reels."""
    # We import post_reel dynamically from our existing auto_post_facebook.py
    try:
        from auto_post_facebook import post_reel
        return post_reel(video_path, caption)
    except Exception as e:
        print(f"Error executing Facebook post automation: {e}")
        return False

def process_job(job):
    post_id = job.get("post_id")
    platform = job.get("platform", "").lower()
    caption = job.get("caption", "")
    media_urls = job.get("media_urls", [])
    
    print(f"\nProcessing Job {post_id} | Platform: {platform}")
    
    # 1. Validate Media
    if not media_urls:
        print("Error: No media files provided for this post.")
        update_post_status(post_id, platform, "failed", "No media URLs in request.")
        return
        
    media_url = media_urls[0]
    
    # Create temp directory if not exists
    os.makedirs("temp_downloads", exist_ok=True)
    local_video_path = os.path.join("temp_downloads", f"{post_id}.mp4")
    
    # 2. Download Media
    if not download_video(media_url, local_video_path):
        update_post_status(post_id, platform, "failed", "Could not download media file.")
        return
        
    # 3. Execute Automation
    success = False
    error_msg = ""
    
    if platform == "facebook":
        print("Executing Facebook Reels upload flow...")
        success = run_facebook_upload_flow(local_video_path, caption)
        if not success:
            error_msg = "Facebook auto post automation script failed."
    elif platform in ["tiktok", "tiktok_business"]:
        print("TikTok Reels upload flow starting (not yet fully mapped, mapping default placeholder)...")
        # In a real setup, we would call auto_post_tiktok.py
        # For now, we will print and set status to failed to indicate TikTok pipeline needs integration
        error_msg = "TikTok auto post not yet configured on this worker."
    else:
        error_msg = f"Platform '{platform}' not supported by this local worker."
        
    # 4. Cleanup local file
    try:
        if os.path.exists(local_video_path):
            os.remove(local_video_path)
    except Exception:
        pass
        
    # 5. Submit Result
    if success:
        update_post_status(post_id, platform, "success")
    else:
        update_post_status(post_id, platform, "failed", error_msg)

def worker_loop():
    print("==================================================")
    print("   M2I Local Automation Bridge Worker Active      ")
    print("==================================================")
    print(f"Monitoring: {GET_PENDING_POSTS_API}")
    print("Press Ctrl+C to stop.")
    
    while True:
        jobs = fetch_pending_jobs()
        if jobs:
            print(f"Found {len(jobs)} pending jobs to process.")
            for job in jobs:
                process_job(job)
                # Sleep briefly between jobs
                time.sleep(5)
        else:
            print("No pending jobs. Waiting 60 seconds...")
            
        time.sleep(60)

if __name__ == "__main__":
    try:
        worker_loop()
    except KeyboardInterrupt:
        print("\nWorker stopped by user.")
