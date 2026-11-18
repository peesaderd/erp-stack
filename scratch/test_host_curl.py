import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

stdin, stdout, stderr = ssh.exec_command('curl -s -i -X POST http://127.0.0.1/kidobits/api/session/open -H "Host: kidobits.m2igen.com" -H "Content-Type: application/json" -d "{\\"lesson\\":\\"L2.01\\"}"')
print("With Host header:")
print(stdout.read().decode())
ssh.close()
