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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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

def get_bing_image_url(name, category):
    # Split query to keep it clean but specific
    clean_name = name
    if len(name) > 40:
        parts = re.split(r'[\(\)\[\]\s]', name)
        clean_name = " ".join([p for p in parts[:4] if p])
    
    # Append category context to avoid homonyms (e.g. Papa -> Pope)
    context = ""
    cat_lower = category.lower()
    if "beauty" in cat_lower or "personal care" in cat_lower:
        context = "skincare cosmetic"
    elif "supplement" in cat_lower or "food" in cat_lower:
        context = "supplement product"
    elif "kitchen" in cat_lower or "home" in cat_lower or "living" in cat_lower:
        context = "home product"
        
    query = f"{clean_name} {context}".strip()
    
    url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, verify=False, timeout=10)
        if response.status_code == 200:
            # Find image URLs in murl
            matches = re.findall(r'&quot;murl&quot;:&quot;(http[^\s&]+?)&quot;', response.text)
            if not matches:
                matches = re.findall(r'"murl":"(http[^\s"]+?)"', response.text)
            
            # Filter matches
            for match in matches:
                if any(x in match.lower() for x in [".jpg", ".png", ".jpeg", ".webp", "susercontent", "shopee", "lazada", "alicdn"]):
                    return match
            if matches:
                return matches[0]
    except Exception as e:
        print(f"  -> Error searching Bing for '{query}': {e}")
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
        
    if "Image Filename" not in fieldnames:
        fieldnames.append("Image Filename")
        
    print(f"Starting image search and download for {len(rows)} products...")
    
    downloaded_files = []
    
    for idx, row in enumerate(rows):
        pid = row.get("Product ID")
        name = row.get("Product Name")
        category = row.get("Category", "")
        
        # We FORCE re-download to overwrite the wrong Pope images
        print(f"[{idx+1}/{len(rows)}] Searching image for: {name[:40]}...")
        
        img_url = get_bing_image_url(name, category)
        if img_url:
            # Get extension from URL, fallback to .jpg
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
            
        time.sleep(0.5)
            
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
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ssh_ip, username=ssh_user, password=ssh_pass, timeout=15)
        
        # Ensure remote directory exists
        print(f"Creating remote directory if not exists: {remote_dir}")
        ssh.exec_command(f"mkdir -p {remote_dir}")
        
        # Clear out old images on the remote server
        print("Clearing old images from the remote server...")
        ssh.exec_command(f"rm -rf {remote_dir}/*")
        
        # Start SFTP
        sftp = ssh.open_sftp()
        
        print("Uploading new correct images to remote server...")
        uploaded_count = 0
        for pid, filename in downloaded_files:
            local_path = os.path.join(local_image_dir, filename)
            remote_path = f"{remote_dir}/{filename}"
            if os.path.exists(local_path):
                sftp.put(local_path, remote_path)
                uploaded_count += 1
                
        sftp.close()
        
        # Update database with correct image keys
        print("\nUpdating remote database with correct images...")
        sql_updates = ""
        for pid, filename in downloaded_files:
            # We escape single quotes in product_id (though they are numeric, it's safer)
            safe_pid = pid.replace("'", "''")
            safe_fn = filename.replace("'", "''")
            
            # Construct JSON updates
            sql_updates += f"""
            UPDATE products
            SET data = (data::jsonb || jsonb_build_object(
                'image_filename', '{safe_fn}',
                'image', '/product_images/{safe_fn}',
                'image_url', 'http://89.167.82.205:8108/product_images/{safe_fn}',
                'image_path', '/home/openhands/calm-noether/product_images/{safe_fn}'
            ))::json
            WHERE data::jsonb->>'product_id' = '{safe_pid}';
            """
            
        # Execute batch update
        db_cmd = f'sudo docker exec -i db psql -U openhands -d productdb -c "{sql_updates}"'
        stdin, stdout, stderr = ssh.exec_command(db_cmd)
        print("Database Update Stdout:")
        print(stdout.read().decode('utf-8'))
        print("Database Update Stderr:")
        print(stderr.read().decode('utf-8'))
        
        ssh.close()
        print(f"\nSuccessfully downloaded, uploaded {uploaded_count} images, and updated the database!")
        
    except Exception as e:
        print(f"Error connecting or uploading via SSH/SFTP: {e}")
        
if __name__ == "__main__":
    main()
