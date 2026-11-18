import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = r'''
with open("/var/www/kidobits/js/kb-az-engine.js", "r", encoding="utf-8") as f:
    code = f.read()

# Backup to /tmp
with open("/tmp/kb-az-engine.js.bak", "w", encoding="utf-8") as f:
    f.write(code)

old_block = """      var blob = new Blob(chunks, { type: 'audio/webm' });
        var fd = new FormData();
        fd.append('file', blob, 'audio.webm');
        var targetWord = PHONICS[targetLetter] ? PHONICS[targetLetter].word : targetLetter;
        fd.append('hint', targetWord);

        updateMicVisuals(25, 'กำลังตรวจเสียงอ่าน... ✨');
        fetch('/kidobits/stt', { method: 'POST', body: fd })
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (passed || !isAZScreen() || currentLetter !== targetLetter) return;
            var spoken = (data && (data.text || data.transcript || '')) || '';
            if (isMatch(spoken, targetLetter)) {
              handleSuccess(targetLetter, spoken);
            } else {
              updateMicVisuals(0, 'ได้ยิน: “' + spoken + '” (แตะไมค์ 🎙️ ลองใหม่อีกรอบนะคนเก่ง)');
            }
          })
          .catch(function(err) {
            updateMicVisuals(0, 'แตะไมค์ 🎙️ เพื่อลองพูดอีกครั้งนะคะ');
          });"""

new_block = """      var mime = (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported('audio/webm;codecs=opus'))
          ? 'audio/webm;codecs=opus' : (activeRecorder.mimeType || 'audio/webm');
        var blob = new Blob(chunks, { type: mime });
        var fd = new FormData();
        fd.append('audio', blob, 'child.webm');
        fd.append('file', blob, 'audio.webm');
        var targetWord = PHONICS[targetLetter] ? PHONICS[targetLetter].word : targetLetter;
        var hintWords = [targetWord, targetLetter];
        if (PHONICS[targetLetter] && PHONICS[targetLetter].alts) {
          hintWords = hintWords.concat(PHONICS[targetLetter].alts);
        }
        fd.append('hint', hintWords.filter(Boolean).join(','));

        updateMicVisuals(25, 'กำลังตรวจเสียงอ่าน... ✨');
        fetch('/kidobits/stt', { method: 'POST', body: fd })
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (passed || !isAZScreen() || currentLetter !== targetLetter) return;
            var spoken = (data && (data.text || data.transcript || '')) || '';
            var fuzzyOk = !!(data && data.fuzzy_ok);
            if (fuzzyOk || isMatch(spoken, targetLetter)) {
              handleSuccess(targetLetter, spoken || targetWord);
            } else {
              updateMicVisuals(0, 'ได้ยิน: “' + spoken + '” (แตะไมค์ 🎙️ ลองใหม่อีกรอบนะคนเก่ง)');
            }
          })
          .catch(function(err) {
            updateMicVisuals(0, 'แตะไมค์ 🎙️ เพื่อลองพูดอีกครั้งนะคะ');
          });"""

if old_block in code:
    code = code.replace(old_block, new_block, 1)
    print("SUCCESS: onstop updated with 'audio' + 'file' and hints")
else:
    print("ERROR: old_block not found!")

# VAD silence detection
old_vad_block = """          var dataArray = new Uint8Array(analyser.frequencyBinCount);
          volInterval = setInterval(function() {
            if (!isListening || !analyser) return;
            analyser.getByteFrequencyData(dataArray);
            var sum = 0;
            for (var i = 0; i < dataArray.length; i++) sum += dataArray[i];
            var avg = sum / dataArray.length;
            var pct = Math.min(100, Math.round((avg / 128) * 100));
            updateMicVisuals(pct);
          }, 80);"""

new_vad_block = """          var dataArray = new Uint8Array(analyser.frequencyBinCount);
          var speechDetected = false;
          var lastVoiceTime = 0;
          var voicedMs = 0;

          volInterval = setInterval(function() {
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
              // Voice Activity Detection: Stop mic immediately when user stops speaking
              if (activeRecorder && activeRecorder.state === 'recording') {
                activeRecorder.stop();
              }
            }
          }, 80);"""

if old_vad_block in code:
    code = code.replace(old_vad_block, new_vad_block, 1)
    print("SUCCESS: VAD silence detection added (auto cuts 700ms after speaking)")
else:
    print("ERROR: old_vad_block not found!")

with open("/tmp/kb-az-engine-new.js", "w", encoding="utf-8") as f:
    f.write(code)
print("Temp file ready in /tmp/kb-az-engine-new.js")
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/patch_az_engine.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/patch_az_engine.py')
print(stdout.read().decode())
print("ERR:", stderr.read().decode())

# Now sudo cp to /var/www/kidobits/js/kb-az-engine.js
cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/kb-az-engine-new.js /var/www/kidobits/js/kb-az-engine.js && echo "DEPLOY_OK" && sudo chmod 644 /var/www/kidobits/js/kb-az-engine.js'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
