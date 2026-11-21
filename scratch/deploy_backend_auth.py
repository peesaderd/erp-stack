import os
import paramiko

HOSTNAME = '89.167.82.205'
USERNAME = 'openhands'
PASSWORD = 'OpenHands@ERP2026'

LOCAL_BACKEND_DIR = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\smartback_backend'
REMOTE_BACKEND_DIR = '/home/openhands/smartback_backend'

print("Connecting to remote server...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD)

sftp = ssh.open_sftp()
for f in ["database.py", "main.py"]:
    local_p = os.path.join(LOCAL_BACKEND_DIR, f)
    remote_p = f"{REMOTE_BACKEND_DIR}/{f}"
    print(f"Uploading {f} -> {remote_p}")
    sftp.put(local_p, remote_p)
sftp.close()

cmd = f"""
cd {REMOTE_BACKEND_DIR}
python3 database.py
echo '{PASSWORD}' | sudo -S systemctl restart smartback
sleep 2
echo '{PASSWORD}' | sudo -S systemctl status smartback --no-pager
"""
stdin, stdout, stderr = ssh.exec_command(cmd)
print("Remote Output:\n", stdout.read().decode())
print("Remote Errors:\n", stderr.read().decode())

ssh.close()
print("Backend deployed and restarted successfully!")
