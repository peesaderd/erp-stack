import paramiko
import json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

# Start session via /session/open
stdin, stdout, stderr = ssh.exec_command('curl -s -X POST -H "Content-Type: application/json" -d \'{"lesson":"L1.01"}\' http://127.0.0.1:8116/session/open')
start_res = json.loads(stdout.read().decode())
print("OPEN RESPONSE:")
print("session:", start_res.get('session'))
print("steps:", start_res.get('steps'))
print("item:", start_res.get('item'))

session_id = start_res.get('session')

# Advance to step 3
# Step 1 has 5 items (at, sat, mat, pat, tap)
# Step 2 has 5 items (at, sat, mat, pat, tap)
# Step 3 is listen_choose (at, sat, mat, pat, tap)
curr_item = start_res.get('item')
while curr_item and curr_item.get('step') != 3:
    step = curr_item.get('step')
    idx = curr_item.get('index')
    w = curr_item.get('word')
    
    # submit answer
    cmd = f'curl -s -X POST -H "Content-Type: application/json" -d \'{{"session":"{session_id}","input":"{w}"}}\' http://127.0.0.1:8116/session/answer'
    stdin, stdout, stderr = ssh.exec_command(cmd)
    ans_res = json.loads(stdout.read().decode())
    
    # advance
    cmd = f'curl -s -X POST -H "Content-Type: application/json" -d \'{{"session":"{session_id}"}}\' http://127.0.0.1:8116/session/advance'
    stdin, stdout, stderr = ssh.exec_command(cmd)
    adv_res = json.loads(stdout.read().decode())
    curr_item = adv_res.get('item')
    print(f"Step {step}[{idx}] '{w}' answered={ans_res.get('correct')} -> Next step: {curr_item.get('step') if curr_item else 'done'}[{curr_item.get('index') if curr_item else 'done'}] word={curr_item.get('word') if curr_item else ''}")

print("\n--- STEP 3 ITEM PAYLOAD ---")
print(json.dumps(curr_item, indent=2, ensure_ascii=False))

ssh.close()
