import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = """
from google import genai
from PIL import Image

with open('/home/openhands/calm-noether/.env') as f:
    for l in f:
        if l.startswith('GEMINI_API_KEY='):
            api_key = l.split('=', 1)[1].strip().strip('"').strip("'")
            break

client = genai.Client(api_key=api_key)

img1 = Image.open('/var/www/kidobits/v2/images/bird.png')
img2 = Image.open('/var/www/kidobits/v2/images/car.png')
img3 = Image.open('/var/www/kidobits/v2/images/star.png')

prompt = '''Identify the object shown in each of the following images. Choose from candidate words:
car, star, girl, farm, park, fork, bird.
Format as JSON: {"img1": "...", "img2": "...", "img3": "..."}
'''

contents = ["Image 1:", img1, "Image 2:", img2, "Image 3:", img3, prompt]

res = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=contents
)
print("Result:")
print(res.text.strip())
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_multi_image.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_multi_image.py')
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
