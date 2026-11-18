import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_code = """
import re

STT_PATH = '/home/openhands/emma-stt/stt_server.py'
with open(STT_PATH, 'r', encoding='utf-8') as f:
    code = f.read()

# Make backup
with open('/home/openhands/backups/stt_server.py.bak_l2', 'w', encoding='utf-8') as f:
    f.write(code)

new_aliases_str = '''
    # Level 2 Words
    "at": {"at", "add", "ad", "et", "ed", "hat", "att"},
    "big": {"big", "pig", "beak", "bic", "beg", "bick", "bigs"},
    "bin": {"bin", "been", "bean", "pin", "bing", "bins"},
    "bug": {"bug", "back", "buck", "bag", "bog", "bugs"},
    "bun": {"bun", "ban", "pan", "burn", "buns"},
    "cap": {"cap", "cup", "cab", "cat", "caps"},
    "cot": {"cot", "cut", "cod", "cat", "caught", "cots"},
    "dig": {"dig", "dick", "deek", "deck", "digs"},
    "dot": {"dot", "dat", "dock", "duck", "dots"},
    "fin": {"fin", "thin", "fan", "pin", "thing", "fins"},
    "fog": {"fog", "fork", "fox", "fock", "frog", "fogs"},
    "fun": {"fun", "fan", "fang", "fine", "funs"},
    "hot": {"hot", "hat", "heart", "hard", "hod"},
    "hug": {"hug", "hack", "hook", "hawk", "hugs"},
    "jet": {"jet", "jed", "check", "jack", "chat", "jets"},
    "jog": {"jog", "jock", "chock", "shock", "joke", "jogs"},
    "pan": {"pan", "pen", "pin", "fan", "pam", "pans"},
    "pat": {"pat", "pet", "pad", "bad", "bat", "pats"},
    "pet": {"pet", "pat", "ped", "bet", "pets"},
    "pig": {"pig", "pick", "peek", "peg", "pigs"},
    "pin": {"pin", "pen", "bin", "tin", "peen", "ping", "pins"},
    "pot": {"pot", "pod", "part", "hot", "pots"},
    "rug": {"rug", "rag", "rock", "rack", "rugs"},
    "run": {"run", "ran", "rum", "one", "ren", "runs"},
    "sat": {"sat", "set", "sad", "sed", "sack", "sap", "sats"},
    "sit": {"sit", "set", "seed", "sick", "seat", "sits"},
    "sun": {"sun", "son", "san", "some", "sung", "suns"},
    "ten": {"ten", "tin", "tan", "den", "tens"},
    "tip": {"tip", "tib", "deep", "dip", "teep", "tips"},
    "win": {"win", "wen", "when", "one", "wind", "wing", "wins"},
'''

pos = code.find('WORD_ALIASES = {')
if pos != -1:
    pos += len('WORD_ALIASES = {')
    code = code[:pos] + new_aliases_str + code[pos:]
    with open(STT_PATH, 'w', encoding='utf-8') as f:
        f.write(code)
    print("Updated stt_server.py successfully!")
else:
    print("Could not find WORD_ALIASES in stt_server.py")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/apply_stt_l2.py', 'w') as f:
    f.write(remote_code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/apply_stt_l2.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR:", err)

# Restart emma-stt
stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S systemctl restart emma-stt")
print("Restart stt:", stdout.read().decode(), stderr.read().decode())

# Check health
stdin, stdout, stderr = ssh.exec_command("curl -s http://127.0.0.1:8115/health")
print("Health:", stdout.read().decode())

ssh.close()
