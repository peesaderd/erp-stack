import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

test_script = """
import requests
import subprocess

# Convert an existing audio to webm / wav for test
subprocess.run(['ffmpeg', '-y', '-i', '/var/www/kidobits/v2/audio/word_sat.mp3', '-t', '5', '-f', 'wav', '/tmp/test_sat.wav'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

with open('/tmp/test_sat.wav', 'rb') as f:
    files = {'audio': ('test.wav', f, 'audio/wav')}
    data = {'hint': 'sat'}
    resp = requests.post('http://127.0.0.1:8115/stt', files=files, data=data)
    print("STT response for 'sat':", resp.status_code, resp.json())

# Convert word_at.mp3
subprocess.run(['ffmpeg', '-y', '-i', '/var/www/kidobits/v2/audio/word_at.mp3', '-t', '5', '-f', 'wav', '/tmp/test_at.wav'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
with open('/tmp/test_at.wav', 'rb') as f:
    files = {'audio': ('test.wav', f, 'audio/wav')}
    data = {'hint': 'at'}
    resp = requests.post('http://127.0.0.1:8115/stt', files=files, data=data)
    print("STT response for 'at':", resp.status_code, resp.json())
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_stt_post.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/test_stt_post.py")
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
