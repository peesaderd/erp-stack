import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

test_compare_script = """
import os, subprocess, asyncio, edge_tts

# Test 1: Sliced Littlewood with gentle fadeout and slight tail
cmd1 = 'ffmpeg -y -ss 1.30 -t 0.35 -i /tmp/littlewood/assets/audio/a.mp3 -af "afade=t=out:st=0.25:d=0.10" /tmp/test_fade_a.mp3'
cmd2 = 'ffmpeg -y -ss 1.32 -t 0.32 -i /tmp/littlewood/assets/audio/i.mp3 -af "afade=t=out:st=0.22:d=0.10" /tmp/test_fade_i.mp3'
cmd3 = 'ffmpeg -y -ss 1.30 -t 0.40 -i /tmp/littlewood/assets/audio/p.mp3 -af "afade=t=out:st=0.28:d=0.12" /tmp/test_fade_p.mp3'
subprocess.run(cmd1, shell=True)
subprocess.run(cmd2, shell=True)
subprocess.run(cmd3, shell=True)

# Test 2: Edge-TTS JennyNeural (very friendly teacher) vs EmmaNeural with longer vowels
async def gen_tts():
    # Test longer articulation
    await edge_tts.Communicate("ah", "en-US-JennyNeural").save("/tmp/test_jenny_a.mp3")
    await edge_tts.Communicate("ih", "en-US-JennyNeural").save("/tmp/test_jenny_i.mp3")
    await edge_tts.Communicate("puh", "en-US-JennyNeural").save("/tmp/test_jenny_p.mp3")
    await edge_tts.Communicate("tuh", "en-US-JennyNeural").save("/tmp/test_jenny_t.mp3")
    await edge_tts.Communicate("sss", "en-US-JennyNeural").save("/tmp/test_jenny_s.mp3")

asyncio.run(gen_tts())
print("Comparison audio generated.")
"""

sftp = ssh.open_sftp()
with sftp.open('/tmp/run_compare.py', 'w') as f:
    f.write(test_compare_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/run_compare.py')
print(stdout.read().decode())
print(stderr.read().decode())

# Download to listen
sftp = ssh.open_sftp()
for f in ['test_fade_a.mp3', 'test_fade_i.mp3', 'test_fade_p.mp3', 'test_jenny_a.mp3', 'test_jenny_i.mp3', 'test_jenny_p.mp3', 'test_jenny_t.mp3', 'test_jenny_s.mp3']:
    sftp.get(f'/tmp/{f}', f'C:/Users/ADMIN/.gemini/antigravity/brain/5aaad136-0e16-491c-b1ad-9b64499b48ac/{f}')
    print(f"Downloaded {f}")
sftp.close()

ssh.close()
