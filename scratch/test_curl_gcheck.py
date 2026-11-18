import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

cmds = [
    "curl -s -I https://kidobits.m2igen.com/kidobits/v2/gcheck/L1/at.png",
    "curl -s -I https://kidobits.m2igen.com/kidobits/v2/gcheck/L1/sat.png",
    "curl -s -I https://kidobits.m2igen.com/kidobits/v2/gcheck/L1/mat.png",
    "curl -s -I https://kidobits.m2igen.com/kidobits/v2/gcheck/L2/bin.png"
]

for cmd in cmds:
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())

ssh.close()
