import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

test_transcribe = """
import urllib.request
import json
import os

files = [
    '/var/www/kidobits/v2/audio/teach_blend_how.mp3',
    '/var/www/kidobits/audio/l2/prompt_blend.mp3',
    '/var/www/kidobits/v2/audio/teach_intro_l201.mp3',
    '/var/www/kidobits/v2/audio/teach_segment_how.mp3'
]

# Or check size and read metadata or use whisper
import subprocess
for f in files:
    if os.path.exists(f):
        cmd = f'curl -s -X POST http://127.0.0.1:8115/stt -F "audio=@{f}"'
        res = subprocess.getoutput(cmd)
        print(f"{os.path.basename(f)}: {res}")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/transcribe_prompts.py', 'w') as f:
    f.write(test_transcribe)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/transcribe_prompts.py")
print(stdout.read().decode('utf-8'))
ssh.close()
