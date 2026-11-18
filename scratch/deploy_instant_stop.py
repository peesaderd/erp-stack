import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = r'''
with open("/var/www/kidobits/js/kb-az-engine.js", "r", encoding="utf-8") as f:
    text = f.read()

# In mr.onstop, release activeStream AND audioContext immediately before fetch!
old_code = """      mr.onstop = function() {
        if (passed || !isAZScreen() || currentLetter !== targetLetter) return;
        if (chunks.length === 0) {
          stopMic();
          return;
        }"""

new_code = """      mr.onstop = function() {
        // Stop audio input stream immediately when recording stops
        if (activeStream) {
          try { activeStream.getTracks().forEach(function(t) { t.stop(); }); } catch (e) {}
          activeStream = null;
        }
        if (volInterval) { clearInterval(volInterval); volInterval = null; }
        if (audioContext) {
          try { audioContext.close(); } catch (e) {}
          audioContext = null;
        }
        analyser = null;

        if (passed || !isAZScreen() || currentLetter !== targetLetter) return;
        if (chunks.length === 0) {
          stopMic();
          return;
        }"""

if old_code in text:
    text = text.replace(old_code, new_code, 1)
    print("SUCCESS: Stream tracks and AudioContext stopped immediately on mr.onstop!")
    with open("/tmp/kb-az-engine-instant.js", "w", encoding="utf-8") as f:
        f.write(text)
else:
    print("ERROR: old_code not found")
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/apply_instant_stop.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/apply_instant_stop.py')
print(stdout.read().decode())
print("ERR:", stderr.read().decode())

cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/kb-az-engine-instant.js /var/www/kidobits/js/kb-az-engine.js && echo "DEPLOY_JS_OK"'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

cmd2 = 'echo "OpenHands@ERP2026" | sudo -S sed -i "s/kb-az-engine.js?v=[^\"]*/kb-az-engine.js?v=20261114_instant_off/g" /var/www/kidobits/theme/theme_azPlayer.html'
stdin, stdout, stderr = ssh.exec_command(cmd2)
print(stdout.read().decode())

ssh.close()
