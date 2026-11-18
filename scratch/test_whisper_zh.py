import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)

script = """
import sys
sys.path.insert(0, '/home/openhands/emma-stt')
from stt_server import get_model

model = get_model()
print('Whisper model:', model)

# Check if model can transcribe with language='zh'
# Let's synthesize or test with a dummy wav or an existing audio file on the server
import os, glob
audios = glob.glob('/var/www/kidobits/audio_words/*.wav') + glob.glob('/var/www/kidobits/audio_words/*.mp3')
print('Sample audios available:', len(audios))
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_whisper_zh.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_whisper_zh.py')
print(stdout.read().decode())
ssh.close()
