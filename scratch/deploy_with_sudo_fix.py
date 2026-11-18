import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=10)

cmd = """
echo 'OpenHands@ERP2026' | sudo -S python3 /tmp/run_profile_link_fix.py
echo 'OpenHands@ERP2026' | sudo -S chown -R openhands:openhands /var/www/kidobits/theme/
cd /var/www/kidobits
git status --short
git diff --stat
git add -A
git commit -m "fix(nav): replace all theme_home.html#profile with theme_profile.html in theme directory"
git push origin main
echo 'OpenHands@ERP2026' | sudo -S chown -R www-data:www-data /var/www/kidobits/theme/
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
