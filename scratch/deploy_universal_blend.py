import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

# Backup remote file first
stdin, stdout, stderr = ssh.exec_command('echo "OpenHands@ERP2026" | sudo -S cp /var/www/kidobits/theme/theme_phonicsLesson.html /var/www/kidobits/theme/theme_phonicsLesson.html.bak_blend')
stdout.channel.recv_exit_status()

# Upload new file to /tmp then move with sudo
sftp = ssh.open_sftp()
sftp.put('scratch/theme_phonicsLesson_universal_blend.html', '/tmp/theme_phonicsLesson.html')
sftp.close()

cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_phonicsLesson.html /var/www/kidobits/theme/theme_phonicsLesson.html && echo "OpenHands@ERP2026" | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_phonicsLesson.html && echo "OpenHands@ERP2026" | sudo -S chmod 644 /var/www/kidobits/theme/theme_phonicsLesson.html'
stdin, stdout, stderr = ssh.exec_command(cmd)
print("Deploy output:", stdout.read().decode())
print("Deploy error:", stderr.read().decode())

stdin, stdout, stderr = ssh.exec_command('ls -la /var/www/kidobits/theme/theme_phonicsLesson.html')
print("Remote file:", stdout.read().decode())

ssh.close()
