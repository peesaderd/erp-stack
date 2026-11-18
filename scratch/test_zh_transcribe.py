import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)

script = """
import sys
sys.path.insert(0, '/home/openhands/emma-stt')
from stt_server import get_model
import glob

model = get_model()
sample_file = glob.glob('/var/www/kidobits/audio_words/*.wav')[0]
print('Testing on sample:', sample_file)

segs, info = model.transcribe(sample_file, language='zh', without_timestamps=True)
text = ' '.join(s.text.strip() for s in segs)
print('Transcribed with language=zh:', text, 'Info language:', info.language)
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_zh_transcribe.py', 'w') as f:
    f.write(script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_zh_transcribe.py')
print(stdout.read().decode())
ssh.close()
