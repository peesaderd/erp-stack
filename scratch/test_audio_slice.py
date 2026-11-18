import paramiko
import json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

slice_script = """
import json
import subprocess

timeline = json.loads('''{
  "a": {"start": 1.30, "end": 1.60},
  "b": {"start": 1.30, "end": 1.63},
  "p": {"start": 1.30, "end": 1.65},
  "s": {"start": 1.38, "end": 1.77},
  "i": {"start": 1.34, "end": 1.58}
}''')

for letter, bounds in timeline.items():
    start = bounds['start']
    dur = bounds['end'] - bounds['start'] + 0.05
    cmd = f"ffmpeg -y -ss {start} -t {dur} -i /tmp/littlewood/assets/audio/{letter}.mp3 -acodec copy /tmp/slice_{letter}.mp3"
    subprocess.run(cmd, shell=True, check=True)
    print(f"Sliced {letter}")
"""

sftp = ssh.open_sftp()
with sftp.open('/tmp/run_slice_test.py', 'w') as f:
    f.write(slice_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/run_slice_test.py')
print(stdout.read().decode())
print(stderr.read().decode())

# Download slices
sftp = ssh.open_sftp()
for letter in ['a', 'b', 'p', 's', 'i']:
    sftp.get(f'/tmp/slice_{letter}.mp3', f'C:/Users/ADMIN/.gemini/antigravity/brain/5aaad136-0e16-491c-b1ad-9b64499b48ac/slice_{letter}.mp3')
    print(f"Downloaded slice_{letter}.mp3")
sftp.close()

ssh.close()
