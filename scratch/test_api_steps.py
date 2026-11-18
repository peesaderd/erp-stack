import paramiko
import json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

cmd = '''python3 -c "
import urllib.request, json

def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read())

open_res = post('http://127.0.0.1:8116/session/open', {'lesson': 'L1.01'})
sid = open_res['session']
print('OPEN ITEM:', open_res['item'])
print('OPEN SCRIPT:', open_res['script'])

# Step 1 advance through all items
cur = open_res
for i in range(5):
    word = cur['item']['word']
    ans = post('http://127.0.0.1:8116/session/answer', {'session': sid, 'input': word})
    cur = post('http://127.0.0.1:8116/session/advance', {'session': sid})
    print(f'Advanced {i+1}: step={cur[\"item\"][\"step\"]} word={cur[\"item\"][\"word\"]} total={cur[\"item\"][\"total\"]}')
"'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR:", err)

ssh.close()
