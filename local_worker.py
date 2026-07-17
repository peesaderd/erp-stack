import time
import requests

SERVER_URL = "http://89.167.82.205:18123"

def process_job(job):
    job_id = job["id"]
    action = job["action"]
    payload = job.get("payload") or {}
    
    print(f"\n[Worker] Processing Job {job_id} | Action: {action}")
    
    # 1. Update status to 'processing'
    try:
        r = requests.post(f"{SERVER_URL}/api/v1/jobs/{job_id}/status", json={"status": "processing"})
        r.raise_for_status()
    except Exception as e:
        print(f"  -> Failed to update status to processing: {e}")
        return
        
    # 2. Execute local logic based on action type
    result_data = {}
    success = True
    
    try:
        if action == "test_job":
            print(f"  -> Running test job. Payload: {payload}")
            time.sleep(2)
            result_data = {"message": "Test job completed successfully locally!", "timestamp": time.time()}
            
        elif action == "refresh_shopee_cookies":
            print("  -> Refreshing Shopee cookies...")
            # Here we could launch the headed browser or run a command
            # For demonstration, we simulate success
            result_data = {"status": "success", "message": "Shopee cookies refreshed locally!"}
            
        elif action == "scrape_products":
            import subprocess
            import sys
            
            print("  -> Step 1: Scraping fresh products from TikTok...")
            p1 = subprocess.run([sys.executable, "scrape_tiktok_products.py"], capture_output=True, text=True)
            if p1.returncode != 0:
                raise Exception(f"TikTok Scraper failed: {p1.stderr or p1.stdout}")
            print("     [OK] Scraped successfully.")
            
            print("  -> Step 2: Downloading and uploading product images to server...")
            p2 = subprocess.run([sys.executable, "download_and_upload_images.py"], capture_output=True, text=True)
            if p2.returncode != 0:
                raise Exception(f"Image Downloader/Deployer failed: {p2.stderr or p2.stdout}")
            print("     [OK] Images uploaded successfully.")
            
            print("  -> Step 3: Importing scraped products into remote PostgreSQL database...")
            p3 = subprocess.run([sys.executable, "create_import_sql.py"], capture_output=True, text=True)
            if p3.returncode != 0:
                raise Exception(f"SQL Database Importer failed: {p3.stderr or p3.stdout}")
            print("     [OK] Database imported successfully.")
            
            result_data = {
                "status": "success",
                "message": "Scraped, downloaded/uploaded images, and imported products to SQL database successfully!"
            }
            
        else:
            print(f"  -> Unknown action: {action}")
            success = False
            result_data = {"error": f"Unknown action: {action}"}
            
    except Exception as e:
        print(f"  -> Error executing job: {e}")
        success = False
        result_data = {"error": str(e)}
        
    # 3. Update status to completed or failed
    final_status = "completed" if success else "failed"
    print(f"  -> Job {job_id} finished with status: {final_status}")
    try:
        r = requests.post(f"{SERVER_URL}/api/v1/jobs/{job_id}/status", json={
            "status": final_status,
            "result": result_data
        })
        r.raise_for_status()
        print(f"  -> Status updated on server.")
    except Exception as e:
        print(f"  -> Failed to send result to server: {e}")

def main():
    print(f"=== Starting Calm-Noether Local Worker ===")
    print(f"Polling server: {SERVER_URL} for pending jobs...")
    
    while True:
        try:
            # Poll for pending jobs
            response = requests.get(f"{SERVER_URL}/api/v1/jobs/pending", timeout=10)
            if response.status_code == 200:
                pending_jobs = response.json()
                if pending_jobs:
                    print(f"\n[Worker] Found {len(pending_jobs)} pending job(s).")
                    # Process the first job in the queue
                    process_job(pending_jobs[0])
            else:
                print(f"[Worker] Server returned status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"[Worker] Connection error: {e}")
            
        # Poll interval: 5 seconds
        time.sleep(5)

if __name__ == "__main__":
    main()
