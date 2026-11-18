import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

sftp = ssh.open_sftp()
sftp.put('scratch/theme_phonicsLevel.html', '/tmp/theme_phonicsLevel.html')
sftp.put('scratch/theme_phonicsLesson.html', '/tmp/theme_phonicsLesson.html')
sftp.close()

cmd = """
sudo cp /tmp/theme_phonicsLevel.html /var/www/kidobits/theme/theme_phonicsLevel.html
sudo cp /tmp/theme_phonicsLesson.html /var/www/kidobits/theme/theme_phonicsLesson.html
sudo chown www-data:www-data /var/www/kidobits/theme/theme_phonicsLevel.html /var/www/kidobits/theme/theme_phonicsLesson.html
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print('DEPLOY OUT:', stdout.read().decode())
print('DEPLOY ERR:', stderr.read().decode())
print('SUCCESS: deployed both pure HTML files to remote cloud server!')
ssh.close()
