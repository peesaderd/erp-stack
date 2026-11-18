import paramiko

print("Connecting to remote server 89.167.82.205...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=15)
sftp = ssh.open_sftp()

print("Reading /var/www/kidobits/chinese.html...")
with sftp.open('/var/www/kidobits/chinese.html', 'r') as f:
    html = f.read().decode('utf-8')

# 1. Add stopChineseMic definition right before cnMicUI
stop_chinese_mic_fn = """    /* ================= ฟังก์ชันปิดไมค์แบบปลอดภัย ครอบคลุมทุกสภาวะ ================= */
    window.__cnActiveRecognizer = null;
    window.__cnSilenceTimer = null;

    function stopChineseMic() {
      if (window.__cnSilenceTimer) {
        clearTimeout(window.__cnSilenceTimer);
        window.__cnSilenceTimer = null;
      }
      if (window.__cnActiveRecognizer) {
        try {
          window.__cnActiveRecognizer.abort();
        } catch(e) {}
        window.__cnActiveRecognizer = null;
      }
      isMicListening = false;
      cnMicUI('retry', '');
    }
"""

if 'function stopChineseMic' not in html:
    html = html.replace('function cnMicUI(state, message) {', stop_chinese_mic_fn + '\n    function cnMicUI(state, message) {', 1)
    print("Added stopChineseMic() function")

# 2. Update closeLesson() to call stopChineseMic()
old_close_lesson = """    function closeLesson() {
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();"""

new_close_lesson = """    function closeLesson() {
      stopChineseMic();
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();"""

if old_close_lesson in html:
    html = html.replace(old_close_lesson, new_close_lesson, 1)
    print("Updated closeLesson() to stop mic")

# 3. Update renderStep() to stop mic if leaving step 1
old_render_step = """    function renderStep() {
      updateStepPills();"""

new_render_step = """    function renderStep() {
      if (CURRENT_STEP !== 1) {
        stopChineseMic();
      }
      updateStepPills();"""

if old_render_step in html:
    html = html.replace(old_render_step, new_render_step, 1)
    print("Updated renderStep() to stop mic when moving steps")

# 4. Update handleManualPass() to call stopChineseMic()
old_manual_pass = """    function handleManualPass() {
      if (CURRENT_STEP < 4) {"""

new_manual_pass = """    function handleManualPass() {
      stopChineseMic();
      if (CURRENT_STEP < 4) {"""

if old_manual_pass in html:
    html = html.replace(old_manual_pass, new_manual_pass, 1)
    print("Updated handleManualPass() to stop mic")

# 5. Update renderSpeakStep() for manual button toggle
old_btn_click = """      const micBtn0 = document.getElementById('btnChineseMic');
      if (micBtn0) {
        micBtn0.onclick = () => {
          if (window.__cnAutoMic === true) { return; }   /* กัน click() จาก auto */
          window.__micManual = (window.__micManual || 0) + 1;
          cnStopQueue();
          triggerChineseMic(micBtn0.getAttribute('data-target'));
        };
      }"""

new_btn_click = """      const micBtn0 = document.getElementById('btnChineseMic');
      if (micBtn0) {
        micBtn0.onclick = () => {
          if (window.__cnAutoMic === true) { return; }   /* กัน click() จาก auto */
          window.__micManual = (window.__micManual || 0) + 1;
          cnStopQueue();

          // Condition 3: แตะไมค์ซ้ำขณะฟังอยู่ ให้ปิดไมค์ทันที
          if (isMicListening && window.__cnActiveRecognizer) {
            stopChineseMic();
            const sa = document.getElementById('micStatusText');
            if (sa) {
              sa.className = 'text-xs font-bold text-slate-500 mt-2';
              sa.textContent = 'ปิดไมค์เรียบร้อยค่ะ — แตะไมค์อีกครั้งเมื่อพร้อมพูดนะคะ';
            }
            return;
          }

          triggerChineseMic(micBtn0.getAttribute('data-target'));
        };
      }"""

if old_btn_click in html:
    html = html.replace(old_btn_click, new_btn_click, 1)
    print("Updated micBtn0.onclick to toggle off when active")

# 6. Update triggerChineseMic implementation
old_trigger_fn = """    function triggerChineseMic(targetText) {
      const btn = document.getElementById('btnChineseMic');
      const st = document.getElementById('micStatusText');
      const fb = document.getElementById('stepFeedback');

      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRec) {
        st.textContent = 'เบราว์เซอร์นี้ไม่รองรับการฟังเสียง (ลอง Chrome / Safari รุ่นใหม่) หรือแตะปุ่มผ่านด้านล่างค่ะ';
        return;
      }
      /* ขอสิทธิ์ไมค์ก่อน — ถ้าถูกปฏิเสธ SpeechRecognition จะ start() แล้ว "เงียบ" ไม่แจ้งอะไร */
      const askMic = async () => {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return true;
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          stream.getTracks().forEach(t => t.stop());
          return true;
        } catch (e) {
          cnMicUI('retry', '');
          const sa = document.getElementById('micStatusText');
          if (sa) {
            sa.className = 'text-xs font-bold text-rose-600';
            sa.textContent = (e && e.name === 'NotAllowedError')
              ? 'ยังไม่ได้อนุญาตไมโครโฟน — กดไอคอน 🔒/🎙️ ข้างช่องที่อยู่ แล้วเลือก "อนุญาต" ค่ะ'
              : 'เปิดไมโครโฟนไม่สำเร็จ: ' + ((e && e.name) || 'unknown') + ' — ตรวจว่าอุปกรณ์มีไมค์และอนุญาตแล้วหรือยังค่ะ';
          }
          window.__cnLog = window.__cnLog || [];
          window.__cnLog.push({ key: 'mic', via: 'gum-fail:' + ((e && e.name) || 'unknown') });
          return false;
        }
      };

      try {
        const recognizer = new SpeechRec();
        recognizer.lang = 'zh-CN';
        recognizer.continuous = false;
        recognizer.interimResults = true;   /* ให้เห็นคำที่กำลังพูดทีละคำ */

        cnMicUI('listening', 'กำลังรับฟังเสียงภาษาจีน... 🎙️');

        /* กล่องคำพูดสด — เห็นข้อความโตขึ้นระหว่างพูด */
        const liveBox = () => document.getElementById('micLiveWords');
        const setLive = (text, final) => {
          const box = liveBox();
          if (!box) return;
          if (!text) { box.classList.add('hidden'); box.innerHTML = ''; return; }
          box.classList.remove('hidden');
          box.className = final
            ? 'mt-3 px-4 py-3 rounded-2xl bg-emerald-50 border-2 border-emerald-200 text-center'
            : 'mt-3 px-4 py-3 rounded-2xl bg-sky-50 border-2 border-sky-200 text-center';
          box.innerHTML = `
            <div class="text-[10px] font-black ${final ? 'text-emerald-700' : 'text-sky-700'} mb-1">
              ${final ? '✅ หนูพูดว่า' : '🎧 กำลังได้ยิน...'}
            </div>
            <div class="font-display font-black text-2xl text-slate-900 leading-tight">${text}</div>
          `;
        };

        /* แสดงระหว่างพูด (interim) */
        recognizer.onresult = (e) => {
          let interim = '';
          let finalText = '';
          for (let i = e.resultIndex; i < e.results.length; i++) {
            const r = e.results[i];
            if (r.isFinal) finalText += r[0].transcript;
            else interim += r[0].transcript;
          }
          if (interim) setLive(interim.trim(), false);
          if (!finalText) return;
          const heard = finalText.trim();
          setLive(heard, true);
          const st2 = document.getElementById('micStatusText');
          cnMicUI('idle', '');
          if (st2) {
            st2.className = 'text-xs font-bold text-slate-500 mt-2';
            st2.innerHTML = `เทียบกับคำเป้าหมาย: <b class="text-slate-800">${targetText}</b>`;
          }
          window.__cnLog = window.__cnLog || [];
          window.__cnLog.push({ key: 'mic', via: 'result:' + heard });
          // Clean comparison
          const cleanTarget = targetText.replace(/[^a-zA-Z0-9一-龥]/g, '').toLowerCase();
          const cleanHeard = heard.replace(/[^a-zA-Z0-9一-龥]/g, '').toLowerCase();

          if (cleanHeard === cleanTarget || cleanHeard.includes(cleanTarget) || cleanTarget.includes(cleanHeard)) {
            playTone('correct');
            TOTAL_STARS += 1;
            updateGlobalStars();
            fb.innerHTML = `🎉 ออกเสียงได้ยอดเยี่ยมมากค่ะ! ⭐⭐⭐`;
            speakMandarin('很好！发音很清楚！', 0.9, () => {
              setTimeout(() => {
                CURRENT_STEP = 2;
                renderStep();
              }, 450);
            });
          } else {
            playTone('wrong');
            fb.innerHTML = `ลองอ่านใหม่อีกครั้งนะคะ 🙂`;
            speakMandarin('再试一次', 0.85);
          }
        };

        recognizer.onerror = (err) => {
          const code = (err && err.error) || 'unknown';
          cnMicUI('retry', '');
          const stx = document.getElementById('micStatusText');
          const msg = {
            'not-allowed': 'ยังไม่ได้อนุญาตไมโครโฟน — กดไอคอน 🔒 ข้างช่องที่อยู่ แล้วอนุญาตค่ะ',
            'service-not-allowed': 'เบราว์เซอร์/ระบบบล็อกบริการฟังเสียง (ต้องใช้ https + Chrome/Safari)',
            'audio-capture': 'ไม่พบไมโครโฟนในเครื่องนี้ค่ะ',
            'no-speech': 'ไม่ได้ยินเสียง — แตะไมค์แล้วพูดดัง ๆ ใกล้ไมค์อีกครั้งนะคะ',
            'network': 'ต่อเซิร์ฟเวอร์ฟังเสียงไม่ได้ (ตรวจอินเทอร์เน็ต)'
          }[code] || ('ฟังเสียงไม่สำเร็จ (' + code + ')');
          if (stx) { stx.className = 'text-xs font-bold text-rose-600'; stx.textContent = msg; }
          window.__cnLog = window.__cnLog || [];
          window.__cnLog.push({ key: 'mic', via: 'error:' + code });

          /* ลองซ้ำอัตโนมัติ 1 ครั้ง สำหรับเคสที่รอบแรกถูกรบกวน
             (ไม่ลองซ้ำกับ not-allowed / audio-capture เพราะจะล้มเหมือนเดิม) */
          if (!triggerChineseMic.__retried && (code === 'network' || code === 'no-speech' || code === 'aborted')) {
            triggerChineseMic.__retried = true;
            setTimeout(() => { triggerChineseMic.__retried = false; if (window.__cnAutoOpenMic) window.__cnAutoOpenMic(); }, 900);
          }
        };

        /* ขอสิทธิ์ก่อน แล้วค่อยเริ่มฟังจริง */
        askMic().then((ok) => {
          if (!ok) return;
          try {
            recognizer.start();
            window.__cnLog = window.__cnLog || [];
            window.__cnLog.push({ key: 'mic', via: 'started' });
          }
          catch (e) {
            cnMicUI('retry', '');
            const sx = document.getElementById('micStatusText');
            if (sx) {
              sx.className = 'text-xs font-bold text-rose-600';
              sx.textContent = 'เริ่มฟังไม่สำเร็จ (' + ((e && e.name) || 'error') + ') — ระบบถอดเสียงอาจถูกบล็อก ลองใหม่หรือใช้ปุ่มผ่านขั้นด้านล่างค่ะ';
            }
            window.__cnLog = window.__cnLog || [];
            window.__cnLog.push({ key: 'mic', via: 'start-threw:' + ((e && e.name) || 'error') });
          }
        });
      } catch(e) {
        btn.className = "px-6 py-3.5 rounded-2xl bg-emerald-600 hover:bg-emerald-700 text-white font-display font-black text-sm shadow-lg shadow-emerald-600/30 transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
        btn.innerHTML = '<span>🎙️ แตะไมค์แล้วเริ่มพูด</span>';
      }
    }"""

new_trigger_fn = """    function triggerChineseMic(targetText) {
      const btn = document.getElementById('btnChineseMic');
      const st = document.getElementById('micStatusText');
      const fb = document.getElementById('stepFeedback');

      // ปิดไมค์เดิมก่อนเสมอ เพื่อไม่ให้มี Stream ค้าง
      stopChineseMic();

      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRec) {
        st.textContent = 'เบราว์เซอร์นี้ไม่รองรับการฟังเสียง (ลอง Chrome / Safari รุ่นใหม่) หรือแตะปุ่มผ่านด้านล่างค่ะ';
        return;
      }
      /* ขอสิทธิ์ไมค์ก่อน — ถ้าถูกปฏิเสธ SpeechRecognition จะ start() แล้ว "เงียบ" ไม่แจ้งอะไร */
      const askMic = async () => {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return true;
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          stream.getTracks().forEach(t => t.stop());
          return true;
        } catch (e) {
          stopChineseMic();
          const sa = document.getElementById('micStatusText');
          if (sa) {
            sa.className = 'text-xs font-bold text-rose-600';
            sa.textContent = (e && e.name === 'NotAllowedError')
              ? 'ยังไม่ได้อนุญาตไมโครโฟน — กดไอคอน 🔒/🎙️ ข้างช่องที่อยู่ แล้วเลือก "อนุญาต" ค่ะ'
              : 'เปิดไมโครโฟนไม่สำเร็จ: ' + ((e && e.name) || 'unknown') + ' — ตรวจว่าอุปกรณ์มีไมค์และอนุญาตแล้วหรือยังค่ะ';
          }
          window.__cnLog = window.__cnLog || [];
          window.__cnLog.push({ key: 'mic', via: 'gum-fail:' + ((e && e.name) || 'unknown') });
          return false;
        }
      };

      try {
        const recognizer = new SpeechRec();
        recognizer.lang = 'zh-CN';
        recognizer.continuous = false;
        recognizer.interimResults = true;   /* ให้เห็นคำที่กำลังพูดทีละคำ */

        window.__cnActiveRecognizer = recognizer;
        isMicListening = true;

        cnMicUI('listening', 'กำลังรับฟังเสียงภาษาจีน... 🎙️ (แตะไมค์อีกครั้งเพื่อหยุด)');

        /* เงื่อนไขที่ 2: Silence Timeout (6 วินาที) ถ้าไม่ได้ยินเสียง ให้ปิดไมค์อัตโนมัติ */
        if (window.__cnSilenceTimer) clearTimeout(window.__cnSilenceTimer);
        window.__cnSilenceTimer = setTimeout(() => {
          if (isMicListening) {
            stopChineseMic();
            const sa = document.getElementById('micStatusText');
            if (sa) {
              sa.className = 'text-xs font-bold text-slate-500 mt-2';
              sa.textContent = 'ยังไม่ได้ยินเสียง — แตะไมค์ลองใหม่อีกครั้งนะคะ 🙂';
            }
          }
        }, 6000);

        /* กล่องคำพูดสด — เห็นข้อความโตขึ้นระหว่างพูด */
        const liveBox = () => document.getElementById('micLiveWords');
        const setLive = (text, final) => {
          const box = liveBox();
          if (!box) return;
          if (!text) { box.classList.add('hidden'); box.innerHTML = ''; return; }
          box.classList.remove('hidden');
          box.className = final
            ? 'mt-3 px-4 py-3 rounded-2xl bg-emerald-50 border-2 border-emerald-200 text-center'
            : 'mt-3 px-4 py-3 rounded-2xl bg-sky-50 border-2 border-sky-200 text-center';
          box.innerHTML = `
            <div class="text-[10px] font-black ${final ? 'text-emerald-700' : 'text-sky-700'} mb-1">
              ${final ? '✅ หนูพูดว่า' : '🎧 กำลังได้ยิน...'}
            </div>
            <div class="font-display font-black text-2xl text-slate-900 leading-tight">${text}</div>
          `;
        };

        /* แสดงระหว่างพูด (interim) */
        recognizer.onresult = (e) => {
          let interim = '';
          let finalText = '';
          for (let i = e.resultIndex; i < e.results.length; i++) {
            const r = e.results[i];
            if (r.isFinal) finalText += r[0].transcript;
            else interim += r[0].transcript;
          }
          if (interim) setLive(interim.trim(), false);
          if (!finalText) return;
          const heard = finalText.trim();
          setLive(heard, true);

          // เงื่อนไขที่ 1: ประมวลผลเสร็จแล้ว ปิดไมค์ทันที!
          stopChineseMic();

          const st2 = document.getElementById('micStatusText');
          if (st2) {
            st2.className = 'text-xs font-bold text-slate-500 mt-2';
            st2.innerHTML = `เทียบกับคำเป้าหมาย: <b class="text-slate-800">${targetText}</b>`;
          }
          window.__cnLog = window.__cnLog || [];
          window.__cnLog.push({ key: 'mic', via: 'result:' + heard });
          // Clean comparison
          const cleanTarget = targetText.replace(/[^a-zA-Z0-9一-龥]/g, '').toLowerCase();
          const cleanHeard = heard.replace(/[^a-zA-Z0-9一-龥]/g, '').toLowerCase();

          if (cleanHeard === cleanTarget || cleanHeard.includes(cleanTarget) || cleanTarget.includes(cleanHeard)) {
            playTone('correct');
            TOTAL_STARS += 1;
            updateGlobalStars();
            fb.innerHTML = `🎉 ออกเสียงได้ยอดเยี่ยมมากค่ะ! ⭐⭐⭐`;
            speakMandarin('很好！发音很清楚！', 0.9, () => {
              setTimeout(() => {
                CURRENT_STEP = 2;
                renderStep();
              }, 450);
            });
          } else {
            playTone('wrong');
            fb.innerHTML = `ลองอ่านใหม่อีกครั้งนะคะ 🙂`;
            speakMandarin('再试一次', 0.85);
          }
        };

        recognizer.onerror = (err) => {
          const code = (err && err.error) || 'unknown';
          // ปิดไมค์ทันทีเมื่อเกิด error (ไม่เปิดวนซ้ำ)
          stopChineseMic();

          const stx = document.getElementById('micStatusText');
          const msg = {
            'not-allowed': 'ยังไม่ได้อนุญาตไมโครโฟน — กดไอคอน 🔒 ข้างช่องที่อยู่ แล้วอนุญาตค่ะ',
            'service-not-allowed': 'เบราว์เซอร์/ระบบบล็อกบริการฟังเสียง (ต้องใช้ https + Chrome/Safari)',
            'audio-capture': 'ไม่พบไมโครโฟนในเครื่องนี้ค่ะ',
            'no-speech': 'ไม่ได้ยินเสียง — แตะไมค์แล้วพูดดัง ๆ ใกล้ไมค์อีกครั้งนะคะ',
            'network': 'ต่อเซิร์ฟเวอร์ฟังเสียงไม่ได้ (ตรวจอินเทอร์เน็ต)'
          }[code] || ('ฟังเสียงไม่สำเร็จ (' + code + ')');
          if (stx) { stx.className = 'text-xs font-bold text-slate-500 mt-2'; stx.textContent = msg; }
          window.__cnLog = window.__cnLog || [];
          window.__cnLog.push({ key: 'mic', via: 'error:' + code });
        };

        recognizer.onend = () => {
          stopChineseMic();
        };

        /* ขอสิทธิ์ก่อน แล้วค่อยเริ่มฟังจริง */
        askMic().then((ok) => {
          if (!ok) return;
          try {
            recognizer.start();
            window.__cnLog = window.__cnLog || [];
            window.__cnLog.push({ key: 'mic', via: 'started' });
          }
          catch (e) {
            stopChineseMic();
            const sx = document.getElementById('micStatusText');
            if (sx) {
              sx.className = 'text-xs font-bold text-rose-600';
              sx.textContent = 'เริ่มฟังไม่สำเร็จ (' + ((e && e.name) || 'error') + ') — ระบบถอดเสียงอาจถูกบล็อก ลองใหม่หรือใช้ปุ่มผ่านขั้นด้านล่างค่ะ';
            }
            window.__cnLog = window.__cnLog || [];
            window.__cnLog.push({ key: 'mic', via: 'start-threw:' + ((e && e.name) || 'error') });
          }
        });
      } catch(e) {
        stopChineseMic();
      }
    }"""

if old_trigger_fn in html:
    html = html.replace(old_trigger_fn, new_trigger_fn, 1)
    print("Updated triggerChineseMic with safe lifecycle and stopping")
else:
    print("Could not match old_trigger_fn directly!")

# Save to /tmp/chinese.html
with sftp.open('/tmp/chinese.html', 'w') as f:
    f.write(html.encode('utf-8'))

sftp.close()

def run_sudo_cmd(cmd):
    full_cmd = f"echo 'OpenHands@ERP2026' | sudo -S bash -c \"{cmd}\""
    stdin, stdout, stderr = ssh.exec_command(full_cmd)
    return stdout.read().decode('utf-8'), stderr.read().decode('utf-8')

print("Deploying updated chinese.html with sudo...")
run_sudo_cmd("cp /tmp/chinese.html /var/www/kidobits/chinese.html")
run_sudo_cmd("chown www-data:www-data /var/www/kidobits/chinese.html")

print("Checking git diff on chinese.html...")
stdin, stdout, stderr = ssh.exec_command("cd /var/www/kidobits && git diff chinese.html")
print(stdout.read().decode('utf-8'))

print("Committing and pushing...")
msg = "fix(chinese): implement stopChineseMic across all 5 closing conditions and prevent mic hanging"
cmd = f"cd /var/www/kidobits && git add chinese.html && git commit -m \\\"{msg}\\\" && git push origin main"
out, err = run_sudo_cmd(cmd)
print("OUT:\n", out)
print("ERR:\n", err)

ssh.close()
print("All finished!")
