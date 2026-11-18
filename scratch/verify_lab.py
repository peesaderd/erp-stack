import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)
cmd = 'echo "OpenHands@ERP2026" | sudo -S chown www-data:www-data /var/www/kidobits/chinese_lab.html && grep -n "evaluatePhonemeMatch" /var/www/kidobits/chinese_lab.html'
stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
ssh.close()
