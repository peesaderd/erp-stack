import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = r'''
with open("/var/www/kidobits/js/kb-az-engine.js", "r", encoding="utf-8") as f:
    code = f.read()

import re

# 1. Update stopMic to also close AudioContext if open
old_stopmic = """  function stopMic() {
    isListening = false;
    if (volInterval) { clearInterval(volInterval); volInterval = null; }
    if (activeStream) {
      try { activeStream.getTracks().forEach(function(t) { t.stop(); }); } catch (e) {}
      activeStream = null;
    }
    if (activeRecorder && activeRecorder.state === 'recording') {
      try { activeRecorder.stop(); } catch (e) {}
    }
    activeRecorder = null;
    updateMicVisuals(0);
  }"""

new_stopmic = """  function stopMic() {
    isListening = false;
    if (volInterval) { clearInterval(volInterval); volInterval = null; }
    if (activeStream) {
      try { activeStream.getTracks().forEach(function(t) { t.stop(); }); } catch (e) {}
      activeStream = null;
    }
    if (audioContext) {
      try { audioContext.close(); } catch (e) {}
      audioContext = null;
    }
    analyser = null;
    if (activeRecorder && activeRecorder.state === 'recording') {
      try { activeRecorder.stop(); } catch (e) {}
    }
    activeRecorder = null;
    updateMicVisuals(0);
  }"""

if old_stopmic in code:
    code = code.replace(old_stopmic, new_stopmic, 1)
    print("PATCH 1 OK: stopMic updated with track + audioContext release")
else:
    print("PATCH 1 WARNING: old_stopmic not exact match")

# 2. Make sure when recording stops, stopMic() is called to completely release hardware mic
# In mr.onstop and the timeout:
old_timer = """      setTimeout(function() {
        if (isListening && activeRecorder && activeRecorder.state === 'recording') {
          activeRecorder.stop();
        }
      }, 3500);"""

new_timer = """      setTimeout(function() {
        if (isListening) {
          stopMic();
        }
      }, 3500);"""

if old_timer in code:
    code = code.replace(old_timer, new_timer, 1)
    print("PATCH 2 OK: timer now calls stopMic() to release hardware mic")
else:
    print("PATCH 2 WARNING: old_timer not exact match")

# Also in VAD silence detection, make sure it calls stopMic() instead of just activeRecorder.stop()
old_vad_stop = """              // Voice Activity Detection: Stop mic immediately when user stops speaking
              if (activeRecorder && activeRecorder.state === 'recording') {
                activeRecorder.stop();
              }"""

new_vad_stop = """              // Voice Activity Detection: Stop mic immediately when user stops speaking
              stopMic();"""

if old_vad_stop in code:
    code = code.replace(old_vad_stop, new_vad_stop, 1)
    print("PATCH 3 OK: VAD now calls stopMic()")
else:
    print("PATCH 3 WARNING: old_vad_stop not found")

# Make sure on error / catch, stopMic() is guaranteed
old_catch = """          .catch(function(err) {
            updateMicVisuals(0, 'แตะไมค์ 🎙️ เพื่อลองพูดอีกครั้งนะคะ');
          });"""

new_catch = """          .catch(function(err) {
            stopMic();
            updateMicVisuals(0, 'แตะไมค์ 🎙️ เพื่อลองพูดอีกครั้งนะคะ');
          });"""

if old_catch in code:
    code = code.replace(old_catch, new_catch, 1)
    print("PATCH 4 OK: catch now calls stopMic()")

with open("/tmp/kb-az-engine-fixed.js", "w", encoding="utf-8") as f:
    f.write(code)
print("Saved to /tmp/kb-az-engine-fixed.js")
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/fix_mic_close.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/fix_mic_close.py')
print(stdout.read().decode())
print("ERR:", stderr.read().decode())

# Deploy to /var/www/kidobits/js/kb-az-engine.js using sudo
cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/kb-az-engine-fixed.js /var/www/kidobits/js/kb-az-engine.js && echo "DEPLOY_SUCCESS"'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

# Also bump version query in theme_azPlayer.html so browser loads fresh file
cmd2 = 'echo "OpenHands@ERP2026" | sudo -S sed -i "s/kb-az-engine.js?v=[^\"]*/kb-az-engine.js?v=20261114_mic_closed/g" /var/www/kidobits/theme/theme_azPlayer.html'
stdin, stdout, stderr = ssh.exec_command(cmd2)
print("Bump version:", stdout.read().decode())

ssh.close()
