import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

stdin, stdout, stderr = ssh.exec_command('echo "OpenHands@ERP2026" | sudo -S mkdir -p /var/www/kidobits/v2/audio/phonics_bank && echo "OpenHands@ERP2026" | sudo -S chown -R openhands:openhands /var/www/kidobits/v2/audio/phonics_bank')
print("Init dir:", stdout.read().decode())

# Upload build script
sftp = ssh.open_sftp()
sftp.put('C:/Users/ADMIN/Documents/antigravity/calm-noether/scratch/build_full_phonics_bank.py', '/tmp/build_full_phonics_bank.py')
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/build_full_phonics_bank.py')
print("Build output:\n", stdout.read().decode())
print("Build error:\n", stderr.read().decode())

# Set permissions for nginx www-data to read
stdin, stdout, stderr = ssh.exec_command('echo "OpenHands@ERP2026" | sudo -S chown -R www-data:www-data /var/www/kidobits/v2/audio/phonics_bank && echo "OpenHands@ERP2026" | sudo -S chmod -R 755 /var/www/kidobits/v2/audio/phonics_bank')
stdout.read()

ssh.close()
