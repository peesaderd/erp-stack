import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = """
import os
from google import genai

# read key from /home/openhands/calm-noether/.env
api_key = None
with open('/home/openhands/calm-noether/.env') as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY='):
            api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
            break

print("API key loaded:", bool(api_key), api_key[:8] if api_key else "None")

client = genai.Client(api_key=api_key)

# Test with bird.png (which is a red car)
from PIL import Image
img = Image.open('/var/www/kidobits/v2/images/bird.png')
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[img, 'What is the primary object in this cartoon image? Reply with just 1 or 2 lowercase words, e.g. car, bird, star, dog, etc.']
)
print('Response for bird.png:', response.text.strip())
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_gemini_vision.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_gemini_vision.py')
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
