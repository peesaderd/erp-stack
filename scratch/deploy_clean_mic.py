import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = r'''
with open("/var/www/kidobits/js/kb-az-engine.js", "r", encoding="utf-8") as f:
    code = f.read()

# 1. In onstop when result is not matched:
old_fail = """            if (fuzzyOk || isMatch(spoken, targetLetter)) {
              handleSuccess(targetLetter, spoken || targetWord);
            } else {
              updateMicVisuals(0, 'ได้ยิน: “' + spoken + '” (แตะไมค์ 🎙️ ลองใหม่อีกรอบนะคนเก่ง)');
            }"""

new_fail = """            if (fuzzyOk || isMatch(spoken, targetLetter)) {
              handleSuccess(targetLetter, spoken || targetWord);
            } else {
              stopMic();
              updateMicVisuals(0, 'ได้ยิน: “' + spoken + '” (แตะไมค์ 🎙️ ลองใหม่อีกรอบนะคนเก่ง)');
            }"""

if old_fail in code:
    code = code.replace(old_fail, new_fail, 1)
    print("PATCH A OK: stopMic on speech not match")
else:
    print("PATCH A ERROR: old_fail not found")

# 2. In onstop when chunks length is 0:
old_chunks = """        if (chunks.length === 0) return;"""
new_chunks = """        if (chunks.length === 0) {
          stopMic();
          return;
        }"""

if old_chunks in code:
    code = code.replace(old_chunks, new_chunks, 1)
    print("PATCH B OK: stopMic on empty chunks")
else:
    print("PATCH B ERROR: old_chunks not found")

# 3. Before mr.onstop triggers, when activeRecorder.stop() is called:
# If setTimeout finishes 3500ms, it must stop activeRecorder AND activeStream immediately
old_timer = """      setTimeout(function() {
        if (isListening) {
          stopMic();
        }
      }, 3500);"""

new_timer = """      setTimeout(function() {
        if (isListening && activeRecorder && activeRecorder.state === 'recording') {
          try { activeRecorder.stop(); } catch (e) {}
        }
        if (activeStream) {
          try { activeStream.getTracks().forEach(function(t) { t.stop(); }); } catch (e) {}
        }
      }, 3500);"""

if old_timer in code:
    code = code.replace(old_timer, new_timer, 1)
    print("PATCH C OK: timeout stops recorder and stops media stream tracks")
else:
    print("PATCH C ERROR: old_timer not found")

# 4. In VAD silence detection:
old_vad = """              // Voice Activity Detection: Stop mic immediately when user stops speaking
              stopMic();"""

new_vad = """              // Voice Activity Detection: Stop recording and release mic track immediately
              if (activeRecorder && activeRecorder.state === 'recording') {
                try { activeRecorder.stop(); } catch (e) {}
              }
              if (activeStream) {
                try { activeStream.getTracks().forEach(function(t) { t.stop(); }); } catch (e) {}
              }"""

if old_vad in code:
    code = code.replace(old_vad, new_vad, 1)
    print("PATCH D OK: VAD stops recorder and stops media stream tracks")
else:
    print("PATCH D ERROR: old_vad not found")

with open("/tmp/kb-az-engine-clean.js", "w", encoding="utf-8") as f:
    f.write(code)
print("Temp file ready")
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/apply_clean_mic.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/apply_clean_mic.py')
print(stdout.read().decode())
print("ERR:", stderr.read().decode())

cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/kb-az-engine-clean.js /var/www/kidobits/js/kb-az-engine.js && echo "DEPLOYED_OK"'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

cmd2 = 'echo "OpenHands@ERP2026" | sudo -S sed -i "s/kb-az-engine.js?v=[^\"]*/kb-az-engine.js?v=20261114_clean_v1/g" /var/www/kidobits/theme/theme_azPlayer.html'
stdin, stdout, stderr = ssh.exec_command(cmd2)
print(stdout.read().decode())

ssh.close()
