import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')
stdin, stdout, stderr = ssh.exec_command("python3 -c 'import fastapi, uvicorn, sqlite3; print(\"OK\")'")
print("Remote python check:", stdout.read().decode())
ssh.close()
