import paramiko
import json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

stdin, stdout, stderr = ssh.exec_command('curl -s -X POST -H "Content-Type: application/json" -d \'{"lesson":"L1.01"}\' http://127.0.0.1:8116/session/open')
res = json.loads(stdout.read().decode())
sid = res.get('session')
print("Session open:", sid)

# Advance to step 3
for _ in range(10): # 5 blend + 5 seg
    # get current item
    stdin, stdout, stderr = ssh.exec_command(f'curl -s http://127.0.0.1:8116/session/{sid}/item')
    item_res = json.loads(stdout.read().decode())
    w = item_res['item']['word']
    # answer
    ssh.exec_command(f'curl -s -X POST -H "Content-Type: application/json" -d \'{{"session":"{sid}","input":"{w}"}}\' http://127.0.0.1:8116/session/answer')
    # advance
    stdin, stdout, stderr = ssh.exec_command(f'curl -s -X POST -H "Content-Type: application/json" -d \'{{"session":"{sid}"}}\' http://127.0.0.1:8116/session/advance')

# Now fetch step 3 item
stdin, stdout, stderr = ssh.exec_command(f'curl -s http://127.0.0.1:8116/session/{sid}/item')
step3_item = json.loads(stdout.read().decode())
print("Step 3 item payload from API:")
print(json.dumps(step3_item['item'], indent=2, ensure_ascii=False))

ssh.close()
