import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')
sftp = ssh.open_sftp()

remote_script = """import urllib.request
import json

headers = {'User-Agent': 'Mozilla/5.0'}

for lid in ['L3.01', 'L3.09', 'L3.15', 'L3.16']:
    req = urllib.request.Request(f'http://127.0.0.1:8116/lesson/{lid}', headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print(f"=== /lesson/{lid} ===")
        print(f"  ok: {data.get('ok')}, id: {data.get('id')}")
        for s in data.get('steps', []):
            print(f"  Step {s['step']}: count={s['count']}, words={s['words']}")

# Test session open for L3.01
open_req = urllib.request.Request(
    'http://127.0.0.1:8116/session/open',
    data=json.dumps({"lesson": "L3.01"}).encode('utf-8'),
    headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
)
with urllib.request.urlopen(open_req) as resp:
    s_data = json.loads(resp.read().decode('utf-8'))
    print("\\n=== /session/open for L3.01 ===")
    print(f"  ok: {s_data.get('ok')}, session: {s_data.get('session')}")
    print(f"  item: {s_data.get('item')}")
    print(f"  expect: {s_data.get('expect')}")

# Test session open for L3.15
open_req2 = urllib.request.Request(
    'http://127.0.0.1:8116/session/open',
    data=json.dumps({"lesson": "L3.15"}).encode('utf-8'),
    headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
)
with urllib.request.urlopen(open_req2) as resp:
    s_data2 = json.loads(resp.read().decode('utf-8'))
    print("\\n=== /session/open for L3.15 ===")
    print(f"  ok: {s_data2.get('ok')}, session: {s_data2.get('session')}")
    print(f"  item: {s_data2.get('item')}")
"""

with sftp.file('/tmp/test_l3_api.py', 'w') as f:
    f.write(remote_script)

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/test_l3_api.py")
out = stdout.read().decode('utf-8')
print("STDOUT:\n", out)
sftp.close()
ssh.close()
