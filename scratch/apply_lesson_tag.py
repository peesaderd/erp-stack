import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_py = '''
with open('/var/www/kidobits/theme/theme_phonicsLesson.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Remove any existing script tags for kb-lesson
import re
text = re.sub(r'<script src="/kidobits/js/kb-lesson.*?></script>', '', text)

# Insert script in head
needle = '<title>'
pos = text.find(needle)
if pos != -1:
    tag = '<script src="/kidobits/js/kb-lesson.v2.js?v=20261111_v999"></script>\\n'
    text = text[:pos] + tag + text[pos:]

with open('/tmp/theme_phonicsLesson.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated /tmp/theme_phonicsLesson.html, length:", len(text))
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_lesson_html.py', 'w') as f:
    f.write(remote_py)
sftp.close()

cmd = 'python3 /tmp/patch_lesson_html.py && echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_phonicsLesson.html /var/www/kidobits/theme/theme_phonicsLesson.html && echo "OpenHands@ERP2026" | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_phonicsLesson.html'
stdin, stdout, stderr = ssh.exec_command(cmd)
print("Result:", stdout.read().decode())
print("STDERR:", stderr.read().decode())
ssh.close()
