import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

sftp = ssh.open_sftp()
sftp.put('scratch/theme_phonicsLesson_v2.html', '/tmp/theme_phonicsLesson.html')
sftp.close()

stdin, stdout, stderr = ssh.exec_command('sudo cp /tmp/theme_phonicsLesson.html /var/www/kidobits/theme/theme_phonicsLesson.html && sudo chmod 644 /var/www/kidobits/theme/theme_phonicsLesson.html')
stdout.channel.recv_exit_status()

stdin, stdout, stderr = ssh.exec_command('ls -la /var/www/kidobits/theme/theme_phonicsLesson.html')
print(stdout.read().decode())

ssh.close()
print("Successfully deployed theme_phonicsLesson.html!")
