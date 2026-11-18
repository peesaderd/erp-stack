import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

sftp = ssh.open_sftp()
sftp.put(r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\kb-az-engine-v2.js', '/tmp/kb-az-engine-v2.js')
sftp.close()

cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/kb-az-engine-v2.js /var/www/kidobits/js/kb-az-engine.js && echo "OpenHands@ERP2026" | sudo -S chown www-data:www-data /var/www/kidobits/js/kb-az-engine.js && ls -l /var/www/kidobits/js/kb-az-engine.js'
stdin, stdout, stderr = ssh.exec_command(cmd)
print("Uploaded & Moved:", stdout.read().decode())
print("STDERR:", stderr.read().decode())
ssh.close()
