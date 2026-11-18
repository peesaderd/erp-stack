import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

update_script = """
with open('/home/openhands/emma-phonics/api_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_advance = '''def handle_session_advance(payload):
    \"\"\"เลื่อนไปตำแหน่งถัดไป — idempotent: เรียกซ้ำได้ ไม่ข้ามข้อ\"\"\"
    sid = payload.get("session")
    s = _get_session(sid)
    if not s:
        return 404, {"ok": False, "error": "session-not-found"}
    lesson = LESSONS[s["lesson"]]
    if s["done"]:
        return 409, {"ok": False, "error": "lesson-done"}
    if not s["answered"]:
        return 409, {"ok": False, "error": "not-answered", "step": s["step"], "index": s["index"]}'''

new_advance = '''def handle_session_advance(payload):
    \"\"\"เลื่อนไปตำแหน่งถัดไป — idempotent: เรียกซ้ำได้ ไม่ข้ามข้อ (เว้นแต่ force=True)\"\"\"
    sid = payload.get("session")
    force = bool(payload.get("force", False))
    s = _get_session(sid)
    if not s:
        return 404, {"ok": False, "error": "session-not-found"}
    lesson = LESSONS[s["lesson"]]
    if s["done"]:
        return 409, {"ok": False, "error": "lesson-done"}
    if not s["answered"] and not force:
        return 409, {"ok": False, "error": "not-answered", "step": s["step"], "index": s["index"]}'''

assert old_advance in content, "old_advance not found in content"
content = content.replace(old_advance, new_advance)

# Add handle_session_jump before handle_session_audio
jump_fn = '''def handle_session_jump(payload):
    \"\"\"กระโดดไปยังขั้น (step) และ index ที่ต้องการโดยตรง\"\"\"
    sid = payload.get("session")
    s = _get_session(sid)
    if not s:
        return 404, {"ok": False, "error": "session-not-found"}
    lesson = LESSONS[s["lesson"]]

    try:
        target_step = int(payload.get("step", 1))
    except Exception:
        target_step = 1

    try:
        target_index = int(payload.get("index", 0))
    except Exception:
        target_index = 0

    if target_step not in s["steps"]:
        return 400, {"ok": False, "error": f"invalid-step: {target_step} not in {s['steps']}"}

    items = step_items(lesson, target_step)
    if not items:
        return 400, {"ok": False, "error": f"no-items-for-step-{target_step}"}

    if target_index >= len(items):
        target_index = 0

    step_changed = (target_step != s["step"])
    s["step"] = target_step
    s["index"] = target_index
    s["answered"] = False
    s["done"] = False

    return 200, {
        "ok": True,
        "done": False,
        "item": _item_payload(lesson, target_step, target_index),
        "expect": _expect_payload(lesson, target_step, target_index),
        "script": _item_script(lesson, target_step, target_index, with_teach=step_changed),
        "progress": {"step": target_step, "index": target_index,
                     "step_no": s["steps"].index(target_step) + 1,
                     "step_count": len(s["steps"])},
    }


def handle_session_audio(sid):'''

assert "def handle_session_audio(sid):" in content, "handle_session_audio not found"
content = content.replace("def handle_session_audio(sid):", jump_fn)

# Add /session/jump to Handler.do_POST
old_post = '''        elif path == "/session/advance":
            self._json(*handle_session_advance(payload))'''

new_post = '''        elif path == "/session/advance":
            self._json(*handle_session_advance(payload))
        elif path == "/session/jump":
            self._json(*handle_session_jump(payload))'''

assert old_post in content, "old_post not found"
content = content.replace(old_post, new_post)

with open('/home/openhands/emma-phonics/api_server.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated api_server.py successfully")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/update_api.py', 'w') as f:
    f.write(update_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/update_api.py")
print("update output:", stdout.read().decode())
print("update error:", stderr.read().decode())

# Restart emma-phonics.service
stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S systemctl restart emma-phonics.service")
print("restart:", stdout.read().decode(), stderr.read().decode())

stdin, stdout, stderr = ssh.exec_command("systemctl status emma-phonics.service")
print("status:", stdout.read().decode())

ssh.close()
