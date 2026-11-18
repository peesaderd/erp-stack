import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = """
import os
from google import genai
from PIL import Image

def get_key(path):
    with open(path) as f:
        for l in f:
            if 'GEMINI_API_KEY' in l:
                return l.split('=', 1)[1].strip().strip('"').strip("'")
    return None

for path in [
    '/home/openhands/erp-stack/services/ai-stream/.env',
    '/home/openhands/erp-core/erp-core/packages/ai-orchestrator/.env'
]:
    k = get_key(path)
    print(f"Testing key from {path}: {k[:8]}...")
    try:
        client = genai.Client(api_key=k)
        img = Image.open('/var/www/kidobits/v2/images/bird.png')
        res = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[img, 'What is this? One word.']
        )
        print("  SUCCESS:", res.text.strip())
    except Exception as e:
        print("  FAILED:", e)
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_aiza_keys.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_aiza_keys.py')
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
