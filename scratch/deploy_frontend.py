import paramiko, os

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

sftp = ssh.open_sftp()
local_path = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\PosRestodash.vue'
remote_path = '/home/openhands/super-appsheet/frontend/src/views/PosRestodash.vue'

print('Uploading...', os.path.getsize(local_path), 'bytes')
sftp.put(local_path, remote_path)
sftp.close()
print('Uploaded successfully!')

stdin, stdout, stderr = ssh.exec_command('cd /home/openhands/super-appsheet/frontend && npm run build')
out = stdout.read().decode('utf-8')
err = stderr.read().decode('utf-8')
print('BUILD OUTPUT:\n', out[-400:])

stdin, stdout, stderr = ssh.exec_command('pm2 restart super-appsheet-frontend')
print('PM2:\n', stdout.read().decode('utf-8')[:300])
ssh.close()
print('Deploy complete!')
