import os
import csv
import sys
import time
import re
import urllib3
import requests
import paramiko

def download_image(url, save_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"  -> Error downloading {url}: {e}")
    return False

def get_bing_image_url(query):
    # Filter search query to remove long generic descriptions
    # e.g. "PAPA FEEL 577 เซรั่มลดเลือนฝ้ากระและรอยสิว" -> "PAPA FEEL 577 เซรั่ม"
    clean_query = query
    if len(query) > 40:
        # Take first 40 characters or split by space/brackets
        parts = re.split(r'[\(\)\[\]\s]', query)
        # Take first few parts to keep it specific but short
        clean_query = " ".join([p for p in parts[:4] if p])
        
    url = f"https://www.bing.com/images/search?q={requests.utils.quote(clean_query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
    }
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        if response.status_code == 200:
            # Find all murl URLs
            matches = re.findall(r'&quot;murl&quot;:&quot;(http[^\s&]+?)&quot;', response.text)
            if not matches:
                matches = re.findall(r'"murl":"(http[^\s"]+?)"', response.text)
            
            # Filter out non-image extensions or bad domains if any
            for match in matches:
                if any(x in match.lower() for x in [".jpg", ".png", ".jpeg", ".webp", "susercontent", "shopee", "lazada", "alicdn"]):
                    return match
            # Fallback to first URL found
            if matches:
                return matches[0]
    except Exception as e:
        print(f"  -> Error searching Bing for '{clean_query}': {e}")
    return None

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    input_file = "trending_affiliate_products.csv"
    local_image_dir = "product_images"
    os.makedirs(local_image_dir, exist_ok=True)
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found!")
        sys.exit(1)
        
    print(f"Reading products from {input_file}...")
    with open(input_file, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
        
    # Add new column for image filename if not present
    if "Image Filename" not in fieldnames:
        fieldnames.append("Image Filename")
        
    print(f"Starting image search and download for {len(rows)} products using Bing...")
    
    downloaded_files = []
    
    for idx, row in enumerate(rows):
        pid = row.get("Product ID")
        name = row.get("Product Name")
        existing_img = row.get("Image Filename")
        
        # Skip if already downloaded
        if existing_img and os.path.exists(os.path.join(local_image_dir, existing_img)):
            print(f"[{idx+1}/{len(rows)}] Image already exists for: {name[:40]}")
            downloaded_files.append((pid, existing_img))
            continue
            
        print(f"[{idx+1}/{len(rows)}] Searching image for: {name[:40]}...")
        
        img_url = get_bing_image_url(name)
        if img_url:
            # Try to get extension from URL, fallback to .jpg
            ext = ".jpg"
            if "." in img_url.split("/")[-1]:
                potential_ext = "." + img_url.split("/")[-1].split(".")[-1].split("?")[0]
                if potential_ext.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                    ext = potential_ext.lower()
                    
            filename = f"{pid}{ext}"
            save_path = os.path.join(local_image_dir, filename)
            
            print(f"  -> Found image URL: {img_url[:80]}...")
            if download_image(img_url, save_path):
                print(f"  -> Downloaded and saved as: {filename}")
                row["Image Filename"] = filename
                downloaded_files.append((pid, filename))
            else:
                print("  -> Failed to download image.")
        else:
            print("  -> No image results found.")
            
        # Small delay to avoid hammering Bing
        time.sleep(1.0)
            
    # Save the updated CSV
    print(f"Saving updated CSV back to {input_file}...")
    with open(input_file, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            
    # Upload to remote server via SSH / SFTP
    print("\nConnecting to remote cloud server (89.167.82.205)...")
    ssh_ip = "89.167.82.205"
    ssh_user = "openhands"
    ssh_pass = "OpenHands@ERP2026"
    remote_dir = "/home/openhands/calm-noether/product_images"
    
    try:
        # Create SSH Client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ssh_ip, username=ssh_user, password=ssh_pass, timeout=15)
        
        # Ensure remote directory exists
        print(f"Creating remote directory if not exists: {remote_dir}")
        ssh.exec_command(f"mkdir -p {remote_dir}")
        
        # Start SFTP
        sftp = ssh.open_sftp()
        
        print("Uploading images to remote server...")
        uploaded_count = 0
        for pid, filename in downloaded_files:
            local_path = os.path.join(local_image_dir, filename)
            remote_path = f"{remote_dir}/{filename}"
            if os.path.exists(local_path):
                sftp.put(local_path, remote_path)
                uploaded_count += 1
                
        sftp.close()
        ssh.close()
        print(f"\nSuccessfully uploaded {uploaded_count} images to remote server at {remote_dir}!")
        
    except Exception as e:
        print(f"Error connecting or uploading via SSH/SFTP: {e}")
        
if __name__ == "__main__":
    main()
