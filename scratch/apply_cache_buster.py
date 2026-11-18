import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

patch_script = """
with open('/var/www/kidobits/theme/theme_phonicsLesson.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace .png" with .png?v=2" for the images
content = content.replace('/kidobits/v2/images/${targetWord.toLowerCase().trim()}.png"', '/kidobits/v2/images/${targetWord.toLowerCase().trim()}.png?v=2"')
content = content.replace('/kidobits/v2/images/${cleanW}.png"', '/kidobits/v2/images/${cleanW}.png?v=2"')
content = content.replace('/kidobits/v2/images/${cleanW}.png`;', '/kidobits/v2/images/${cleanW}.png?v=2`;')

with open('/tmp/theme_phonicsLesson_v2img.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS: Added cache buster ?v=2 to image paths")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_v2img.py', 'w') as f:
    f.write(patch_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/patch_v2img.py")
print(stdout.read().decode())

# Deploy to /var/www/kidobits/theme/theme_phonicsLesson.html
stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S cp /tmp/theme_phonicsLesson_v2img.html /var/www/kidobits/theme/theme_phonicsLesson.html")
print("cp:", stdout.read().decode(), stderr.read().decode())

ssh.close()
