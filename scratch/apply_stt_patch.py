import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)

patch_script = """
with open('/home/openhands/emma-stt/stt_server.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Parse lang field
old_parse = '''            if "hint" in fields:
                try:
                    hint_raw = fields["hint"][1].decode("utf-8", "replace")
                except Exception:
                    hint_raw = ""'''

new_parse = '''            if "hint" in fields:
                try:
                    hint_raw = fields["hint"][1].decode("utf-8", "replace")
                except Exception:
                    hint_raw = ""
            if "lang" in fields:
                try:
                    lang_raw = fields["lang"][1].decode("utf-8", "replace").strip().lower()
                except Exception:
                    lang_raw = ""
            elif "language" in fields:
                try:
                    lang_raw = fields["language"][1].decode("utf-8", "replace").strip().lower()
                except Exception:
                    lang_raw = ""'''

code = code.replace(old_parse, new_parse)

# 2. Support lang in decode_kwargs
old_decode = '''            decode_kwargs = dict(
                language="en",
                beam_size=5,'''

new_decode = '''            target_lang = "zh" if lang_raw in ("zh", "zh-cn", "cmn", "mandarin", "chinese") else "en"
            decode_kwargs = dict(
                language=target_lang,
                beam_size=5,'''

code = code.replace(old_decode, new_decode)

# Also ensure lang_raw is initialized before `if "multipart/form-data" in ctype:`
code = code.replace('hint_raw = ""', 'hint_raw = ""\\n        lang_raw = ""')

with open('/home/openhands/emma-stt/stt_server.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("SUCCESS: stt_server.py patched with multi-language (Chinese + English) support!")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_stt_server.py', 'w') as f:
    f.write(patch_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/patch_stt_server.py && systemctl --user daemon-reload 2>/dev/null || true')
print(stdout.read().decode())
print(stderr.read().decode())

cmd = 'echo "OpenHands@ERP2026" | sudo -S systemctl restart emma-stt.service'
stdin, stdout, stderr = ssh.exec_command(cmd)
print("Restart output:\n", stdout.read().decode())
print("Restart error:\n", stderr.read().decode())
ssh.close()
