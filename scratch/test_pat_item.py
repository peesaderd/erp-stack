import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

test_script = """
import urllib.request
import json

def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        return resp.getcode(), json.loads(resp.read().decode())

code, res = post('http://127.0.0.1:8116/session/open', {'lesson': 'L1.01'})
sid = res['session']
code, jmp = post('http://127.0.0.1:8116/session/jump', {'session': sid, 'step': 4, 'index': 3})
print("Step 4 index 3 item:", jmp['item'])
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_pat_item.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/test_pat_item.py")
print(stdout.read().decode())

ssh.close()
