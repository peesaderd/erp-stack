import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

files = [
    ('/var/www/kidobits/chinese.html', '/tmp/chinese.html'),
    ('/var/www/kidobits/chinese_lab.html', '/tmp/chinese_lab.html')
]

sftp = ssh.open_sftp()

for fpath, tmppath in files:
    with sftp.open(fpath, 'r') as f:
        content = f.read().decode('utf-8')

    # 1. Update stopChineseMic signature and implementation
    old_stop = """    function stopChineseMic(shouldProcess = false) {
      if (__cnMaxTimer) { clearTimeout(__cnMaxTimer); __cnMaxTimer = null; }
      if (window.__cnSilenceTimer) { clearTimeout(window.__cnSilenceTimer); window.__cnSilenceTimer = null; }

      if (__cnMediaRecorder && __cnMediaRecorder.state === 'recording') {
        if (shouldProcess) {
          try { __cnMediaRecorder.stop(); } catch(e) {}
        } else {
          try {
            __cnMediaRecorder.onstop = null;
            __cnMediaRecorder.stop();
          } catch(e) {}
          isMicListening = false;
          cnMicUI('retry', '');
        }
      } else {
        isMicListening = false;
        cnMicUI('retry', '');
      }

      if (window.__cnActiveRecognizer) {
        try { window.__cnActiveRecognizer.abort(); } catch(e) {}
        window.__cnActiveRecognizer = null;
      }
    }"""

    new_stop = """    function stopChineseMic(shouldProcess = false, silent = false) {
      if (__cnMaxTimer) { clearTimeout(__cnMaxTimer); __cnMaxTimer = null; }
      if (window.__cnSilenceTimer) { clearTimeout(window.__cnSilenceTimer); window.__cnSilenceTimer = null; }

      if (__cnMediaRecorder && __cnMediaRecorder.state === 'recording') {
        if (shouldProcess) {
          try { __cnMediaRecorder.stop(); } catch(e) {}
        } else {
          try {
            __cnMediaRecorder.onstop = null;
            __cnMediaRecorder.stop();
          } catch(e) {}
          isMicListening = false;
          if (!silent) cnMicUI('retry', '');
        }
      } else {
        isMicListening = false;
        if (!silent) cnMicUI('retry', '');
      }

      if (window.__cnActiveRecognizer) {
        try { window.__cnActiveRecognizer.abort(); } catch(e) {}
        window.__cnActiveRecognizer = null;
      }
    }"""

    if old_stop in content:
        content = content.replace(old_stop, new_stop)
        print(f"[{fpath}] Updated stopChineseMic")
    else:
        print(f"[{fpath}] WARNING: old_stop not matched exactly")

    # 2. Update cnMicUI states (remove 🎙️ and replace 'แตะไมค์' with 'แตะ')
    old_mic_ui = """        } else if (state === 'retry') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white font-display font-black text-sm shadow-lg shadow-amber-500/30 transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🔁 แตะไมค์เพื่อลองพูดอีกครั้ง</span>';
        } else {
          btn.className = "px-6 py-3.5 rounded-2xl bg-emerald-600 hover:bg-emerald-700 text-white font-display font-black text-sm shadow-lg transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🎙️ ไมค์พร้อมรับฟัง</span>';
        }"""

    new_mic_ui = """        } else if (state === 'retry') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white font-display font-black text-sm shadow-lg shadow-amber-500/30 transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🔁 แตะเพื่อลองพูดอีกครั้ง</span>';
        } else {
          btn.className = "px-6 py-3.5 rounded-2xl bg-emerald-600 hover:bg-emerald-700 text-white font-display font-black text-sm shadow-lg transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🔴 ระบบพร้อมรับฟังเสียง</span>';
        }"""

    if old_mic_ui in content:
        content = content.replace(old_mic_ui, new_mic_ui)
        print(f"[{fpath}] Updated cnMicUI")
    else:
        print(f"[{fpath}] WARNING: old_mic_ui not matched exactly")

    # 3. Update triggerChineseMic to call stopChineseMic(false, true)
    old_trigger = """    function triggerChineseMic(targetText) {
      if (isMicListening) {
        stopChineseMic(true);
        return;
      }
      stopChineseMic(false);"""

    new_trigger = """    function triggerChineseMic(targetText) {
      if (isMicListening) {
        stopChineseMic(true);
        return;
      }
      stopChineseMic(false, true);"""

    if old_trigger in content:
        content = content.replace(old_trigger, new_trigger)
        print(f"[{fpath}] Updated triggerChineseMic")
    else:
        print(f"[{fpath}] WARNING: old_trigger not matched exactly")

    # 4. Remove 🎙️ from startServerSTTRecording listening message
    old_rec_msg = "cnMicUI('listening', '🎙️ ไมค์เปิดอัตโนมัติแล้ว... พูดคำว่า \"' + targetText + '\" ได้เลยค่ะ');"
    new_rec_msg = "cnMicUI('listening', '🔴 ไมค์เปิดอัตโนมัติแล้ว... พูดคำว่า \"' + targetText + '\" ได้เลยค่ะ');"
    if old_rec_msg in content:
        content = content.replace(old_rec_msg, new_rec_msg)
        print(f"[{fpath}] Updated startServerSTTRecording listening msg")
    else:
        print(f"[{fpath}] WARNING: old_rec_msg not matched exactly")

    # 5. In renderSpeakStep, sanitize data.prompt
    old_prompt_line = '<p class="text-sm font-bold text-slate-700">${data.prompt}</p>'
    new_prompt_line = '<p class="text-sm font-bold text-slate-700">${(data.prompt || \'\').replace(/แตะไมค์แล้ว/g, \'ฟังครูอ่านนำ แล้ว\')}</p>'
    if old_prompt_line in content:
        content = content.replace(old_prompt_line, new_prompt_line)
        print(f"[{fpath}] Updated renderSpeakStep prompt line")

    # 6. Replace lesson prompts
    content = content.replace("prompt: 'แตะไมค์แล้ว", "prompt: 'ฟังครูอ่านนำ แล้ว")
    content = content.replace("? 'สัญญาณอินเทอร์เน็ตขาดช่วง แตะไมค์อีกครั้งนะคะ'", "? 'สัญญาณอินเทอร์เน็ตขาดช่วง แตะเพื่อลองอีกครั้งนะคะ'")
    content = content.replace("? 'ยังไม่ได้ยินเสียง — แตะไมค์แล้วพูดดัง ๆ ใกล้ไมค์อีกครั้งนะคะ'", "? 'ยังไม่ได้ยินเสียง — แตะเพื่อลองพูดอีกครั้งนะคะ'")

    with sftp.open(tmppath, 'w') as f:
        f.write(content.encode('utf-8'))
    print(f"Wrote to {tmppath}")

sftp.close()

# Copy with sudo
for fpath, tmppath in files:
    cmd = f"echo 'OpenHands@ERP2026' | sudo -S cp {tmppath} {fpath} && echo 'OpenHands@ERP2026' | sudo -S chown openhands:www-data {fpath}"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    stdout.channel.recv_exit_status()
    print(f"Copied {tmppath} -> {fpath}")

ssh.close()
print("All done!")
