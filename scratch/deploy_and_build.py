import paramiko
import time

HOST = '89.167.82.205'
USER = 'openhands'
PASS = 'OpenHands@ERP2026'

print("Connecting to server...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=15)
print("Connected.")

# 1. Upload fixed PosRestodash.vue
print("Uploading PosRestodash.vue...")
sftp = client.open_sftp()
sftp.put('scratch/PosRestodash_fixed.vue', '/home/openhands/super-appsheet/frontend/src/views/PosRestodash.vue')
sftp.close()
print("Uploaded successfully.")

# 2. Build frontend
print("Running npm run build...")
stdin, stdout, stderr = client.exec_command('cd /home/openhands/super-appsheet/frontend && npm run build')
build_out = stdout.read().decode('utf-8')
build_err = stderr.read().decode('utf-8')
print("Build output:\n", build_out[-1500:])
if build_err.strip():
    print("Build err:\n", build_err[-1000:])

# 3. Check dist assets
stdin, stdout, stderr = client.exec_command('ls -la /home/openhands/super-appsheet/frontend/dist/assets/PosRestodash*')
print("New dist assets:\n", stdout.read().decode('utf-8'))

# 4. Check if node server needs restart or pm2
stdin, stdout, stderr = client.exec_command('pm2 list 2>/dev/null || echo "no pm2"')
print("PM2:\n", stdout.read().decode('utf-8'))

client.close()
print("Done!")
