import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

test_gen_script = """
import asyncio
import edge_tts

# We test teacher Emma voice (en-US-EmmaNeural or en-US-JennyNeural)
VOICE = "en-US-EmmaNeural"

samples = {
    "sh": "shh",
    "ch": "chuh",
    "th": "thuh",
    "ck": "kuh",
    "ng": "ng",
    "wh": "wuh",
    "qu": "kwuh",
    "ee": "ee",
    "ai": "ay",
    "oa": "oh",
    "oo": "oo",
    "oi": "oy",
    "ou": "ow",
    "ar": "ar",
    "or": "or",
    "er": "er"
}

async def main():
    for name, text in samples.items():
        out_path = f"/tmp/test_digraph_{name}.mp3"
        comm = edge_tts.Communicate(text, VOICE)
        await comm.save(out_path)
        print(f"Generated {name} -> {text}")

asyncio.run(main())
"""

sftp = ssh.open_sftp()
with sftp.open('/tmp/test_digraph_gen.py', 'w') as f:
    f.write(test_gen_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/test_digraph_gen.py')
print(stdout.read().decode())
print(stderr.read().decode())

# Download samples to listen
sftp = ssh.open_sftp()
for name in ["sh", "ch", "th", "ck", "ng", "ee", "ai", "oa", "oo", "ar"]:
    sftp.get(f'/tmp/test_digraph_{name}.mp3', f'C:/Users/ADMIN/.gemini/antigravity/brain/5aaad136-0e16-491c-b1ad-9b64499b48ac/test_dg_{name}.mp3')
    print(f"Downloaded test_dg_{name}.mp3")
sftp.close()

ssh.close()
