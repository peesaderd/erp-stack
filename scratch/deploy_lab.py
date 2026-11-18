import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)

with open('scratch/remote_script.py', 'w', encoding='utf-8') as f:
    f.write(r'''# -*- coding: utf-8 -*-
import re

with open('/var/www/kidobits/chinese.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Insert Top Lab Mode Banner
body_tag = '<body class="min-h-screen text-slate-800 flex flex-col justify-between selection:bg-orange-200">'
lab_top_banner = """<body class="min-h-screen text-slate-800 flex flex-col justify-between selection:bg-orange-200">
  <!-- ================= PHONEME LAB BANNER ================= -->
  <div class="bg-gradient-to-r from-purple-700 via-indigo-600 to-blue-600 text-white px-4 py-2.5 text-center text-xs font-bold flex flex-wrap items-center justify-center gap-2 shadow-md z-50">
    <span class="inline-flex items-center gap-1.5 bg-white/20 px-2 py-0.5 rounded-full text-[11px] font-black uppercase tracking-wider">
      🧪 Phoneme Lab Mode
    </span>
    <span>ห้องทดลองประเมินเสียงพูดภาษาจีน (เทียบด้วย Pinyin & หน่วยเสียง ช่วยให้เด็กพูดผ่านได้ง่ายขึ้น ไม่ติดปัญหาตัวอักษรพ้องรูป)</span>
    <a href="/chinese.html" class="bg-white text-indigo-900 hover:bg-slate-100 px-3 py-0.5 rounded-full text-xs font-black shadow-xs transition ml-2">
      สลับไปหน้าเดิม ➔
    </a>
  </div>
"""
html = html.replace(body_tag, lab_top_banner)

# 2. Insert Player Modal Lab Badge
modal_banner_target = '<div class="px-4 py-3 bg-gradient-to-r from-red-500 via-orange-500 to-amber-500 text-white flex items-center justify-between shrink-0">'
modal_lab_badge = """<div class="px-4 py-1.5 bg-gradient-to-r from-purple-700 to-indigo-700 text-white text-[11px] font-black flex items-center justify-between shrink-0">
        <span class="flex items-center gap-1.5">🧪 <span>Phoneme Lab Active: ตรวจจับเสียงด้วยหน่วยเสียงพินอิน + อนุโลมสำเนียงเด็ก</span></span>
        <span class="bg-white/20 px-2 py-0.5 rounded-full text-[10px]">Pinyin & Homophone Engine</span>
      </div>
      <div class="px-4 py-3 bg-gradient-to-r from-red-500 via-orange-500 to-amber-500 text-white flex items-center justify-between shrink-0">"""
html = html.replace(modal_banner_target, modal_lab_badge, 1)

# 3. Add Comprehensive Pinyin & Phoneme Evaluation Engine
phoneme_engine_js = """
    // ================= PHONEME LAB: CHINESE PINYIN & PHONEME ENGINE =================
    const HANZI_PINYIN_MAP = {
      // Common characters in curriculum
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
      '猫': 'mao', '狗': 'gou', '鳥': 'niao', '鸟': 'niao',
      '点': 'dian', '半': 'ban', '分': 'fen', '往': 'wang', '前': 'qian', '走': 'zou', '向': 'xiang', '左': 'zuo', '右': 'you'
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

      // Normalize Hanzi
      const normTargetHanzi = cleanTarget.replace(/[^a-zA-Z0-9一-龥]/g, '').toLowerCase();
      const normHeardHanzi = cleanHeard.replace(/[^a-zA-Z0-9一-龥]/g, '').toLowerCase();

      // 1. Direct character match
      if (normHeardHanzi === normTargetHanzi || (normHeardHanzi.length >= 2 && normHeardHanzi.includes(normTargetHanzi)) || (normTargetHanzi.length >= 2 && normTargetHanzi.includes(normHeardHanzi))) {
        return { isPass: true, score: 100, heardPinyin: hanziToPinyin(normHeardHanzi), targetPinyin: stripTone(hintPinyin) || hanziToPinyin(normTargetHanzi), reason: 'ตรงตามตัวอักษร 100%' };
      }

      // 2. Convert to tone-stripped Pinyin
      const targetPinyin = stripTone(hintPinyin) || hanziToPinyin(normTargetHanzi);
      const heardPinyin = hanziToPinyin(normHeardHanzi) || stripTone(normHeardHanzi);

      if (targetPinyin && heardPinyin) {
        // Direct pinyin equivalence (e.g. 八八 == 爸爸 -> baba == baba)
        if (heardPinyin === targetPinyin) {
          return { isPass: true, score: 98, heardPinyin, targetPinyin, reason: 'หน่วยเสียงพินอินตรงกัน (' + heardPinyin + ')' };
        }
        // Substring pinyin containment
        if (heardPinyin.includes(targetPinyin) || (targetPinyin.length >= 3 && targetPinyin.includes(heardPinyin))) {
          return { isPass: true, score: 88, heardPinyin, targetPinyin, reason: 'สำเนียงครอบคลุมคำเป้าหมาย (' + heardPinyin + ')' };
        }

        // Syllable overlap check
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
"""

# 4. Replace evaluation inside triggerChineseMic
html = html.replace('function triggerChineseMic(targetText) {', phoneme_engine_js + '\n    function triggerChineseMic(targetText) {')

old_eval_code = """          if (cleanHeard === cleanTarget || cleanHeard.includes(cleanTarget) || cleanTarget.includes(cleanHeard)) {
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
          }"""

new_eval_code = """          // ================= PHONEME LAB EVALUATION =================
          const targetHintPinyin = (CURRENT_LESSON && CURRENT_LESSON.speak && CURRENT_LESSON.speak.pinyin) || '';
          const evalRes = evaluatePhonemeMatch(targetText, heard, targetHintPinyin);

          window.__cnLabAttempts = (window.__cnLabAttempts || 0) + 1;

          if (evalRes.isPass) {
            playTone('correct');
            TOTAL_STARS += 1;
            updateGlobalStars();
            window.__cnLabAttempts = 0;
            fb.innerHTML = `
              <div class="p-3 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-center animate-pop">
                <div class="text-base font-black">🎉 ยอดเยี่ยมมากค่ะ! [${evalRes.score}%] ⭐⭐⭐</div>
                <div class="text-xs font-bold text-emerald-700 mt-0.5">${evalRes.reason}</div>
                <div class="text-[11px] text-slate-500 mt-1">ที่ได้ยิน: <b>"${heard}"</b> (${evalRes.heardPinyin || '-'}) ➔ เป้าหมาย: <b>"${targetText}"</b> (${evalRes.targetPinyin || '-'})</div>
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
            fb.innerHTML = `
              <div class="p-3 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 text-center">
                <div class="text-sm font-black text-rose-700">เสียงยังไม่ตรง ลองใหม่อีกครั้งนะคะ 🙂</div>
                <div class="text-[11px] text-slate-600 mt-1">ที่ได้ยิน: <b>"${heard}"</b> (${evalRes.heardPinyin || '-'}) | คำเป้าหมาย: <b>"${targetText}"</b> (${evalRes.targetPinyin || '-'})</div>
                ${window.__cnLabAttempts >= 2 ? `
                  <div class="mt-2.5 pt-2 border-t border-rose-200">
                    <button onclick="playTone('correct'); TOTAL_STARS += 1; updateGlobalStars(); CURRENT_STEP = 2; renderStep();" class="px-3.5 py-1.5 bg-gradient-to-r from-amber-400 to-orange-400 hover:from-amber-500 hover:to-orange-500 text-white rounded-full text-xs font-black shadow-md transition active:scale-95 flex items-center justify-center gap-1 mx-auto cursor-pointer">
                      <span>⭐ คุณครูให้ผ่าน (ยอดเยี่ยมมากค่ะ แตะเพื่อไปต่อ) ➔</span>
                    </button>
                  </div>
                ` : ''}
              </div>
            `;
            speakMandarin('再试一次', 0.85);
          }"""

html = html.replace(old_eval_code, new_eval_code)

fallback_id_code = """      const params = new URLSearchParams(window.location.search);
      const lId = params.get('lesson') || params.get('id') || params.get('les');"""

fallback_id_replacement = """      const params = new URLSearchParams(window.location.search);
      let lId = params.get('lesson') || params.get('id') || params.get('les');
      // Phoneme Lab helper: normalize L1.01 -> K1.01
      if (lId && lId.startsWith('L')) {
        lId = 'K' + lId.slice(1);
      }"""
html = html.replace(fallback_id_code, fallback_id_replacement)

with open('/var/www/kidobits/chinese_lab.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("SUCCESS: /var/www/kidobits/chinese_lab.html re-written with full Phoneme Lab features!")
''')

sftp = ssh.open_sftp()
sftp.put('scratch/remote_script.py', '/tmp/create_chinese_lab.py')
sftp.close()

cmd = 'echo "OpenHands@ERP2026" | sudo -S python3 /tmp/create_chinese_lab.py && echo "OpenHands@ERP2026" | sudo -S chown www-data:www-data /var/www/kidobits/chinese_lab.html && echo "OpenHands@ERP2026" | sudo -S chmod 775 /var/www/kidobits/chinese_lab.html'
stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
ssh.close()
