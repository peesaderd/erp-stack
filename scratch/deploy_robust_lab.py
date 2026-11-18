import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)

update_script = r'''# -*- coding: utf-8 -*-
with open('/var/www/kidobits/chinese_lab.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace the entire mic handling block in chinese_lab.html
old_mic_pattern_start = '/* ================= ฟังก์ชันปิดไมค์แบบปลอดภัย ครอบคลุมทุกสภาวะ ================= */'
old_mic_pattern_end = '/* ---------------- STEP 3: 📖 อ่าน (READING) ---------------- */'

idx_start = html.find(old_mic_pattern_start)
idx_end = html.find(old_mic_pattern_end)

if idx_start == -1 or idx_end == -1:
    print(f"ERROR: Could not find markers: start={idx_start}, end={idx_end}")
    exit(1)

new_robust_mic_code = r'''/* ================= 🧪 PHONEME LAB: ROBUST LOCAL SERVER STT ENGINE ================= */
    let __cnMicStream = null;
    let __cnMediaRecorder = null;
    let __cnAudioChunks = [];
    let __cnRecTimer = null;
    let __cnMaxTimer = null;
    window.__cnActiveRecognizer = null;
    window.__cnSilenceTimer = null;

    async function getChineseAudioStream() {
      if (__cnMicStream && __cnMicStream.active) return __cnMicStream;
      __cnMicStream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
      return __cnMicStream;
    }

    function stopChineseMic(shouldProcess = false) {
      if (__cnRecTimer) { clearInterval(__cnRecTimer); __cnRecTimer = null; }
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
    }

    function cnMicUI(state, message) {
      const btn = document.getElementById('btnChineseMic');
      const st  = document.getElementById('micStatusText');
      if (btn) {
        if (state === 'wait') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-slate-400 text-white font-display font-black text-sm shadow-lg shadow-slate-400/30 transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>⏳ รอครูพูดจบ แล้วแตะไมค์พูดนะคะ...</span>';
        } else if (state === 'ready') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white font-display font-black text-base shadow-xl ring-4 ring-emerald-300 animate-pulse transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🎙️ ตาหนูพูดแล้วค่ะ! (แตะเพื่อพูด)</span>';
        } else if (state === 'listening') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-rose-600 text-white font-display font-black text-base shadow-xl ring-4 ring-rose-300 animate-pulse transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-white animate-ping"></span>🔴 กำลังฟังเสียง... (แตะเมื่อพูดจบ)</span>';
        } else if (state === 'thinking') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-indigo-600 text-white font-display font-black text-sm shadow-lg transition flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🎧 ครูเป่าเปากำลังตรวจเสียง...</span>';
        } else if (state === 'retry') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white font-display font-black text-sm shadow-lg shadow-amber-500/30 transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🔁 แตะไมค์เพื่อลองพูดอีกครั้ง</span>';
        } else {
          btn.className = "px-6 py-3.5 rounded-2xl bg-emerald-600 hover:bg-emerald-700 text-white font-display font-black text-sm shadow-lg transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🎙️ แตะไมค์เพื่อพูด</span>';
        }
      }
      if (st && message) {
        st.className = 'text-xs font-bold text-slate-500 mt-2';
        st.textContent = message;
      }
    }

    /* ครูพูดนำเฉพาะขั้น */
    let cnTutorDone = {};
    let cnTutorToken = null;
    function cnTutorStep() {
      if (!CURRENT_LESSON) return;
      const key = CURRENT_LESSON.id + '|' + CURRENT_STEP;
      if (cnTutorToken && cnTutorToken.key === key && (Date.now() - cnTutorToken.at) < 1500) return;
      if (cnTutorDone[key]) return;
      cnTutorDone[key] = true;
      cnTutorToken = { key, at: Date.now() };
      const L = CURRENT_LESSON;
      if (CURRENT_STEP === 0) {
        cnPlayKey(L.id + '_listen', L.listen.audioWord);
      } else if (CURRENT_STEP === 1) {
        /* ครูอ่านนำ -> เว้น -> บอกตาหนู -> เว้น -> แสดงปุ่มพร้อมพูด (แตะปุ๊บพูดได้ทันที) */
        cnQueue([
          { key: L.id + '_speak', text: L.speak.target, gapAfter: CN_GAP_WORD },
          { key: L.id + '_turn',  text: '现在轮到你了',  gapAfter: CN_GAP_TURN,
            then: () => {
              cnMicUI('ready', 'แตะปุ่มไมค์สีเขียวแล้วพูดคำว่า "' + L.speak.target + '" ได้เลยค่ะ');
            }
          }
        ]);
        if (window.__cnTurnAuto) window.__cnTurnAuto[L.id] = false;
      } else if (CURRENT_STEP === 2) {
        cnPlayKey(L.id + '_read', L.read.sentence);
      } else if (CURRENT_STEP === 3 && L.write.char) {
        cnPlayKey(L.id + '_write', L.write.char);
      }
    }

    function triggerChineseMic(targetText) {
      if (isMicListening) {
        stopChineseMic(true);
        return;
      }

      stopChineseMic(false);

      if (typeof MediaRecorder !== 'undefined' && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        startServerSTTRecording(targetText);
      } else {
        startFallbackWebSpeech(targetText);
      }
    }

    async function startServerSTTRecording(targetText) {
      const fb = document.getElementById('stepFeedback');
      const st = document.getElementById('micStatusText');
      const liveBox = document.getElementById('micLiveWords');

      try {
        const stream = await getChineseAudioStream();
        __cnAudioChunks = [];

        let mime = '';
        const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
        for (const c of candidates) {
          try { if (MediaRecorder.isTypeSupported(c)) { mime = c; break; } } catch(e) {}
        }

        const rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
        __cnMediaRecorder = rec;
        isMicListening = true;

        cnMicUI('listening', '🎙️ กำลังฟังเสียง... พูดดัง ๆ ใกล้ไมค์เลยค่ะ (แตะปุ่มอีกครั้งเมื่อพูดเสร็จ)');

        if (liveBox) {
          liveBox.classList.remove('hidden');
          liveBox.className = 'mt-3 px-4 py-3 rounded-2xl bg-amber-50 border-2 border-amber-200 text-center animate-pulse';
          liveBox.innerHTML = `
            <div class="text-[10px] font-black text-amber-700 mb-1">🎧 ห้องทดลองกำลังบันทึกเสียง</div>
            <div class="font-display font-black text-xl text-slate-900 leading-tight">กำลังฟัง... พูดคำว่า "${targetText}" ได้เลยจ้ะ</div>
          `;
        }

        rec.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) __cnAudioChunks.push(e.data);
        };

        rec.onstop = async () => {
          isMicListening = false;
          cnMicUI('thinking', 'ครูเป่าเปากำลังตรวจการออกเสียง... 🎧');

          const blob = new Blob(__cnAudioChunks, { type: mime || 'audio/webm' });
          if (blob.size < 600) {
            cnMicUI('retry', 'ยังไม่ได้ยินเสียงชัดเจน — แตะไมค์ลองใหม่อีกครั้งนะคะ 🙂');
            return;
          }

          const fd = new FormData();
          fd.append('audio', blob, 'child_chinese.webm');
          fd.append('lang', 'zh');
          fd.append('hint', targetText);

          try {
            const ctrl = new AbortController();
            const to = setTimeout(() => ctrl.abort(), 12000);
            const resp = await fetch('/kidobits/stt', { method: 'POST', body: fd, signal: ctrl.signal });
            clearTimeout(to);

            const data = await resp.json();
            const heard = (data && data.text) ? data.text.trim() : '';

            handlePhonemeEvaluationResult(targetText, heard);
          } catch (err) {
            console.error('Server STT failed:', err);
            handlePhonemeEvaluationResult(targetText, '', 'เกิดข้อผิดพลาดในการเชื่อมต่อ กรุณาลองใหม่ค่ะ');
          }
        };

        rec.start();

        /* อัดเสียงอัตโนมัติสูงสุด 3.2 วินาที (คำเดี่ยว/วลีสั้นของเด็ก) */
        __cnMaxTimer = setTimeout(() => {
          if (isMicListening && __cnMediaRecorder && __cnMediaRecorder.state === 'recording') {
            stopChineseMic(true);
          }
        }, 3200);

      } catch (err) {
        console.warn('getUserMedia failed, falling back to WebSpeech:', err);
        startFallbackWebSpeech(targetText);
      }
    }

    function handlePhonemeEvaluationResult(targetText, heard, customError = null) {
      const fb = document.getElementById('stepFeedback');
      const liveBox = document.getElementById('micLiveWords');
      window.__cnLabAttempts = (window.__cnLabAttempts || 0) + 1;

      if (customError) {
        cnMicUI('retry', customError);
        return;
      }

      const targetHintPinyin = (CURRENT_LESSON && CURRENT_LESSON.speak && CURRENT_LESSON.speak.pinyin) || '';
      const evalRes = evaluatePhonemeMatch(targetText, heard, targetHintPinyin);

      if (liveBox) {
        liveBox.classList.remove('hidden');
        liveBox.className = evalRes.isPass
          ? 'mt-3 px-4 py-3 rounded-2xl bg-emerald-50 border-2 border-emerald-200 text-center animate-pop'
          : 'mt-3 px-4 py-3 rounded-2xl bg-rose-50 border-2 border-rose-200 text-center';
        liveBox.innerHTML = `
          <div class="text-[10px] font-black ${evalRes.isPass ? 'text-emerald-700' : 'text-rose-700'} mb-1">
            ${evalRes.isPass ? '✅ ออกเสียงตรงตามเกณฑ์' : '❌ ที่ได้ยินยังไม่ตรง'}
          </div>
          <div class="font-display font-black text-2xl text-slate-900 leading-tight">"${heard || '(เงียบ)'}"</div>
          <div class="text-[11px] text-slate-500 mt-1">พินอินที่ได้ยิน: <b>${evalRes.heardPinyin || '-'}</b> | เป้าหมาย: <b>${evalRes.targetPinyin || '-'}</b></div>
        `;
      }

      if (evalRes.isPass) {
        playTone('correct');
        TOTAL_STARS += 1;
        updateGlobalStars();
        window.__cnLabAttempts = 0;
        cnMicUI('ready', 'ยอดเยี่ยมมากค่ะ! 🎉');

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
      } else {
        playTone('wrong');
        cnMicUI('retry', 'ลองใหม่อีกครั้งนะคะ 🙂');

        fb.innerHTML = `
          <div class="p-3 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 text-center">
            <div class="text-sm font-black text-rose-700">เสียงยังไม่ตรง ลองฟังครูแล้วพูดใหม่อีกครั้งนะคะ 🙂</div>
            ${window.__cnLabAttempts >= 2 ? `
              <div class="mt-2.5 pt-2 border-t border-rose-200">
                <button onclick="playTone('correct'); TOTAL_STARS += 1; updateGlobalStars(); CURRENT_STEP = 2; renderStep();" class="px-4 py-2 bg-gradient-to-r from-amber-400 to-orange-400 hover:from-amber-500 hover:to-orange-500 text-white rounded-full text-xs font-black shadow-md transition active:scale-95 flex items-center justify-center gap-1 mx-auto cursor-pointer">
                  <span>⭐ คุณครูให้ผ่าน (ยอดเยี่ยมมากค่ะ แตะเพื่อไปต่อ) ➔</span>
                </button>
              </div>
            ` : ''}
          </div>
        `;
        speakMandarin('再试一次', 0.85);
      }
    }

    function startFallbackWebSpeech(targetText) {
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRec) {
        cnMicUI('retry', 'อุปกรณ์นี้ไม่รองรับไมค์ — แตะปุ่มผ่านด้านล่างเพื่อไปต่อได้ค่ะ');
        return;
      }

      try {
        const recognizer = new SpeechRec();
        recognizer.lang = 'zh-CN';
        recognizer.continuous = false;
        recognizer.interimResults = false;

        window.__cnActiveRecognizer = recognizer;
        isMicListening = true;
        cnMicUI('listening', 'กำลังฟังเสียงภาษาจีน... 🎙️ (พูดได้เลยค่ะ)');

        recognizer.onresult = (e) => {
          stopChineseMic(false);
          const heard = (e.results[0] && e.results[0][0] && e.results[0][0].transcript) || '';
          handlePhonemeEvaluationResult(targetText, heard);
        };

        recognizer.onerror = (err) => {
          stopChineseMic(false);
          const code = (err && err.error) || 'unknown';
          const msg = (code === 'network')
            ? 'สัญญาณอินเทอร์เน็ตขาดช่วง แตะไมค์อีกครั้งนะคะ'
            : (code === 'no-speech')
            ? 'ยังไม่ได้ยินเสียง — แตะไมค์แล้วพูดดัง ๆ ใกล้ไมค์อีกครั้งนะคะ'
            : 'เกิดข้อผิดพลาดในการฟัง (' + code + ')';
          cnMicUI('retry', msg);
        };

        recognizer.onend = () => {
          if (isMicListening) stopChineseMic(false);
        };

        recognizer.start();
      } catch (e) {
        cnMicUI('retry', 'เปิดไมโครโฟนไม่สำเร็จ แตะปุ่มผ่านเพื่อไปต่อได้ค่ะ');
      }
    }

    // ---------------- STEP 2: 🗣️ พูด (SPEAKING) ----------------
    function renderSpeakStep(stage) {
      const data = CURRENT_LESSON.speak;
      let h = `
        <div class="text-center space-y-4">
          <div class="inline-block px-3 py-1 rounded-full bg-emerald-100 text-emerald-900 text-xs font-black">
            🗣️ ขั้นที่ 2 · ฝึกทักษะการพูด (Phoneme Lab + Server STT)
          </div>
          <p class="text-sm font-bold text-slate-700">${data.prompt}</p>

          <!-- Target Card -->
          <div class="p-6 rounded-3xl bg-white border-2 border-emerald-200 text-center shadow-sm max-w-sm mx-auto">
            <div class="text-xs font-bold text-emerald-600 mb-1">${data.pinyin}</div>
            <div class="font-display font-black text-3xl sm:text-4xl text-slate-900 leading-tight mb-2">${data.target}</div>
            <div class="text-xs text-slate-500 font-semibold mb-3">"${data.th}"</div>
            <button onclick="cnReplayCurrent()" class="px-3.5 py-1.5 rounded-full bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-xs font-bold border border-emerald-200 inline-flex items-center gap-1 transition">
              <span>🔊 ฟังครูอ่านนำ</span>
            </button>
          </div>

          <!-- Mic Button -->
          <div class="pt-2">
            <button id="btnChineseMic" onclick="triggerChineseMic('${data.target.replace(/'/g, "\\'")}')" class="px-6 py-3.5 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white font-display font-black text-base shadow-xl ring-4 ring-emerald-300 animate-pulse transition cursor-pointer flex items-center justify-center gap-2 mx-auto">
              <span>🎙️ แตะไมค์เพื่อพูด</span>
            </button>
            <div id="micStatusText" class="text-xs text-slate-500 font-bold mt-2">
              แตะไมค์แล้วอ่านออกเสียงคำว่า "${data.target}" ตามครูได้เลยค่ะ
            </div>
            <div id="micLiveWords" class="hidden max-w-sm mx-auto"></div>
          </div>

          <div id="stepFeedback" class="min-h-12 text-xs font-bold text-emerald-600 flex items-center justify-center"></div>
        </div>
      `;
      stage.innerHTML = h;
    }
'''

html = html[:idx_start] + new_robust_mic_code + '\n    ' + html[idx_end:]

with open('/var/www/kidobits/chinese_lab.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("SUCCESS: /var/www/kidobits/chinese_lab.html upgraded with robust server-side STT & Phoneme Lab!")
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/update_lab_robust.py', 'w') as f:
    f.write(update_script.encode('utf-8'))
sftp.close()

cmd = 'python3 /tmp/update_lab_robust.py'
stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
ssh.close()
