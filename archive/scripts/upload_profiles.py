import os
import sys
import paramiko

# Directory names (lowercase) to exclude from upload to keep size small and transfer instant
EXCLUDE_DIR_PATTERNS = {
    "cache", "gpucache", "service worker", "blob_storage", "code cache",
    "network action predictor", "videodecodestats", "shared_proto_db", 
    "databases", "local extension settings", "extension rules", "crashpad",
    "extensions", "extension state", "extension scripts", "background_categories"
}

# File extensions to exclude
EXCLUDE_EXTENSIONS = {".log", ".tmp", ".bak", ".dld", ".lock"}

def should_exclude(path):
    """Check if the path or any of its parent folders match the exclusion patterns."""
    parts = path.lower().replace('\\', '/').split('/')
    for part in parts:
        for pattern in EXCLUDE_DIR_PATTERNS:
            if pattern in part:
                return True
    return False

def sftp_upload_dir(sftp, local_dir, remote_dir, base_local_dir):
    """Recursively upload a local directory to a remote server, ignoring excluded files."""
    try:
        sftp.mkdir(remote_dir)
    except IOError:
        pass  # Already exists
        
    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = f"{remote_dir}/{item}"
        
        # Calculate path relative to the platform root folder
        relative_path = os.path.relpath(local_path, base_local_dir)
        
        if should_exclude(relative_path):
            continue
            
        if os.path.isdir(local_path):
            sftp_upload_dir(sftp, local_path, remote_path, base_local_dir)
        else:
            _, ext = os.path.splitext(item.lower())
            if ext in EXCLUDE_EXTENSIONS:
                continue
                
            try:
                sftp.put(local_path, remote_path)
                # Print only important files to keep output clean
                if item.lower() in ("cookies", "preferences", "secure preferences") or "local storage" in relative_path.lower():
                    size_kb = os.path.getsize(local_path) / 1024.0
                    print(f"  -> Sent: {relative_path.replace('\\', '/')} ({size_kb:.1f} KB)")
            except Exception as e:
                pass # Skip locked/system files

def main():
    hostname = "89.167.82.205"
    username = "openhands"
    password = "OpenHands@ERP2026"
    
    local_profiles = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profiles")
    remote_profiles = "/home/openhands/erp-stack/tiktok-ugc-studio/browser_profiles"
    
    if not os.path.exists(local_profiles):
        print(f"Error: Local 'browser_profiles' directory not found at: {local_profiles}")
        print("Please run 'python open_profile.py <platform>' first.")
        sys.exit(1)
        
    platforms = [d for d in os.listdir(local_profiles) if os.path.isdir(os.path.join(local_profiles, d))]
    if not platforms:
        print("No browser profiles found to upload.")
        sys.exit(0)
        
    print(f"Found profiles for: {', '.join(platforms)}")
    print("Connecting to server...")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(hostname, port=22, username=username, password=password, timeout=30)
        sftp = ssh.open_sftp()
        
        try:
            sftp.mkdir(remote_profiles)
        except IOError:
            pass
            
        for platform in platforms:
            print(f"\nUploading session for '{platform}' (optimized)...")
            local_plat_dir = os.path.join(local_profiles, platform)
            remote_plat_dir = f"{remote_profiles}/{platform}"
            
            # Clean remote target directory for this platform to prevent old files mismatch
            try:
                ssh.exec_command(f"rm -rf {remote_plat_dir}")
            except Exception:
                pass
                
            sftp_upload_dir(sftp, local_plat_dir, remote_plat_dir, local_plat_dir)
            print(f"Successfully uploaded session for '{platform}'!")
            
        print("\nAll session profiles uploaded successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
