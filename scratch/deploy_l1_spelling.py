import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

sftp = ssh.open_sftp()
sftp.put('scratch/theme_phonicsLesson_l1_spelling.html', '/tmp/theme_phonicsLesson.html')
sftp.close()

cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_phonicsLesson.html /var/www/kidobits/theme/theme_phonicsLesson.html && echo "OpenHands@ERP2026" | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_phonicsLesson.html && echo "OpenHands@ERP2026" | sudo -S chmod 644 /var/www/kidobits/theme/theme_phonicsLesson.html'
stdin, stdout, stderr = ssh.exec_command(cmd)
print("Deploy output:", stdout.read().decode())
print("Deploy error:", stderr.read().decode())

stdin, stdout, stderr = ssh.exec_command('ls -la /var/www/kidobits/theme/theme_phonicsLesson.html')
print("File check:", stdout.read().decode())

ssh.close()
