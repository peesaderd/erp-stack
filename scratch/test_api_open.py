import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

stdin, stdout, stderr = ssh.exec_command('curl -s -X POST http://127.0.0.1:8116/session/open -H "Content-Type: application/json" -d "{\\"lesson\\":\\"L1.01\\"}"')
print("=== /session/open response:")
print(stdout.read().decode('utf-8'))

ssh.close()
