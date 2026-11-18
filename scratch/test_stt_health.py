import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

test_script = """
import urllib.request
import urllib.parse
import json

req = urllib.request.Request("http://127.0.0.1:8115/health")
with urllib.request.urlopen(req) as resp:
    print("STT Health:", resp.read().decode())
"""
stdin, stdout, stderr = ssh.exec_command(f"python3 -c '{test_script}'")
print(stdout.read().decode())

ssh.close()
