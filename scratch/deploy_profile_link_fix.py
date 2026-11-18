import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=10)

sftp = ssh.open_sftp()
with open(r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\fix_home_profile_remote.py', 'rb') as f:
    data = f.read()
with sftp.open('/tmp/run_profile_link_fix.py', 'wb') as f:
    f.write(data)
sftp.close()

cmd = """
python3 /tmp/run_profile_link_fix.py
cd /var/www/kidobits
git status --short
git diff --stat
git add -A
git commit -m "fix(nav): replace all theme_home.html#profile with theme_profile.html and auto-redirect hash"
git push origin main
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
