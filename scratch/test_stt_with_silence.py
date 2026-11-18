import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

test_script = """
import requests
import subprocess

# Generate 5 seconds of silence
subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=16000:cl=mono', '-t', '5.2', '/tmp/silence.wav'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
# Concat word_at.mp3 + silence.wav
subprocess.run(['ffmpeg', '-y', '-i', '/var/www/kidobits/v2/audio/word_at.mp3', '-i', '/tmp/silence.wav', '-filter_complex', '[0:a][1:a]concat=n=2:v=0:a=1[out]', '-map', '[out]', '/tmp/at_with_silence.wav'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

with open('/tmp/at_with_silence.wav', 'rb') as f:
    files = {'audio': ('child.wav', f, 'audio/wav')}
    data = {'hint': 'at'}
    resp = requests.post('http://127.0.0.1:8115/stt', files=files, data=data)
    print("STT with silence response:", resp.status_code, resp.json())
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_stt_silence.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/test_stt_silence.py")
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
