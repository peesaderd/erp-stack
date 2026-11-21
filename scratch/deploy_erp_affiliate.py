import os
import paramiko

HOSTNAME = '89.167.82.205'
USERNAME = 'openhands'
PASSWORD = 'OpenHands@ERP2026'

LOCAL_BACKEND = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\smartback_backend'
REMOTE_BACKEND = '/home/openhands/smartback_backend'
LOCAL_MODULE = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\modules\affiliate'
REMOTE_MODULE = '/home/openhands/erp-stack/modules/affiliate'

print("Connecting to remote server...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD)

# Create remote directories
ssh.exec_command(f"mkdir -p {REMOTE_BACKEND}/affiliate {REMOTE_MODULE}")

sftp = ssh.open_sftp()

def upload_dir(local_dir, remote_dir):
    for root, dirs, files in os.walk(local_dir):
        rel_path = os.path.relpath(root, local_dir)
        target_dir = remote_dir if rel_path == '.' else f"{remote_dir}/{rel_path}".replace('\\', '/')
        try:
            sftp.mkdir(target_dir)
        except:
            pass
        for f in files:
            local_file = os.path.join(root, f)
            remote_file = f"{target_dir}/{f}".replace('\\', '/')
            print(f"Uploading {local_file} -> {remote_file}")
            sftp.put(local_file, remote_file)

print("\n--- 1. Uploading smartback backend ---")
upload_dir(LOCAL_BACKEND, REMOTE_BACKEND)

print("\n--- 2. Uploading erp-stack module ---")
upload_dir(LOCAL_MODULE, REMOTE_MODULE)

sftp.close()

# Restart service
cmd = f"""
echo '{PASSWORD}' | sudo -S systemctl restart smartback
sleep 2
echo '{PASSWORD}' | sudo -S systemctl status smartback --no-pager
"""
stdin, stdout, stderr = ssh.exec_command(cmd)
print("\n--- Remote Service Status ---\n", stdout.read().decode())
print("Stderr:\n", stderr.read().decode())

ssh.close()
print("\nDeployment completed successfully!")
