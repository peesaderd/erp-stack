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

    # 1. Update stopChineseMic to support fullRelease
    old_stop = """    function stopChineseMic(shouldProcess = false, silent = false) {
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

    new_stop = """    function stopChineseMic(shouldProcess = false, silent = false, fullRelease = false) {
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

      if (fullRelease && __cnMicStream) {
        try {
          __cnMicStream.getTracks().forEach(t => t.stop());
        } catch(e) {}
        __cnMicStream = null;
      }
    }"""

    if old_stop in content:
        content = content.replace(old_stop, new_stop)
        print(f"[{fpath}] Updated stopChineseMic")
    else:
        print(f"[{fpath}] WARNING: old_stop not matched")

    # 2. Update cnMicUI to add 'correct'/'success' (blue button)
    old_mic_ui = """        } else if (state === 'thinking') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-indigo-600 text-white font-display font-black text-sm shadow-lg transition flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🎧 ครูเป่าเปากำลังตรวจเสียง...</span>';
        } else if (state === 'retry') {"""

    new_mic_ui = """        } else if (state === 'thinking') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-indigo-600 text-white font-display font-black text-sm shadow-lg transition flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🎧 ครูเป่าเปากำลังตรวจเสียง...</span>';
        } else if (state === 'correct' || state === 'success') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-sky-500 text-white font-display font-black text-base shadow-xl shadow-sky-500/30 transition flex items-center justify-center gap-2 mx-auto pointer-events-none";
          btn.innerHTML = '<span>🎉 ออกเสียงถูกต้องแล้วค่ะ! เก่งมาก</span>';
        } else if (state === 'retry') {"""

    if old_mic_ui in content:
        content = content.replace(old_mic_ui, new_mic_ui)
        print(f"[{fpath}] Updated cnMicUI button states")
    else:
        print(f"[{fpath}] WARNING: old_mic_ui not matched")

    # Also in cnMicUI for status text styling:
    old_st_text = """      if (st && message) {
        st.className = 'text-xs font-bold text-slate-500 mt-2';
        st.textContent = message;
      }"""

    new_st_text = """      if (st && message) {
        if (state === 'correct' || state === 'success') {
          st.className = 'text-xs font-bold text-sky-600 mt-2';
        } else {
          st.className = 'text-xs font-bold text-slate-500 mt-2';
        }
        st.textContent = message;
      }"""

    if old_st_text in content:
        content = content.replace(old_st_text, new_st_text)
        print(f"[{fpath}] Updated cnMicUI status text styling")

    # 3. Update handlePhonemeEvaluationResult when isPass is true
    old_pass = """      if (evalRes.isPass) {
        playTone('correct');
        TOTAL_STARS += 1;
        updateGlobalStars();
        window.__cnLabAttempts = 0;
        cnMicUI('listening', 'ยอดเยี่ยมมากค่ะ! 🎉');

        fb.innerHTML = `
          <div class="p-3 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-center animate-pop">
            <div class="text-base font-black">🎉 ยอดเยี่ยมมากค่ะ! [ความตรงกัน ${evalRes.score}%] ⭐⭐⭐</div>
            <div class="text-xs font-bold text-emerald-700 mt-0.5">${evalRes.reason}</div>
          </div>
        `;

        speakMandarin('很好！发音很清楚！', 0.9, () => {
          setTimeout(() => {
            CURRENT_STEP = 2;
            renderStep();
          }, 600);
        });
      }"""

    new_pass = """      if (evalRes.isPass) {
        // 1. หยุดคิวเสียงและไมโครโฟนทันที เพื่อป้องกันไมค์เปิดซ้ำ
        cnStopQueue();
        stopChineseMic(false, true, true);
        isMicListening = false;

        playTone('correct');
        TOTAL_STARS += 1;
        updateGlobalStars();
        window.__cnLabAttempts = 0;

        // 2. ปรับปุ่มไมค์เป็นสีฟ้า (Sky Blue) และหยุดการรับเสียง
        cnMicUI('correct', '🎉 ออกเสียงถูกต้องแล้วค่ะ! เก่งมาก (กำลังไปข้อต่อไป...)');

        fb.innerHTML = `
          <div class="p-3 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-center animate-pop">
            <div class="text-base font-black">🎉 ยอดเยี่ยมมากค่ะ! [ความตรงกัน ${evalRes.score}%] ⭐⭐⭐</div>
            <div class="text-xs font-bold text-emerald-700 mt-0.5">${evalRes.reason}</div>
          </div>
        `;

        speakMandarin('很好！发音很清楚！', 0.9, () => {
          setTimeout(() => {
            CURRENT_STEP = 2;
            renderStep();
          }, 600);
        });
      }"""

    if old_pass in content:
        content = content.replace(old_pass, new_pass)
        print(f"[{fpath}] Updated isPass handling in handlePhonemeEvaluationResult")
    else:
        print(f"[{fpath}] WARNING: old_pass not matched")

    # 4. In renderStep, ensure full release of mic when CURRENT_STEP !== 1
    content = content.replace("if (CURRENT_STEP !== 1) {\n        stopChineseMic();\n      }", "if (CURRENT_STEP !== 1) {\n        stopChineseMic(false, true, true);\n      }")
    content = content.replace("function closeLesson() {\n      stopChineseMic();", "function closeLesson() {\n      stopChineseMic(false, true, true);")

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
