import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

test_script = """
import os, sys, json, time, re

PROGRESS_FILE = '/home/openhands/emma-phonics/data/progress.json'

sample_data = {
    "guest": {
        "latest": {
            "user_id": "guest",
            "subject": "Phonics",
            "lesson_id": "L3.01",
            "level": 3,
            "step": 2,
            "item_index": 1,
            "total_steps": 5,
            "done": False,
            "percent": 40,
            "title": "Level 3: sh - เสียง sh /ʃ/",
            "url": "theme_phonicsLesson.html?lesson=L3.01&step=2",
            "updated_at": int(time.time())
        },
        "lessons": {
            "L3.01": {
                "user_id": "guest",
                "subject": "Phonics",
                "lesson_id": "L3.01",
                "level": 3,
                "step": 2,
                "item_index": 1,
                "total_steps": 5,
                "done": False,
                "percent": 40,
                "title": "Level 3: sh - เสียง sh /ʃ/",
                "url": "theme_phonicsLesson.html?lesson=L3.01&step=2",
                "updated_at": int(time.time())
            }
        }
    }
}

os.makedirs('/home/openhands/emma-phonics/data', exist_ok=True)
with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
    json.dump(sample_data, f, ensure_ascii=False, indent=2)

print("Saved sample progress.json successfully.")
with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
    loaded = json.load(f)
print("Loaded user count:", len(loaded))
print("Guest latest lesson:", loaded['guest']['latest']['lesson_id'])
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/test_prog.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/test_prog.py")
print("Output:\n", stdout.read().decode())
print("Error:\n", stderr.read().decode())

ssh.close()
