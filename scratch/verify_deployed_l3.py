import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = """import urllib.request

headers = {'User-Agent': 'Mozilla/5.0'}

req = urllib.request.Request('http://127.0.0.1/kidobits/theme/theme_phonicsLevel.html?lv=3', headers=headers)
with urllib.request.urlopen(req) as resp:
    html = resp.read().decode('utf-8')
    print("theme_phonicsLevel.html?lv=3 length:", len(html))
    print("Has LV3_LESSONS:", 'LV3_LESSONS' in html)
    print("Has Digraphs & Consonant Blends:", 'Digraphs & Consonant Blends' in html)

req2 = urllib.request.Request('http://127.0.0.1/kidobits/theme/theme_phonicsLesson.html?lesson=L3.01', headers=headers)
with urllib.request.urlopen(req2) as resp:
    html2 = resp.read().decode('utf-8')
    print("theme_phonicsLesson.html?lesson=L3.01 length:", len(html2))
    print("Has L3.01 meta:", '"L3.01":' in html2)
    print("Has L3.16 meta:", '"L3.16":' in html2)
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/verify_deployed_l3.py', 'w') as f:
    f.write(remote_script)

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/verify_deployed_l3.py")
out = stdout.read().decode('utf-8')
print("STDOUT:\n", out)
sftp.close()
ssh.close()
