import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = r'''
with open("/var/www/kidobits/theme/theme_azPlayer.html", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# Backup
with open("/tmp/theme_azPlayer.html.bak", "w", encoding="utf-8") as f:
    f.write(text)

# Replace onClick:()=>h("home") with onClick:()=>window.location.href="theme_home.html"
target = 'onClick:()=>h("home"),className:"bg-white border px-3 py-2 rounded-full text-xs font-extrabold",children:"← บทเรียน"'
replacement = 'onClick:()=>window.location.href="theme_home.html",className:"bg-white border px-3 py-2 rounded-full text-xs font-extrabold",children:"← บทเรียน"'

if target in text:
    text = text.replace(target, replacement, 1)
    print("SUCCESS: Back button changed to go to theme_home.html")
else:
    print("ERROR: Target not found")

with open("/tmp/theme_azPlayer_fixed.html", "w", encoding="utf-8") as f:
    f.write(text)
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/fix_back_btn.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/fix_back_btn.py')
print(stdout.read().decode())
print("ERR:", stderr.read().decode())

cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_azPlayer_fixed.html /var/www/kidobits/theme/theme_azPlayer.html && echo "DEPLOY_HTML_OK"'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

ssh.close()
