import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

cmd = 'curl -s -X POST -H "Content-Type: application/json" -d \'{"session":"35180cef23224f16","input":"at"}\' http://127.0.0.1:8116/session/answer'
stdin, stdout, stderr = ssh.exec_command(cmd)
print('answer at:', stdout.read().decode())

cmd = 'curl -s -X POST -H "Content-Type: application/json" -d \'{"session":"35180cef23224f16","input":"[object Object]"}\' http://127.0.0.1:8116/session/answer'
stdin, stdout, stderr = ssh.exec_command(cmd)
print('answer [object Object]:', stdout.read().decode())

ssh.close()
