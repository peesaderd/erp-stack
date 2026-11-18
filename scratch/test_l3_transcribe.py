import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_code = r'''
import subprocess

for fname in ['sent_L3.01_0.mp3', 'sent_L3.01_1.mp3']:
    p = f'/var/www/kidobits/audio/l3/{fname}'
    res = subprocess.run([
        'curl', '-s', '-H', 'Content-Type: audio/mpeg', '--data-binary', f'@{p}', 'http://127.0.0.1:8115/stt'
    ], capture_output=True, text=True)
    print(f"{fname}: {res.stdout.strip()}")
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/transcribe_l3.py', 'w') as f:
    f.write(remote_code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/transcribe_l3.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR:", err)

ssh.close()
