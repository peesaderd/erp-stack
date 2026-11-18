import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='ignore'), stderr.read().decode('utf-8', errors='ignore')

script = r'''
import re

fix_block = """    let currentRecognizer = null;
    let isChineseMicActive = false;

    function stopChineseMic() {
      if (currentRecognizer) {
        try { currentRecognizer.abort(); } catch(e) {}
        currentRecognizer = null;
      }
      isChineseMicActive = false;
      isMicListening = false;
    }

    function skipSpeakStep() {
      stopChineseMic();
      playTone('correct');
      TOTAL_STARS += 1;
      updateGlobalStars();
      const fb = document.getElementById('stepFeedback');
      if (fb) fb.innerHTML = 'ข้ามไปขั้นถัดไป ✨';
      setTimeout(() => {
        CURRENT_STEP = 2;
        renderStep();
      }, 350);
    }

    function triggerChineseMic(targetText) {
      if (isChineseMicActive) {
        console.log('Chinese mic already active, skipping duplicate trigger');
        return;
      }
      if (currentRecognizer) {
        try { currentRecognizer.abort(); } catch(e) {}
        currentRecognizer = null;
      }

      const btn = document.getElementById('btnChineseMic');
      const st = document.getElementById('micStatusText');
      const fb = document.getElementById('stepFeedback');

      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRec) {
        cnMicUI('retry', 'เบราว์เซอร์นี้ไม่รองรับการฟังเสียง — แตะปุ่มข้ามด้านล่างได้เลยค่ะ');
        return;
      }

      try {
        const recognizer = new SpeechRec();
        currentRecognizer = recognizer;
        recognizer.lang = 'zh-CN';
        recognizer.continuous = false;
        recognizer.interimResults = true;

        cnMicUI('listening', 'กำลังฟัง... พูดภาษาจีนได้เลยค่ะ 🎙️');

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

        recognizer.onstart = () => {
          isChineseMicActive = true;
          isMicListening = true;
          cnMicUI('listening', 'กำลังฟัง... พูดภาษาจีนได้เลยค่ะ 🔴');
        };

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
          isChineseMicActive = false;
          isMicListening = false;
          currentRecognizer = null;

          const st2 = document.getElementById('micStatusText');
          cnMicUI('idle', '');
          if (st2) {
            st2.className = 'text-xs font-bold text-slate-500 mt-2';
            st2.innerHTML = `เทียบกับคำเป้าหมาย: <b class="text-slate-800">${targetText}</b>`;
          }

          const cleanTarget = targetText.replace(/[^a-zA-Z0-9一-龥]/g, '').toLowerCase();
          const cleanHeard = heard.replace(/[^a-zA-Z0-9一-龥]/g, '').toLowerCase();

          if (cleanHeard === cleanTarget || cleanHeard.includes(cleanTarget) || cleanTarget.includes(cleanHeard)) {
            playTone('correct');
            TOTAL_STARS += 1;
            updateGlobalStars();
            fb.innerHTML = `🎉 ออกเสียงได้ยอดเยี่ยมมากค่ะ! ⭐⭐⭐`;
            cnMicUI('wait', 'ยอดเยี่ยมมาก! กำลังไปขั้นถัดไป...');
            speakMandarin('很好！发音很清楚！', 0.9, () => {
              setTimeout(() => {
                CURRENT_STEP = 2;
                renderStep();
              }, 450);
            });
          } else {
            playTone('wrong');
            fb.innerHTML = `ลองอ่านใหม่อีกครั้งนะคะ 🙂`;
            cnMicUI('retry', 'แตะไมค์เพื่อลองพูดอีกครั้ง 🎙️');
            speakMandarin('再试一次', 0.85);
          }
        };

        recognizer.onend = () => {
          isChineseMicActive = false;
          isMicListening = false;
          if (currentRecognizer === recognizer) {
            currentRecognizer = null;
            cnMicUI('retry', 'แตะไมค์เพื่อพูดอีกครั้ง 🎙️');
          }
        };

        recognizer.onerror = (err) => {
          isChineseMicActive = false;
          isMicListening = false;
          currentRecognizer = null;
          const code = (err && err.error) || 'unknown';
          cnMicUI('retry', '');
          const stx = document.getElementById('micStatusText');
          const msg = {
            'not-allowed': 'ยังไม่ได้อนุญาตไมโครโฟน — กดไอคอน 🔒 ข้างช่องที่อยู่ แล้วอนุญาตค่ะ',
            'service-not-allowed': 'ระบบยังไม่พร้อมรับเสียง — แตะไมค์ลองใหม่หรือแตะปุ่มข้ามค่ะ',
            'audio-capture': 'ไม่พบไมโครโฟนในเครื่องนี้ค่ะ',
            'no-speech': 'ไม่ได้ยินเสียง — แตะไมค์แล้วพูดดัง ๆ ใกล้ไมค์อีกครั้งนะคะ',
            'aborted': 'หยุดการฟังแล้ว — แตะไมค์เพื่อพูดใหม่ค่ะ',
            'network': 'ต่อเซิร์ฟเวอร์ฟังเสียงไม่ได้ (ตรวจอินเทอร์เน็ต)'
          }[code] || ('ฟังเสียงไม่สำเร็จ (' + code + ')');
          if (stx) { stx.className = 'text-xs font-bold text-rose-600'; stx.textContent = msg; }
        };

        recognizer.start();
      } catch (err) {
        isChineseMicActive = false;
        isMicListening = false;
        currentRecognizer = null;
        cnMicUI('retry', 'เริ่มฟังไม่สำเร็จ — แตะไมค์เพื่อลองใหม่ค่ะ');
      }
    }"""

for file_path in ['/var/www/kidobits/chinese.html', '/var/www/kidobits/chinese_preview.html']:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            c = f.read()

        # Find triggerChineseMic function block
        start_m = 'function triggerChineseMic(targetText) {'
        end_m = '// ---------------- STEP 3: 📖 อ่าน (READING) ----------------'

        s_idx = c.find(start_m)
        e_idx = c.find(end_m)

        if s_idx != -1 and e_idx != -1:
            c = c[:s_idx] + fix_block + "\n\n    " + c[e_idx:]
            print(f'Replaced triggerChineseMic in {file_path}')
        else:
            print(f'Markers not found in {file_path}: {s_idx}, {e_idx}')

        # Add skip button in renderSpeakStep
        skip_btn = """            <div id="micLiveWords" class="hidden max-w-sm mx-auto"></div>
            <button type="button" onclick="skipSpeakStep()" class="mt-3 text-xs font-bold text-slate-400 hover:text-orange-600 underline cursor-pointer transition block mx-auto">
              ข้ามขั้นตอนนี้ (ไปขั้นที่ 3) ›
            </button>"""

        if 'skipSpeakStep()' not in c and '<div id="micLiveWords" class="hidden max-w-sm mx-auto"></div>' in c:
            c = c.replace('<div id="micLiveWords" class="hidden max-w-sm mx-auto"></div>', skip_btn)
            print(f'Added skipSpeakStep button in {file_path}')

        # Add stopChineseMic in closeLesson
        if 'closeLesson()' in c and 'stopChineseMic()' not in c:
            c = c.replace('function closeLesson() {', 'function closeLesson() {\n      stopChineseMic();')
            print(f'Added stopChineseMic in closeLesson in {file_path}')

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(c)

    except Exception as ex:
        print(f'Error processing {file_path}: {ex}')

print('Chinese mic fix script completed!')
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/fix_chinese_mic.py', 'w') as f:
    f.write(script)
sftp.close()

out, err = run("sudo python3 /tmp/fix_chinese_mic.py")
print("=== FIX CHINESE MIC OUTPUT ===")
print(out, err)

ssh.close()
