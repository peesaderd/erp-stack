import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

sftp = ssh.open_sftp()
sftp.put(r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\kb-az-engine-v2.js', '/var/www/kidobits/js/kb-az-engine.js')
sftp.close()

stdin, stdout, stderr = ssh.exec_command('ls -l /var/www/kidobits/js/kb-az-engine.js')
print("Uploaded:", stdout.read().decode())
ssh.close()
