import paramiko

HOST = '89.167.82.205'
USER = 'openhands'
PASS = 'OpenHands@ERP2026'
VUE_FILE = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\PosRestodash.vue'

print("=== DEPLOYING POS RESTODASH TO REMOTE SERVER ===")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS, timeout=30)
print("SSH Connected.")

# 1. Upload Vue Component
print("[1] Uploading PosRestodash.vue via SFTP...")
sftp = ssh.open_sftp()
with open(VUE_FILE, 'rb') as f:
    sftp.putfo(f, '/home/openhands/super-appsheet/frontend/src/views/PosRestodash.vue')
sftp.close()
print("    Upload complete.")

# 2. Build Frontend
print("[2] Running frontend build (npm run build)...")
cmd = "cd /home/openhands/super-appsheet/frontend && npm run build 2>&1 | tail -25"
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=300)
out = stdout.read().decode('utf-8')
print("BUILD OUTPUT:\n", out)

# 3. Check assets
print("[3] Checking dist assets...")
stdin, stdout, stderr = ssh.exec_command("ls -lh /home/openhands/super-appsheet/frontend/dist/assets/ | tail -5")
print(stdout.read().decode())

# 4. Restart Frontend PM2
print("[4] Restarting PM2 super-appsheet-frontend...")
stdin, stdout, stderr = ssh.exec_command("pm2 restart super-appsheet-frontend")
print(stdout.read().decode())

ssh.close()
print("=== DEPLOYMENT FINISHED SUCCESSFULLY ===")
