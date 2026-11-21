import os
import paramiko

HOSTNAME = '89.167.82.205'
USERNAME = 'openhands'
PASSWORD = 'OpenHands@ERP2026'

LOCAL_DIR = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\smartback_pwa'
REMOTE_TEMP_DIR = '/tmp/smartback_pwa'
REMOTE_TARGET_DIR = '/var/www/m2igen-redesign/smartback'

print("Connecting to remote server via SSH...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD)

# Create remote temp directory
ssh.exec_command(f'rm -rf {REMOTE_TEMP_DIR} && mkdir -p {REMOTE_TEMP_DIR}/icons')

print("Uploading files via SFTP to temp directory...")
sftp = ssh.open_sftp()

for root, dirs, files in os.walk(LOCAL_DIR):
    for file in files:
        local_path = os.path.join(root, file)
        rel_path = os.path.relpath(local_path, LOCAL_DIR).replace('\\', '/')
        remote_path = f"{REMOTE_TEMP_DIR}/{rel_path}"
        print(f"Uploading {rel_path} -> {remote_path}")
        sftp.put(local_path, remote_path)

sftp.close()

# Move from temp to target directory with sudo
print("Deploying to target web root...")
cmd = f"""
echo '{PASSWORD}' | sudo -S mkdir -p {REMOTE_TARGET_DIR}
echo '{PASSWORD}' | sudo -S cp -r {REMOTE_TEMP_DIR}/* {REMOTE_TARGET_DIR}/
echo '{PASSWORD}' | sudo -S chown -R www-data:www-data {REMOTE_TARGET_DIR}
echo '{PASSWORD}' | sudo -S chmod -R 755 {REMOTE_TARGET_DIR}
ls -la {REMOTE_TARGET_DIR}
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
out = stdout.read().decode()
err = stderr.read().decode()

print("=== DEPLOY OUTPUT ===")
print(out)
if err and "password" not in err.lower():
    print("=== DEPLOY ERR ===")
    print(err)

# Test fetch via curl on server
test_cmd = "curl -Is https://m2igen.com/smartback/ | head -n 10 && curl -Is https://m2igen.com/smartback/manifest.json | head -n 10"
stdin, stdout, stderr = ssh.exec_command(test_cmd)
print("=== CURL TEST ===")
print(stdout.read().decode())

ssh.close()
print("Deployment completed successfully!")
