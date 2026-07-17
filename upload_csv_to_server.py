import os
import paramiko

def main():
    ssh_ip = "89.167.82.205"
    ssh_user = "openhands"
    ssh_pass = "OpenHands@ERP2026"
    
    files_to_upload = [
        "trending_affiliate_products.csv",
        "generate_ai_scripts.py",
        "generate_50_tiktok_products.py",
        "download_and_upload_images.py"
    ]
    
    print(f"Connecting to remote server {ssh_ip}...")
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ssh_ip, username=ssh_user, password=ssh_pass, timeout=15)
        
        sftp = ssh.open_sftp()
        for local_file in files_to_upload:
            if os.path.exists(local_file):
                remote_file = f"/home/openhands/calm-noether/{local_file}"
                print(f"Uploading {local_file} -> {remote_file}...")
                sftp.put(local_file, remote_file)
        print("Upload successful for all files!")
        
        sftp.close()
        ssh.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
