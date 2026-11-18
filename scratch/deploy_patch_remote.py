import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=10)

sftp = ssh.open_sftp()
with open(r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\patch_profile_local.py', 'rb') as f:
    data = f.read()
with sftp.open('/tmp/run_patch.py', 'wb') as f:
    f.write(data)
sftp.close()

cmd = """
python3 /tmp/run_patch.py
echo 'OpenHands@ERP2026' | sudo -S cp /tmp/fixed_theme_profile.html /var/www/kidobits/theme/theme_profile.html
echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_profile.html
cd /var/www/kidobits
git status
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
