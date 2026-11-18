import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8') + stderr.read().decode('utf-8')

print(run("curl -s http://127.0.0.1:8114/pos/menu | python3 -c 'import sys, json; data=json.load(sys.stdin); print(f\"Total items: {len(data)}\"); print(\"First item:\", json.dumps(data[0], indent=2))'"))
