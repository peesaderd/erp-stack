import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = """
path = '/var/www/kidobits/theme/theme_phonicsLesson.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = '''    // Initial check when page loads: Show Floating Continue Toast if saved progress exists
    window.addEventListener('load', async () => {
      let saved = progLoad();
      if (!saved) {
        try {
          const res = await fetch(`${API_BASE}/progress/get?user_id=guest&lesson_id=${LID}`);
          const d = await res.json();
          if (d && d.ok && d.found && d.progress && !d.progress.done && d.progress.step > 1) {
            saved = { step: d.progress.step, itemIndex: d.progress.item_index || 0 };
          }
        } catch(e) {}
      }

      if (saved && saved.step > 1) {
        // Floating Continue button: หายไปเองใน 6 วินาที ถ้าไม่กด
        resumeToast(saved.step, (action) => {
          if (action === 'continue') {
            startLessonWithAudio(saved.step);
          } else if (action === 'reset') {
            progClear();
            startLessonWithAudio(1);
          }
        });
      }
    });'''

replacement = '''    // Initial check: Show Floating Continue Toast if saved progress exists (disappears in 6s if not pressed)
    async function checkAndShowResumeToast() {
      let saved = progLoad();
      if (!saved || saved.step <= 1) {
        try {
          const res = await fetch(`${API_BASE}/progress/get?user_id=guest&lesson_id=${LID}`);
          const d = await res.json();
          if (d && d.ok && d.found && d.progress && !d.progress.done && d.progress.step > 1) {
            saved = { step: d.progress.step, itemIndex: d.progress.item_index || 0 };
          }
        } catch(e) {}
      }

      if (saved && saved.step > 1) {
        resumeToast(saved.step, (action) => {
          if (action === 'continue') {
            startLessonWithAudio(saved.step);
          } else if (action === 'reset') {
            progClear();
            startLessonWithAudio(1);
          }
        });
      }
    }

    if (document.readyState === 'loading') {
      window.addEventListener('DOMContentLoaded', () => setTimeout(checkAndShowResumeToast, 300));
    } else {
      setTimeout(checkAndShowResumeToast, 300);
    }'''

if target in content:
    content = content.replace(target, replacement)
    with open('/tmp/theme_phonicsLesson.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced checkAndShowResumeToast successfully!")
else:
    print("Could not find target block in theme_phonicsLesson.html")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_resume_ready.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/patch_resume_ready.py")
print("Patch stdout:\n", stdout.read().decode())
print("Patch stderr:\n", stderr.read().decode())

stdin, stdout, stderr = ssh.exec_command("""
echo 'OpenHands@ERP2026' | sudo -S cp /tmp/theme_phonicsLesson.html /var/www/kidobits/theme/theme_phonicsLesson.html
echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_phonicsLesson.html
""")
print("Deploy stdout:\n", stdout.read().decode())
print("Deploy stderr:\n", stderr.read().decode())

ssh.close()
