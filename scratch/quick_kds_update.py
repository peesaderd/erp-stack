import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)
sftp = ssh.open_sftp()
sftp.put('scratch/PosKdsStandalone.vue', '/home/openhands/super-appsheet/frontend/src/views/PosKdsStandalone.vue')
sftp.close()

stdin, stdout, stderr = ssh.exec_command('cd /home/openhands/super-appsheet/frontend && npm run build && pm2 reload super-appsheet-frontend')
print(stdout.read().decode())

cmd = 'cd /home/openhands/super-appsheet && git add frontend/src/views/PosKdsStandalone.vue && git commit -m "fix: standalone fullscreen KDS" && git push origin theme/bakehouse'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

ssh.close()
