import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = r'''
with open("/var/www/kidobits/js/kb-az-engine.js", "r", encoding="utf-8") as f:
    code = f.read()

import re

# 1. Update getUserMedia constraints to enable noiseSuppression and echoCancellation
old_gum = "navigator.mediaDevices.getUserMedia({ audio: true })"
new_gum = "navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })"

if old_gum in code:
    code = code.replace(old_gum, new_gum, 1)
    print("STEP 1 OK: Hardware noise suppression & echo cancellation enabled")
else:
    print("STEP 1 WARNING: old_gum not exact match")

# 2. Update the volume interval to implement:
# - Speech threshold = 22% (noise floor is usually < 15%)
# - Silence countdown = 600ms (0.6s)
# - When 600ms silence reached after speaking -> stop immediately!
old_loop = """          volInterval = setInterval(function() {
            if (!isListening || !analyser) return;
            analyser.getByteFrequencyData(dataArray);
            var sum = 0;
            for (var i = 0; i < dataArray.length; i++) sum += dataArray[i];
            var avg = sum / dataArray.length;
            var pct = Math.min(100, Math.round((avg / 128) * 100));
            updateMicVisuals(pct);

            var now = Date.now();
            if (pct >= 14) {
              speechDetected = true;
              lastVoiceTime = now;
              voicedMs += 80;
            } else if (speechDetected && (now - lastVoiceTime >= 700) && voicedMs >= 240) {
              // Voice Activity Detection: Stop recording and release mic track immediately
              if (activeRecorder && activeRecorder.state === 'recording') {
                try { activeRecorder.stop(); } catch (e) {}
              }
              if (activeStream) {
                try { activeStream.getTracks().forEach(function(t) { t.stop(); }); } catch (e) {}
              }
            }
          }, 80);"""

new_loop = """          var speechDetected = false;
          var lastVoiceTime = Date.now();
          var voicedMs = 0;
          var startTime = Date.now();

          volInterval = setInterval(function() {
            if (!isListening || !analyser) return;
            analyser.getByteFrequencyData(dataArray);
            var sum = 0;
            for (var i = 0; i < dataArray.length; i++) sum += dataArray[i];
            var avg = sum / dataArray.length;
            var pct = Math.min(100, Math.round((avg / 128) * 100));
            updateMicVisuals(pct);

            var now = Date.now();
            // Threshold 20%: Ignore room noise/fan/aircon. Real speech is > 20%
            if (pct >= 20) {
              speechDetected = true;
              lastVoiceTime = now;
              voicedMs += 60;
            } else if (speechDetected) {
              // Once user started speaking, if silence (pct < 20%) lasts >= 600ms (0.6 sec), CUT IMMEDIATELY!
              if (now - lastVoiceTime >= 600 && voicedMs >= 180) {
                stopMic();
              }
            } else if (now - startTime >= 4000) {
              // If user didn't speak anything for 4 seconds, auto close
              stopMic();
            }
          }, 60);"""

if old_loop in code:
    code = code.replace(old_loop, new_loop, 1)
    print("STEP 2 OK: Clean 0.6s silence countdown + noise floor cutoff applied")
else:
    print("STEP 2 WARNING: old_loop not found")

with open("/tmp/kb-az-engine-clean-vad.js", "w", encoding="utf-8") as f:
    f.write(code)
print("Saved /tmp/kb-az-engine-clean-vad.js")
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/apply_clean_vad.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/apply_clean_vad.py')
print(stdout.read().decode())
print("ERR:", stderr.read().decode())

# Copy to production
cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/kb-az-engine-clean-vad.js /var/www/kidobits/js/kb-az-engine.js && echo "DEPLOY_JS_OK"'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

# Bump cache version in theme_azPlayer.html
cmd2 = 'echo "OpenHands@ERP2026" | sudo -S sed -i "s/kb-az-engine.js?v=[^\"]*/kb-az-engine.js?v=20261114_vad_600ms/g" /var/www/kidobits/theme/theme_azPlayer.html'
stdin, stdout, stderr = ssh.exec_command(cmd2)
print("Bump HTML:", stdout.read().decode())

ssh.close()
