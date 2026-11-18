import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

redirect_html = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Kidobits Phonics — บทเรียน</title>
<script>
  (function(){
    var q = new URLSearchParams(window.location.search);
    var id = q.get('id') || q.get('lesson') || 'L1.01';
    window.location.replace('/kidobits/v2/lesson.html?id=' + encodeURIComponent(id));
  })();
</script>
</head>
<body style="margin:0;background:#FBF9FF;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;color:#5B4B8A;">
  <p style="font-size:16px;font-weight:bold;">กำลังเปิดบทเรียน...</p>
</body>
</html>"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/theme_phonicsLesson.html', 'w') as f:
    f.write(redirect_html)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('sudo cp /tmp/theme_phonicsLesson.html /var/www/kidobits/theme/theme_phonicsLesson.html && sudo chown www-data:www-data /var/www/kidobits/theme/theme_phonicsLesson.html')
print(stdout.read().decode())
print(stderr.read().decode())
print('SUCCESS: deployed clean redirect to theme_phonicsLesson.html')
ssh.close()
