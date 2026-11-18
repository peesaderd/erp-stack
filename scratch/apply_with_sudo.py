import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=10)

cmd = """
echo 'OpenHands@ERP2026' | sudo -S cp /tmp/kidobits_dynamic_island.js /var/www/kidobits/theme/js/kidobits_dynamic_island.js
echo 'OpenHands@ERP2026' | sudo -S cp /tmp/theme_profile.html /var/www/kidobits/theme/theme_profile.html
echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/theme/js/kidobits_dynamic_island.js /var/www/kidobits/theme/theme_profile.html
cd /var/www/kidobits
git status
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'), flush=True)
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'), flush=True)

ssh.close()
