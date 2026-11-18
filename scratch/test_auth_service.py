import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='ignore'), stderr.read().decode('utf-8', errors='ignore')

# Test auth profile PUT endpoint with python script on remote server
test_script = r"""python3 -c "
import urllib.request, json

# First check /health
req = urllib.request.Request('http://127.0.0.1:8101/health')
try:
    with urllib.request.urlopen(req) as resp:
        print('Health:', resp.read().decode())
except Exception as e:
    print('Health err:', e)
" """

out, err = run(test_script)
print("=== AUTH HEALTH ===")
print(out, err)

ssh.close()
