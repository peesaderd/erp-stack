import os
import paramiko

HOSTNAME = '89.167.82.205'
USERNAME = 'openhands'
PASSWORD = 'OpenHands@ERP2026'

LOCAL_BACKEND_DIR = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\smartback_backend'
LOCAL_PWA_DIR = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\smartback_pwa'
REMOTE_BACKEND_DIR = '/home/openhands/smartback_backend'
REMOTE_PWA_DIR = '/var/www/m2igen-redesign/smartback'

print("Connecting to remote server...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD)

# 1. Create remote backend dir & temp dir
ssh.exec_command(f'mkdir -p {REMOTE_BACKEND_DIR} /tmp/sb_pwa')

sftp = ssh.open_sftp()

# Upload backend files
for f in os.listdir(LOCAL_BACKEND_DIR):
    local_p = os.path.join(LOCAL_BACKEND_DIR, f)
    if os.path.isfile(local_p):
        remote_p = f"{REMOTE_BACKEND_DIR}/{f}"
        print(f"Uploading backend {f} -> {remote_p}")
        sftp.put(local_p, remote_p)

# Upload updated PWA index.html to /tmp/sb_pwa/
sftp.put(os.path.join(LOCAL_PWA_DIR, 'index.html'), "/tmp/sb_pwa/index.html")
print("Uploaded PWA index.html to /tmp/sb_pwa/index.html")

sftp.close()

# Copy PWA index.html to target with sudo
cmd_pwa = f"""
echo '{PASSWORD}' | sudo -S cp /tmp/sb_pwa/index.html {REMOTE_PWA_DIR}/index.html
echo '{PASSWORD}' | sudo -S chown www-data:www-data {REMOTE_PWA_DIR}/index.html
echo '{PASSWORD}' | sudo -S chmod 755 {REMOTE_PWA_DIR}/index.html
"""
stdin, stdout, stderr = ssh.exec_command(cmd_pwa)
stdout.read()

# 2. Setup Systemd Service
systemd_unit = """[Unit]
Description=SmartBack Cashback Backend FastAPI
After=network.target

[Service]
Type=simple
User=openhands
WorkingDirectory=/home/openhands/smartback_backend
Environment=SMARTBACK_DB_PATH=/home/openhands/smartback_backend/smartback.db
ExecStart=/usr/local/bin/uvicorn main:app --host 127.0.0.1 --port 8765
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""

create_service_cmd = f"""
echo '{PASSWORD}' | sudo -S bash -c 'cat << "EOF" > /etc/systemd/system/smartback.service
{systemd_unit}
EOF'
echo '{PASSWORD}' | sudo -S systemctl daemon-reload
echo '{PASSWORD}' | sudo -S systemctl restart smartback
echo '{PASSWORD}' | sudo -S systemctl enable smartback
sleep 2
echo '{PASSWORD}' | sudo -S systemctl status smartback --no-pager
"""

print("Setting up and starting smartback.service...")
stdin, stdout, stderr = ssh.exec_command(create_service_cmd)
print("=== SERVICE STATUS ===")
print(stdout.read().decode())

# 3. Check if Nginx config has /smartback/api/
nginx_check = "grep -c 'location ^~ /smartback/api/' /etc/nginx/sites-enabled/m2igen.com || true"
stdin, stdout, stderr = ssh.exec_command(nginx_check)
has_nginx = stdout.read().decode().strip()

if has_nginx == '0':
    print("Injecting Nginx proxy location block for /smartback/api/...")
    inject_script = f"""
echo '{PASSWORD}' | sudo -S python3 -c "
with open('/etc/nginx/sites-enabled/m2igen.com', 'r') as f:
    content = f.read()

block = '''
    # SmartBack Cashback API - added 2026-11-21
    location ^~ /smartback/api/ {{
        proxy_pass http://127.0.0.1:8765/;
        proxy_http_version 1.1;
        proxy_set_header Host \\$host;
        proxy_set_header X-Real-IP \\$remote_addr;
        proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \\$scheme;
        proxy_read_timeout 30s;
    }}
'''

target = '    # Main site — static frontend'
if target in content:
    new_content = content.replace(target, block + '\\\\n' + target)
    with open('/etc/nginx/sites-enabled/m2igen.com', 'w') as f:
        f.write(new_content)
    print('Injected successfully!')
else:
    print('Target not found')
"
echo '{PASSWORD}' | sudo -S nginx -t && echo '{PASSWORD}' | sudo -S systemctl reload nginx
"""
    stdin, stdout, stderr = ssh.exec_command(inject_script)
    print("=== NGINX INJECT & RELOAD ===")
    print(stdout.read().decode())
    print(stderr.read().decode())
else:
    print("Nginx proxy block already present.")

# 4. Test API locally and publicly
test_script = """
sleep 1
curl -s http://127.0.0.1:8765/wallet/user_pw_9821 | head -n 30
echo ""
curl -s https://m2igen.com/smartback/api/wallet/user_pw_9821 | head -n 30
"""
stdin, stdout, stderr = ssh.exec_command(test_script)
print("=== API TEST ===")
print(stdout.read().decode())

ssh.close()
print("All tasks completed!")
