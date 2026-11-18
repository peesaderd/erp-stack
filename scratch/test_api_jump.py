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

# 1. Open session
code, res = post('http://127.0.0.1:8116/session/open', {'lesson': 'L1.01'})
sid = res['session']
print('Session opened:', sid, 'initial step:', res['item']['step'])

# 2. Test advance without force when not answered -> expect 409
try:
    code, adv = post('http://127.0.0.1:8116/session/advance', {'session': sid, 'force': False})
    print('Unexpected success without force:', adv)
except urllib.error.HTTPError as e:
    print('Expected 409 when not answered and force=False:', e.code)

# 3. Test advance with force=True -> expect 200
code, adv = post('http://127.0.0.1:8116/session/advance', {'session': sid, 'force': True})
print('Advance with force=True success:', adv['ok'], 'new item:', adv['item']['word'] if adv['item'] else 'done')

# 4. Test jump to Step 4
code, jmp = post('http://127.0.0.1:8116/session/jump', {'session': sid, 'step': 4})
print('Jump to Step 4 success:', jmp['ok'], 'step:', jmp['item']['step'], 'word:', jmp['item']['word'])

# 5. Test jump to Step 5
code, jmp5 = post('http://127.0.0.1:8116/session/jump', {'session': sid, 'step': 5})
print('Jump to Step 5 success:', jmp5['ok'], 'step:', jmp5['item']['step'], 'sentence:', jmp5['item'].get('sentence'))

# 6. Test jump back to Step 1
code, jmp1 = post('http://127.0.0.1:8116/session/jump', {'session': sid, 'step': 1})
print('Jump back to Step 1 success:', jmp1['ok'], 'step:', jmp1['item']['step'], 'word:', jmp1['item']['word'])
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_api_endpoints.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/test_api_endpoints.py")
print("test output:\n", stdout.read().decode())
print("test error:\n", stderr.read().decode())

ssh.close()
