import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)

test_stt_curl = """
import urllib.request
import urllib.parse
import json

# Send a test multipart request with a wav sample
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
with open('/var/www/kidobits/audio_words/V.wav', 'rb') as f:
    audio_data = f.read()

body = (
    f'--{boundary}\\r\\n'
    f'Content-Disposition: form-data; name="lang"\\r\\n\\r\\n'
    f'zh\\r\\n'
    f'--{boundary}\\r\\n'
    f'Content-Disposition: form-data; name="hint"\\r\\n\\r\\n'
    f'你好\\r\\n'
    f'--{boundary}\\r\\n'
    f'Content-Disposition: form-data; name="audio"; filename="sample.wav"\\r\\n'
    f'Content-Type: audio/wav\\r\\n\\r\\n'
).encode('utf-8') + audio_data + f'\\r\\n--{boundary}--\\r\\n'.encode('utf-8')

req = urllib.request.Request(
    'http://127.0.0.1:8115/stt',
    data=body,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)
with urllib.request.urlopen(req) as resp:
    res = resp.read().decode('utf-8')
    print('STT zh Response:', res)
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_stt_zh.py', 'w') as f:
    f.write(test_stt_curl)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_stt_zh.py')
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
