import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

test_suite = """#!/bin/bash
set -e

echo "=== 1. Test POST /progress/save with in-progress lesson (Step 3/5) ==="
curl -s -X POST http://127.0.0.1:8116/progress/save \\
  -H "Content-Type: application/json" \\
  -d '{"user_id": "guest", "lesson_id": "L3.01", "level": 3, "step": 3, "item_index": 1, "done": false}'
echo ""

echo "=== 2. Test GET /progress/latest?user_id=guest ==="
curl -s "http://127.0.0.1:8116/progress/latest?user_id=guest"
echo ""

echo "=== 3. Test POST /progress/save with completed lesson (Done = true) ==="
curl -s -X POST http://127.0.0.1:8116/progress/save \\
  -H "Content-Type: application/json" \\
  -d '{"user_id": "guest", "lesson_id": "L3.01", "level": 3, "step": 5, "item_index": 0, "done": true}'
echo ""

echo "=== 4. Test GET /progress/latest after completion (should show next_lesson_id: L3.02) ==="
curl -s "http://127.0.0.1:8116/progress/latest?user_id=guest"
echo ""

echo "=== 5. Test Public HTTPS via kidobits.m2igen.com ==="
curl -s -k "https://kidobits.m2igen.com/kidobits/api/progress/latest?user_id=guest"
echo ""

echo "=== 6. Reset to realistic in-progress lesson L3.01 step 2 ==="
curl -s -X POST http://127.0.0.1:8116/progress/save \\
  -H "Content-Type: application/json" \\
  -d '{"user_id": "guest", "lesson_id": "L3.01", "level": 3, "step": 2, "item_index": 0, "done": false}'
echo ""
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_full_progress_suite.sh', 'w') as f:
    f.write(test_suite)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("bash /tmp/test_full_progress_suite.sh")
print(stdout.read().decode())
print("Errors:\n", stderr.read().decode())

ssh.close()
