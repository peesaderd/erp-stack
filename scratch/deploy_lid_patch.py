import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_py = """
with open('/var/www/kidobits/v2/lesson.html', 'r', encoding='utf-8') as f:
    txt = f.read()

target = "const LID = Q.get('id') || 'L1.01';"
replacement = "const LID = Q.get('id') || Q.get('lesson') || 'L1.01';"

if target in txt:
    txt = txt.replace(target, replacement, 1)
    with open('/tmp/lesson_v2.html', 'w', encoding='utf-8') as f:
        f.write(txt)
    print('SUCCESS: updated LID logic in /tmp/lesson_v2.html')
else:
    print('TARGET NOT FOUND')
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_v2_lid.py', 'w') as f:
    f.write(remote_py)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/patch_v2_lid.py && sudo cp /tmp/lesson_v2.html /var/www/kidobits/v2/lesson.html && sudo chown www-data:www-data /var/www/kidobits/v2/lesson.html')
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
