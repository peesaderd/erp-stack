import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)

test_script = """
import urllib.request
import json

req = urllib.request.Request('http://127.0.0.1:8115/health')
with urllib.request.urlopen(req) as resp:
    print('Health response:', resp.read().decode())
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_health.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_health.py')
print(stdout.read().decode())
ssh.close()
