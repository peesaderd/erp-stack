import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

stdin, stdout, stderr = ssh.exec_command("curl -s -I https://kidobits.m2igen.com/kidobits/v2/images/at.png")
print("at.png curl:\n", stdout.read().decode())
stdin, stdout, stderr = ssh.exec_command("curl -s -I https://kidobits.m2igen.com/kidobits/v2/images/sat.png")
print("sat.png curl:\n", stdout.read().decode())
stdin, stdout, stderr = ssh.exec_command("curl -s -I https://kidobits.m2igen.com/kidobits/v2/images/mat.png")
print("mat.png curl:\n", stdout.read().decode())

ssh.close()
