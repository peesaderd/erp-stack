import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')
sftp = ssh.open_sftp()

remote_script = """import os
from faster_whisper import WhisperModel

model = WhisperModel("small", device="cpu", compute_type="int8")

check_files = [
    '/var/www/kidobits/audio/l2/g_sh.mp3',
    '/var/www/kidobits/audio/l2/g_ch.mp3',
    '/var/www/kidobits/audio/l2/g_th.mp3',
    '/var/www/kidobits/audio/l2/g_p.mp3',
    '/var/www/kidobits/audio/l2/g_i.mp3',
    '/var/www/kidobits/audio/l2/g_s.mp3',
    '/var/www/kidobits/audio/l2/g_fr.mp3',
    '/var/www/kidobits/audio/l2/g_st.mp3',
    '/var/www/kidobits/v2/audio/sp_s.mp3',
    '/var/www/kidobits/v2/audio/sp_p.mp3',
    '/var/www/kidobits/audio/S.mp3',
    '/var/www/kidobits/audio/P.mp3'
]

for f in check_files:
    if os.path.exists(f):
        sz = os.path.getsize(f)
        try:
            segments, info = model.transcribe(f, beam_size=5, language="en")
            txt = " ".join([s.text for s in segments]).strip()
        except Exception as e:
            txt = f"Err: {e}"
        print(f"{f} ({sz} bytes, dur={info.duration:.2f}s) -> text='{txt}'")
    else:
        print(f"NOT FOUND: {f}")
"""

with sftp.file('/tmp/test_phoneme_audio.py', 'w') as f:
    f.write(remote_script)

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/test_phoneme_audio.py")
out = stdout.read().decode('utf-8')
print("STDOUT:\n", out)
sftp.close()
ssh.close()
