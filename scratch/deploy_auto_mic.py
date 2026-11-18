# -*- coding: utf-8 -*-
import shutil

# 1. Read base clean chinese.html
with open('/var/www/kidobits/chinese.html', 'r', encoding='utf-8') as f:
    orig_html = f.read()

# Backup
with open('/var/www/kidobits/chinese.html.bak', 'w', encoding='utf-8') as f:
    f.write(orig_html)

# Define Section A replacement (Auto Mic Controller)
secA_start_marker = '/* ================= ฟังก์ชันปิดไมค์แบบปลอดภัย ครอบคลุมทุกสภาวะ ================= */'
secA_end_marker = '    function cnPlayOption(word)'

idxA_start = orig_html.find(secA_start_marker)
idxA_end = orig_html.find(secA_end_marker)

if idxA_start == -1 or idxA_end == -1:
    print(f"ERROR: Section A markers not found: start={idxA_start}, end={idxA_end}")
    exit(1)

secA_replacement = """/* ================= PHONEME LAB: AUDIO & AUTO MIC CONTROLLER ================= */
    let __cnMicStream = null;
    let __cnMediaRecorder = null;
    let __cnAudioChunks = [];
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

    // Pre-warm audio on user touch/click
    document.addEventListener('pointerdown', () => {
      if (!__cnMicStream && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        getChineseAudioStream().catch(() => {});
      }
    }, { once: true });

    function stopChineseMic(shouldProcess = false) {
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
          btn.innerHTML = '<span>⏳ รอครูพูดจบ แล้วไมค์จะเปิดเองอัตโนมัติ...</span>';
        } else if (state === 'listening') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-rose-600 text-white font-display font-black text-base shadow-xl ring-4 ring-rose-300 animate-pulse transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span class="flex items-center gap-2"><span class="w-3 h-3 rounded-full bg-white animate-ping"></span>🔴 ไมค์เปิดแล้ว พูดได้เลยค่ะ... (แตะเมื่อพูดจบ)</span>';
        } else if (state === 'thinking') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-indigo-600 text-white font-display font-black text-sm shadow-lg transition flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🎧 ครูเป่าเปากำลังตรวจเสียง...</span>';
        } else if (state === 'retry') {
          btn.className = "px-6 py-3.5 rounded-2xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white font-display font-black text-sm shadow-lg shadow-amber-500/30 transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🔁 แตะไมค์เพื่อลองพูดอีกครั้ง</span>';
        } else {
          btn.className = "px-6 py-3.5 rounded-2xl bg-emerald-600 hover:bg-emerald-700 text-white font-display font-black text-sm shadow-lg transition cursor-pointer flex items-center justify-center gap-2 mx-auto";
          btn.innerHTML = '<span>🎙️ ไมค์พร้อมรับฟัง</span>';
        }
      }
      if (st && message) {
        st.className = 'text-xs font-bold text-slate-500 mt-2';
        st.textContent = message;
      }
    }

    /* AUTO MIC OPENER */
    window.__cnAutoOpenMic = function () {
      if (!CURRENT_LESSON || CURRENT_STEP !== 1) return;
      const target = CURRENT_LESSON.speak.target;
      triggerChineseMic(target);
    };

    /* ครูพูดนำเฉพาะขั้น -> ตามด้วย AUTO MIC */
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
        /* ครูอ่านนำ -> เว้น -> บอกตาหนู -> เว้น -> เปิดไมค์อัตโนมัติ (AUTO MIC) */
        cnMicUI('wait', 'ไม่ต้องกดอะไรนะคะ — ไมค์จะเปิดอัตโนมัติเมื่อครูพูดจบ');
        cnQueue([
          { key: L.id + '_speak', text: L.speak.target, gapAfter: CN_GAP_WORD },
          { key: L.id + '_turn',  text: '现在轮到你了',  gapAfter: CN_GAP_TURN,
            then: () => {
              window.__cnAutoOpenMic();
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

"""

# Define Section B replacement (Auto Mic & Phoneme Lab)
secB_start_marker = '// ---------------- STEP 2: 🗣️ พูด (SPEAKING) ----------------'
secB_end_marker = '// ---------------- STEP 3: 📖 อ่าน (READING) ----------------'

idxB_start = orig_html.find(secB_start_marker)
idxB_end = orig_html.find(secB_end_marker)

if idxB_start == -1 or idxB_end == -1:
    print(f"ERROR: Section B markers not found: start={idxB_start}, end={idxB_end}")
    exit(1)

secB_replacement = """// ---------------- STEP 2: 🗣️ พูด (SPEAKING - AUTO MIC & PHONEME LAB) ----------------
    const HANZI_PINYIN_MAP = {
      '你': 'ni', '好': 'hao', '您': 'nin', '泥': 'ni', '拟': 'ni', '呢': 'ne', '号': 'hao', '嚎': 'hao',
      '我': 'wo', '要': 'yao', '握': 'wo', '窝': 'wo', '药': 'yao', '咬': 'yao', '耀': 'yao',
      '红': 'hong', '色': 'se', '洪': 'hong', '宏': 'hong', '涩': 'se',
      '叫': 'jiao', '小': 'xiao', '明': 'ming', '名': 'ming', '鸣': 'ming',
      '五': 'wu', '岁': 'sui', '午': 'wu', '武': 'wu', '碎': 'sui',
      '妈': 'ma', '麻': 'ma', '马': 'ma', '骂': 'ma', '吗': 'ma', '嘛': 'ma',
      '爸': 'ba', '八': 'ba', '把': 'ba', '坝': 'ba', '拔': 'ba', '粑': 'ba',
      '书': 'shu', '在': 'zai', '桌': 'zhuo', '子': 'zi', '上': 'shang', '下': 'xia', '里': 'li',
      '今': 'jin', '天': 'tian', '星': 'xing', '期': 'qi', '三': 'san', '一': 'yi', '二': 'er', '四': 'si',
      '气': 'qi', '非': 'fei', '常': 'chang', '热': 're', '冷': 'leng',
      '哥': 'ge', '比': 'bi', '大': 'da', '两': 'liang', '姐': 'jie', '弟': 'di', '妹': 'mei',
      '请': 'qing', '关': 'guan', '开': 'kai', '作': 'zuo', '业': 'ye', '交': 'jiao', '给': 'gei',
      '苹': 'ping', '果': 'guo', '香': 'xiang', '蕉': 'jiao', '西': 'xi', '瓜': 'gua',
      '猫': 'mao', '狗': 'gou', '鳥': 'niao', '鸟': 'niao'
    };

    function stripTone(str) {
      if (!str) return '';
      return str.normalize('NFD')
        .replace(/[\\u0300-\\u036f]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '');
    }

    function hanziToPinyin(text) {
      if (!text) return '';
      let out = '';
      for (const ch of text) {
        if (HANZI_PINYIN_MAP[ch]) {
          out += HANZI_PINYIN_MAP[ch];
        } else if (/[a-zA-Z0-9]/.test(ch)) {
          out += ch.toLowerCase();
        }
      }
      return out;
    }

    function evaluatePhonemeMatch(targetText, heardText, hintPinyin) {
      const cleanTarget = (targetText || '').trim();
      const cleanHeard = (heardText || '').trim();
      const normTargetHanzi = cleanTarget.replace(/[^a-zA-Z0-9一-龥]/g, '').toLowerCase();
      const normHeardHanzi = cleanHeard.replace(/[^a-zA-Z0-9一-龥]/g, '').toLowerCase();

      // 1. Direct character match
      if (normHeardHanzi === normTargetHanzi || (normHeardHanzi.length >= 2 && normHeardHanzi.includes(normTargetHanzi)) || (normTargetHanzi.length >= 2 && normTargetHanzi.includes(normHeardHanzi))) {
        return { isPass: true, score: 100, heardPinyin: hanziToPinyin(normHeardHanzi), targetPinyin: stripTone(hintPinyin) || hanziToPinyin(normTargetHanzi), reason: 'ตรงตามตัวอักษร 100%' };
      }

      // 2. Pinyin / Phoneme conversion
      const targetPinyin = stripTone(hintPinyin) || hanziToPinyin(normTargetHanzi);
      const heardPinyin = hanziToPinyin(normHeardHanzi) || stripTone(normHeardHanzi);

      if (targetPinyin && heardPinyin) {
        if (heardPinyin === targetPinyin) {
          return { isPass: true, score: 98, heardPinyin, targetPinyin, reason: 'หน่วยเสียงพินอินตรงกัน (' + heardPinyin + ')' };
        }
        if (heardPinyin.includes(targetPinyin) || (targetPinyin.length >= 3 && targetPinyin.includes(heardPinyin))) {
          return { isPass: true, score: 88, heardPinyin, targetPinyin, reason: 'สำเนียงครอบคลุมคำเป้าหมาย (' + heardPinyin + ')' };
        }
        let matches = 0;
        const minL = Math.min(targetPinyin.length, heardPinyin.length);
        const maxL = Math.max(targetPinyin.length, heardPinyin.length);
        for (let i = 0; i < minL; i++) {
          if (targetPinyin[i] === heardPinyin[i]) matches++;
        }
        const similarity = Math.round((matches / maxL) * 100);
        if (similarity >= 55) {
          return { isPass: true, score: similarity, heardPinyin, targetPinyin, reason: 'หน่วยเสียงใกล้เคียง ' + similarity + '% (เกณฑ์เด็กผ่าน)' };
        }
        return { isPass: false, score: similarity, heardPinyin, targetPinyin, reason: 'เสียงยังไม่ตรง (' + heardPinyin + ')' };
      }
      return { isPass: false, score: 20, heardPinyin: '', targetPinyin: '', reason: 'ยังไม่ตรงเป้าหมาย' };
    }

    function renderSpeakStep(stage) {
      const data = CURRENT_LESSON.speak;
      let h = `
        <div class="text-center space-y-4">
          <div class="inline-block px-3 py-1 rounded-full bg-emerald-100 text-emerald-900 text-xs font-black">
            🗣️ ขั้นที่ 2 · ฝึกทักษะการพูด (Auto Mic + Phoneme Lab)
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
            <button id="btnChineseMic" onclick="triggerChineseMic('${data.target.replace(/'/g, "\\'")}')" class="px-6 py-3.5 rounded-2xl bg-slate-400 text-white font-display font-black text-base shadow-xl ring-4 ring-slate-300 transition cursor-pointer flex items-center justify-center gap-2 mx-auto">
              <span>⏳ รอครูพูดจบ แล้วไมค์จะเปิดเองอัตโนมัติ...</span>
            </button>
            <div id="micStatusText" class="text-xs text-slate-500 font-bold mt-2">
              ไม่ต้องกดอะไรนะคะ — ไมค์จะเปิดอัตโนมัติเมื่อครูพูดจบ
            </div>
            <div id="micLiveWords" class="hidden max-w-sm mx-auto"></div>
          </div>

          <div id="stepFeedback" class="min-h-12 text-xs font-bold text-emerald-600 flex items-center justify-center"></div>
        </div>
      `;
      stage.innerHTML = h;
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

        cnMicUI('listening', '🎙️ ไมค์เปิดอัตโนมัติแล้ว... พูดคำว่า "' + targetText + '" ได้เลยค่ะ');

        if (liveBox) {
          liveBox.classList.remove('hidden');
          liveBox.className = 'mt-3 px-4 py-3 rounded-2xl bg-rose-50 border-2 border-rose-200 text-center animate-pulse';
          liveBox.innerHTML = `
            <div class="text-[10px] font-black text-rose-700 mb-1">🔴 ไมค์เปิดอัตโนมัติแล้ว กำลังรับฟังเสียง</div>
            <div class="font-display font-black text-2xl text-slate-900 leading-tight">พูดคำว่า "${targetText}" ได้เลยจ้ะ</div>
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
            cnMicUI('retry', 'ยังไม่ได้ยินเสียงชัดเจน — ไมค์จะลองเปิดให้อีกครั้งนะคะ 🙂');
            setTimeout(() => { if (CURRENT_STEP === 1) window.__cnAutoOpenMic(); }, 1200);
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
            handlePhonemeEvaluationResult(targetText, '', 'เกิดข้อผิดพลาดในการเชื่อมต่อ');
          }
        };

        rec.start();

        // 3.5 วินาที สำหรับฟังเสียงพูดของเด็ก แล้วส่งตรวจอัตโนมัติ
        __cnMaxTimer = setTimeout(() => {
          if (isMicListening && __cnMediaRecorder && __cnMediaRecorder.state === 'recording') {
            stopChineseMic(true);
          }
        }, 3500);

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
      } else {
        playTone('wrong');
        cnMicUI('retry', 'เสียงยังไม่ตรง ลองฟังครูอีกครั้งนะคะ');

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
        speakMandarin('再试一次', 0.85, () => {
          // AUTO MIC RETRY: เปิดไมค์ให้เด็กพูดใหม่อัตโนมัติ!
          setTimeout(() => {
            if (CURRENT_STEP === 1) {
              window.__cnAutoOpenMic();
            }
          }, 600);
        });
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
        cnMicUI('listening', 'กำลังฟังเสียงภาษาจีน... (พูดได้เลยค่ะ)');

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

"""

# Build base patched html
patched_html = orig_html[:idxA_start] + secA_replacement + orig_html[idxA_end:]

# Recalculate idxB on patched_html
idxB_start = patched_html.find(secB_start_marker)
idxB_end = patched_html.find(secB_end_marker)
patched_html = patched_html[:idxB_start] + secB_replacement + patched_html[idxB_end:]

# 1. Update chinese.html (production page)
with open('/var/www/kidobits/chinese.html', 'w', encoding='utf-8') as f:
    f.write(patched_html)

# 2. Build chinese_lab.html with the banner
lab_html = patched_html
body_tag = '<body class="min-h-screen text-slate-800 flex flex-col justify-between selection:bg-orange-200">'
lab_top_banner = """<body class="min-h-screen text-slate-800 flex flex-col justify-between selection:bg-orange-200">
  <!-- ================= PHONEME LAB BANNER ================= -->
  <div class="bg-gradient-to-r from-purple-700 via-indigo-600 to-blue-600 text-white px-4 py-2 text-center text-xs font-bold flex flex-wrap items-center justify-center gap-2 shadow-md z-50">
    <span class="inline-flex items-center gap-1.5 bg-white/20 px-2 py-0.5 rounded-full text-[11px] font-black uppercase tracking-wider">
      🧪 Phoneme Lab Mode (Auto Mic)
    </span>
    <span>ห้องทดลองประเมินเสียงพูดภาษาจีน (ไมค์เปิดอัตโนมัติ + เทียบด้วย Pinyin & หน่วยเสียง)</span>
    <a href="/chinese.html" class="bg-white text-indigo-900 hover:bg-slate-100 px-3 py-0.5 rounded-full text-xs font-black shadow-xs transition ml-2">
      สลับไปหน้าเดิม ➔
    </a>
  </div>
"""
lab_html = lab_html.replace(body_tag, lab_top_banner, 1)

modal_banner_target = '<div class="px-4 py-3 bg-gradient-to-r from-red-500 via-orange-500 to-amber-500 text-white flex items-center justify-between shrink-0">'
modal_lab_badge = """<div class="px-4 py-1.5 bg-gradient-to-r from-purple-700 to-indigo-700 text-white text-[11px] font-black flex items-center justify-between shrink-0">
        <span class="flex items-center gap-1.5">🧪 <span>Phoneme Lab Active: Auto Mic + Local Server STT</span></span>
        <span class="bg-white/20 px-2 py-0.5 rounded-full text-[10px]">Auto Mic Engine</span>
      </div>
      <div class="px-4 py-3 bg-gradient-to-r from-red-500 via-orange-500 to-amber-500 text-white flex items-center justify-between shrink-0">"""
lab_html = lab_html.replace(modal_banner_target, modal_lab_badge, 1)

with open('/var/www/kidobits/chinese_lab.html', 'w', encoding='utf-8') as f:
    f.write(lab_html)

print("SUCCESS: Both chinese.html and chinese_lab.html deployed with True Auto Mic!")
