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

def get(url):
    with urllib.request.urlopen(url) as res:
        return json.loads(res.read())

print('1. GET /lesson/L1.01:')
print(json.dumps(get('http://127.0.0.1:8116/lesson/L1.01'), indent=2, ensure_ascii=False))

print('\\n2. POST /session/open:')
open_res = post('http://127.0.0.1:8116/session/open', {'lesson': 'L1.01'})
print(json.dumps(open_res, indent=2, ensure_ascii=False))

sid = open_res['session']

print('\\n3. POST /session/answer (correct: at):')
ans_res = post('http://127.0.0.1:8116/session/answer', {'session': sid, 'input': 'at'})
print(json.dumps(ans_res, indent=2, ensure_ascii=False))

print('\\n4. POST /session/advance:')
adv_res = post('http://127.0.0.1:8116/session/advance', {'session': sid})
print(json.dumps(adv_res, indent=2, ensure_ascii=False))
"'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)

ssh.close()
