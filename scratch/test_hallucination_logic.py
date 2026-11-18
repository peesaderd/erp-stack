import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

test_script = """
import sys
sys.path.insert(0, '/home/openhands/emma-stt')
from stt_server import is_hallucination

cases = [
    ('at', 6.0, 0.018, ['at'], False),
    ('sat', 5.94, 0.017, ['sat'], False),
    ('mat', 6.0, 0.013, ['mat'], False),
    ('pat', 6.0, 0.007, ['pat'], False),
    ('thank you for watching', 1.0, 0.05, ['sat'], True),
    ('', 1.0, 0.0, ['sat'], True),
]

all_pass = True
for text, dur, rms, hints, expected in cases:
    res = is_hallucination(text, dur, rms, hints)
    ok = (res == expected)
    if not ok:
        all_pass = False
    print(f"text={text!r}, dur={dur}, rms={rms}, hints={hints} -> {res} (expected {expected}) {'OK' if ok else 'FAIL'}")

print("ALL TEST CASES PASSED:", all_pass)
"""

stdin, stdout, stderr = ssh.exec_command(f"python3 -c \"{test_script}\"")
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
