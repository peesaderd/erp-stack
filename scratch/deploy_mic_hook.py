import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = r'''
with open("/var/www/kidobits/theme/theme_azPlayer.html", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Direct onClick in React bundle:
target_click = 'onClick:()=>{Qt(0),iP(Qt,()=>{ne("เก่งมาก! ฟังและพูดตามได้แล้ว \\uD83C\\uDF89"),Bn(5,5)})}'
replace_click = 'onClick:()=>{if(window.triggerAZMic){window.triggerAZMic();}else{Qt(0);iP(Qt,()=>{ne("เก่งมาก! ฟังและพูดตามได้แล้ว \\uD83C\\uDF89");Bn(5,5)});}}'

if target_click in text:
    text = text.replace(target_click, replace_click, 1)
    print("SUCCESS 1: onClick hooked to window.triggerAZMic")
else:
    print("ERROR 1: target_click not found")

# 2. Expose triggerAZMic on window in kb-az-engine.js:
# Let's inspect kb-az-engine.js and add window.triggerAZMic
with open("/var/www/kidobits/js/kb-az-engine.js", "r", encoding="utf-8") as f:
    engine = f.read()

engine_hook = """  window.triggerAZMic = function() {
    var letter = detectCurrentLetter();
    if (!letter) return;
    if (isListening) {
      stopMic();
      updateMicVisuals(0, 'หยุดไมค์แล้ว แตะเพื่อเริ่มใหม่');
    } else {
      startMic(letter);
    }
  };
"""

if "window.triggerAZMic" not in engine:
    engine = engine.replace("})();", engine_hook + "\n})();", 1)
    print("SUCCESS 2: window.triggerAZMic added to kb-az-engine.js")
    with open("/tmp/kb-az-engine-hooked.js", "w", encoding="utf-8") as f:
        f.write(engine)
else:
    print("SUCCESS 2: window.triggerAZMic already exists")

with open("/tmp/theme_azPlayer_hooked.html", "w", encoding="utf-8") as f:
    f.write(text)
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/apply_hook.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/apply_hook.py')
print(stdout.read().decode())
print("ERR:", stderr.read().decode())

cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_azPlayer_hooked.html /var/www/kidobits/theme/theme_azPlayer.html && echo "DEPLOY_HTML_OK"'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

cmd2 = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/kb-az-engine-hooked.js /var/www/kidobits/js/kb-az-engine.js 2>/dev/null && echo "DEPLOY_JS_OK" || true'
stdin, stdout, stderr = ssh.exec_command(cmd2)
print(stdout.read().decode())

ssh.close()
