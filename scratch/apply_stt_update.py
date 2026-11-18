import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

with open('scratch/update_stt_server.py', 'w') as f:
    pass

update_script = """
with open('/home/openhands/emma-stt/stt_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace definition of is_hallucination
old_def = '''def is_hallucination(text: str, dur: float, rms: float) -> bool:
    t = normalize_text(text)
    if not t:
        return True
    # strip a leading "thanks/thank you" + keep core
    if t in HALLUCINATIONS:
        return True
    # 1-3 word phrases starting with typical hallucination openers
    head = t.split(" ")[0]
    if head in ("thank", "thanks", "subtitle", "subtitles", "subscribe", "amara.org"):
        return True
    # audio evidence: too short or too quiet to be a real spoken answer
    if dur < 0.45:
        return True
    if rms < 0.02:
        return True
    # impossibly fast speech (>5 words per second)
    if len(t.split()) > max(3, dur * 5):
        return True
    return False'''

new_def = '''def is_hallucination(text: str, dur: float, rms: float, hint_words=None) -> bool:
    t = normalize_text(text)
    if not t:
        return True
    # strip a leading "thanks/thank you" + keep core
    if t in HALLUCINATIONS:
        return True
    # 1-3 word phrases starting with typical hallucination openers
    head = t.split(" ")[0]
    if head in ("thank", "thanks", "subtitle", "subtitles", "subscribe", "amara.org"):
        return True

    # Target hint preservation: if Whisper heard the expected target word, do NOT drop
    if hint_words:
        norm_hints = [normalize_text(h) for h in hint_words if h]
        t_tokens = set(t.split())
        if t in norm_hints or any(h in t_tokens for h in norm_hints) or any(h in t for h in norm_hints):
            if dur >= 0.20 and rms >= 0.003:
                return False

    # audio evidence: too short or too quiet to be a real spoken answer
    if dur < 0.40:
        return True
    if rms < 0.01:
        return True
    # impossibly fast speech (>5 words per second)
    if len(t.split()) > max(3, dur * 5):
        return True
    return False'''

assert old_def in content, "old_def not found in content"
content = content.replace(old_def, new_def)

# Replace the 3 callers
old_caller1 = "asr_confident = bool(text) and not is_hallucination(text, dur, rms) \\\\n                and not spelled"
# let's be careful with whitespace:
content = content.replace("not is_hallucination(text, dur, rms)", "not is_hallucination(text, dur, rms, hint_words)")
content = content.replace("if is_hallucination(text, dur, rms):", "if is_hallucination(text, dur, rms, hint_words):")
content = content.replace("if text2 and not is_hallucination(text2, dur, rms):", "if text2 and not is_hallucination(text2, dur, rms, hint_words):")

with open('/home/openhands/emma-stt/stt_server.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated stt_server.py successfully")
"""

sftp = ssh.open_sftp()
with sftp.file('/home/openhands/update_stt.py', 'w') as f:
    f.write(update_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /home/openhands/update_stt.py')
print("output:", stdout.read().decode())
print("error:", stderr.read().decode())

# Restart emma-stt.service
stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S systemctl restart emma-stt.service")
print("restart output:", stdout.read().decode(), stderr.read().decode())

stdin, stdout, stderr = ssh.exec_command("systemctl status emma-stt.service")
print("status:", stdout.read().decode())

ssh.close()
