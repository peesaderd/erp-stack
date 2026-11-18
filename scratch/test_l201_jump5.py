import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

stdin, stdout, stderr = ssh.exec_command('''curl -s -X POST http://127.0.0.1:8116/session/jump -H "Content-Type: application/json" -d '{"session": "f20895e23dc54949", "step": 5}' ''')
print(stdout.read().decode())
ssh.close()
