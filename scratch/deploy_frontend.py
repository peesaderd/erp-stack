import paramiko
import os

HOST = '89.167.82.205'
USER = 'openhands'
PASS = 'OpenHands@ERP2026'

print("1. Connecting SSH...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PASS)

sftp = ssh.open_sftp()
local_vue = 'scratch/PublicMenu_bulletproof.vue'
remote_vue = '/home/openhands/super-appsheet/frontend/src/views/PublicMenu.vue'
sftp.put(local_vue, remote_vue)
sftp.close()
print("2. Uploaded PublicMenu.vue to remote.")

print("3. Building frontend...")
stdin, stdout, stderr = ssh.exec_command("cd /home/openhands/super-appsheet/frontend && npm run build")
out = stdout.read().decode('utf-8')
err = stderr.read().decode('utf-8')
print("BUILD OUTPUT:\n", out)
if err:
    print("BUILD ERRORS:\n", err)

print("4. Restarting super-appsheet-frontend PM2...")
stdin, stdout, stderr = ssh.exec_command("pm2 restart super-appsheet-frontend")
print(stdout.read().decode('utf-8'))

ssh.close()
print("Frontend deployment complete!")
