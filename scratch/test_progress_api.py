import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

test_curl_script = """#!/bin/bash
echo "=== 1. Check local health ==="
curl -s http://127.0.0.1:8116/health
echo ""

echo "=== 2. Test POST /progress/save (Step 2 of L3.01) ==="
curl -s -X POST http://127.0.0.1:8116/progress/save \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_child", "lesson_id": "L3.01", "level": 3, "step": 2, "item_index": 0, "done": false}'
echo ""

echo "=== 3. Test GET /progress/latest?user_id=test_child ==="
curl -s "http://127.0.0.1:8116/progress/latest?user_id=test_child"
echo ""

echo "=== 4. Test GET /progress/get?user_id=test_child&lesson_id=L3.01 ==="
curl -s "http://127.0.0.1:8116/progress/get?user_id=test_child&lesson_id=L3.01"
echo ""

echo "=== 5. Test Public HTTPS Proxy via kidobits.m2igen.com ==="
curl -s -k "https://kidobits.m2igen.com/kidobits/api/progress/latest?user_id=test_child"
echo ""

echo "=== 6. Test Public HTTPS POST /kidobits/api/progress/save ==="
curl -s -k -X POST "https://kidobits.m2igen.com/kidobits/api/progress/save" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_child", "lesson_id": "L3.02", "level": 3, "step": 3, "item_index": 2, "done": false}'
echo ""

echo "=== 7. Test Public HTTPS GET latest again ==="
curl -s -k "https://kidobits.m2igen.com/kidobits/api/progress/latest?user_id=test_child"
echo ""
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_progress.sh', 'w') as f:
    f.write(test_curl_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("bash /tmp/test_progress.sh")
print(stdout.read().decode())
print("Errors:\n", stderr.read().decode())

ssh.close()
