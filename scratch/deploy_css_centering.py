import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=10)

sftp = ssh.open_sftp()
with open(r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\fix_css_centering.py', 'rb') as f:
    data = f.read()
with sftp.open('/tmp/run_css_fix.py', 'wb') as f:
    f.write(data)
sftp.close()

cmd = """
python3 /tmp/run_css_fix.py
echo 'OpenHands@ERP2026' | sudo -S cp /tmp/fixed_theme_profile_css.html /var/www/kidobits/theme/theme_profile.html
echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_profile.html
cd /var/www/kidobits
git diff --stat
git add theme/theme_profile.html
git commit -m "fix(profile): use top alignment to prevent vertical clipping on desktop/tablet"
git push origin main
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
