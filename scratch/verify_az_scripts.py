import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = r'''
with open("/var/www/kidobits/theme/theme_azPlayer.html", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

import re
# Check all occurrences of VoiceManager in theme_azPlayer.html
print("Occurrences of VoiceManager in theme_azPlayer.html:", len(re.findall(r'VoiceManager', text)))

# Check all occurrences of kb-lesson in theme_azPlayer.html
print("Occurrences of kb-lesson in theme_azPlayer.html:", len(re.findall(r'kb-lesson', text)))
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/verify_az_scripts.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/verify_az_scripts.py')
print(stdout.read().decode())
print("ERR:", stderr.read().decode())

ssh.close()
