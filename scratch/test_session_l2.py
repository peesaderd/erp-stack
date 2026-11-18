import paramiko
import json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_code = r'''
import urllib.request
import json

def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

print("=== TEST L2.01 ===")
res = post('http://127.0.0.1:8116/session/open', {'lesson': 'L2.01'})
sid = res['session']
print("L2.01 open item:", res['item'])
jump = post('http://127.0.0.1:8116/session/jump', {'session': sid, 'step': 5})
print("L2.01 step 5 item:", jump['item'])

print("\n=== TEST L2.15 ===")
res15 = post('http://127.0.0.1:8116/session/open', {'lesson': 'L2.15'})
sid15 = res15['session']
jump15 = post('http://127.0.0.1:8116/session/jump', {'session': sid15, 'step': 5})
print("L2.15 step 5 item:", jump15['item'])
print("L2.15 step 5 script:", jump15['script'])
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_session_l2.py', 'w') as f:
    f.write(remote_code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_session_l2.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR:", err)

ssh.close()
