import paramiko

print("Connecting to remote server 89.167.82.205...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=15)
sftp = ssh.open_sftp()

# =============================================================================
# 1. UPDATE chinese.html
# =============================================================================
print("Reading chinese.html...")
with sftp.open('/var/www/kidobits/chinese.html', 'r') as f:
    cn_html = f.read().decode('utf-8')

# Ensure window.LESSONS is defined after CHINESE_DATA
if 'const LESSONS =' not in cn_html and 'window.LESSONS =' not in cn_html:
    cn_anchor = "// ================= APPLICATION STATE ================="
    cn_lessons_def = """    // Flattened all lessons for progression and navigation
    const LESSONS = [
      ...(CHINESE_DATA.early || []),
      ...(CHINESE_DATA.lower || []),
      ...(CHINESE_DATA.upper || [])
    ];
    window.LESSONS = LESSONS;

    // ================= APPLICATION STATE ================="""
    cn_html = cn_html.replace(cn_anchor, cn_lessons_def, 1)
    print("Added LESSONS array to chinese.html")

# Verify renderSummaryStep has safe fallback
old_cn_summary_search = """      // Mark completed & unlock next lesson in KidobitsLock
      const curIdx = LESSONS.findIndex(l => l.id === CURRENT_LESSON.id);
      const nextLesson = (curIdx >= 0 && curIdx < LESSONS.length - 1) ? LESSONS[curIdx + 1] : null;"""

new_cn_summary_search = """      // Mark completed & unlock next lesson in KidobitsLock
      const allLessons = window.LESSONS || [
        ...(CHINESE_DATA.early || []),
        ...(CHINESE_DATA.lower || []),
        ...(CHINESE_DATA.upper || [])
      ];
      const curIdx = allLessons.findIndex(l => l.id === CURRENT_LESSON.id);
      const nextLesson = (curIdx >= 0 && curIdx < allLessons.length - 1) ? allLessons[curIdx + 1] : null;"""

if old_cn_summary_search in cn_html:
    cn_html = cn_html.replace(old_cn_summary_search, new_cn_summary_search, 1)
    print("Updated renderSummaryStep in chinese.html")

with sftp.open('/tmp/chinese.html', 'w') as f:
    f.write(cn_html.encode('utf-8'))


# =============================================================================
# 2. UPDATE theme/theme_level2.html
# =============================================================================
print("Reading theme/theme_level2.html...")
with sftp.open('/var/www/kidobits/theme/theme_level2.html', 'r') as f:
    l2_html = f.read().decode('utf-8')

# Add lock script to head if missing
if 'kidobits_curriculum_lock.js' not in l2_html:
    l2_html = l2_html.replace('</head>', '  <script src="js/kidobits_curriculum_lock.js"></script>\n</head>', 1)
    print("Added lock script to theme_level2.html")

# Fix duplicate praise in mic match:
old_l2_mic_praise = """          playEmmaMp3('/kidobits/audio/l2/praise_reading.mp3', () => {
            setTimeout(() => {
              handleChildSuccess(it, 'mic');
            }, 400);
          });"""

new_l2_mic_praise = """          // Single praise playback handled inside handleChildSuccess
          handleChildSuccess(it, 'mic');"""

if old_l2_mic_praise in l2_html:
    l2_html = l2_html.replace(old_l2_mic_praise, new_l2_mic_praise, 1)
    print("Fixed duplicate praise in theme_level2.html")

# Add Auto-Next button & timer in renderSummary:
old_l2_summary_buttons = """          <div class="space-y-2 pt-1">
            ${hasNext ? `
              <button onclick="openLesson('${nextLid}')" class="w-full py-3 rounded-2xl bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-black text-sm uppercase tracking-wide flex items-center justify-center gap-2 shadow-lg shadow-orange-500/25 active:scale-98">
                <span>▶ ไปบทเรียนถัดไป (${nextLid}) ทันที</span>
              </button>
            ` : `
              <button onclick="alert('🏆 ยินดีด้วย! หนูพิชิต Level 2 ครบทั้ง 16 บทเรียนแล้ว!')" class="w-full py-3 rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-400 text-slate-950 font-black text-sm shadow-xl">
                <span>🏆 รับเกียรติบัตร Level 2 Master Reader</span>
              </button>
            `}
            <button onclick="openLesson('${STATE.lid}')" class="w-full py-2 rounded-2xl bg-white hover:bg-slate-50 text-slate-700 font-bold text-xs border border-slate-300">
              🔄 เล่นบทนี้อีกครั้ง
            </button>
            <button onclick="closeLesson()" class="w-full py-2 rounded-2xl bg-orange-50 hover:bg-orange-100 text-orange-700 font-bold text-xs border border-orange-200">
              🏠 กลับสู่แผนที่รวมด่าน
            </button>
          </div>
        </div>
      `;

      emmaSpeak(`Wonderful work! You completed lesson ${STATE.lid}. See you in the next lesson!`, `/kidobits/audio/l2/prompt_lesson_done.mp3`);
    }"""

new_l2_summary_buttons = """          <div class="space-y-2 pt-1">
            ${hasNext ? `
              <button id="btnAutoNextL2" onclick="if(window.l2AutoNextTimer) clearInterval(window.l2AutoNextTimer); openLesson('${nextLid}')" class="w-full py-3.5 rounded-2xl bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-black text-sm uppercase tracking-wide flex items-center justify-center gap-2 shadow-lg shadow-orange-500/25 active:scale-98 cursor-pointer">
                <span>▶ ไปบทเรียนถัดไป (${nextLid}) ทันที</span>
                <span id="l2AutoCount" class="bg-black/25 text-white text-xs px-2.5 py-0.5 rounded-full font-mono">3s</span>
              </button>
            ` : `
              <button onclick="alert('🏆 ยินดีด้วย! หนูพิชิต Level 2 ครบทั้ง 16 บทเรียนแล้ว!')" class="w-full py-3 rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-400 text-slate-950 font-black text-sm shadow-xl">
                <span>🏆 รับเกียรติบัตร Level 2 Master Reader</span>
              </button>
            `}
            <button onclick="if(window.l2AutoNextTimer) clearInterval(window.l2AutoNextTimer); openLesson('${STATE.lid}')" class="w-full py-2 rounded-2xl bg-white hover:bg-slate-50 text-slate-700 font-bold text-xs border border-slate-300 cursor-pointer">
              🔄 เล่นบทนี้อีกครั้ง
            </button>
            <button onclick="if(window.l2AutoNextTimer) clearInterval(window.l2AutoNextTimer); closeLesson()" class="w-full py-2 rounded-2xl bg-orange-50 hover:bg-orange-100 text-orange-700 font-bold text-xs border border-orange-200 cursor-pointer">
              🏠 กลับสู่แผนที่รวมด่าน
            </button>
          </div>
        </div>
      `;

      emmaSpeak(`Wonderful work! You completed lesson ${STATE.lid}. See you in the next lesson!`, `/kidobits/audio/l2/prompt_lesson_done.mp3`);

      // Update curriculum lock
      if (window.KidobitsLock) {
        KidobitsLock.markCompleted('phonics', STATE.lid, nextNum);
      }

      // Auto-Next Timer (3 seconds)
      if (hasNext) {
        let remain = 3;
        const countEl = document.getElementById('l2AutoCount');
        if (window.l2AutoNextTimer) clearInterval(window.l2AutoNextTimer);
        window.l2AutoNextTimer = setInterval(() => {
          remain--;
          if (countEl) countEl.textContent = remain + 's';
          if (remain <= 0) {
            clearInterval(window.l2AutoNextTimer);
            openLesson(nextLid);
          }
        }, 1000);
      }
    }"""

if old_l2_summary_buttons in l2_html:
    l2_html = l2_html.replace(old_l2_summary_buttons, new_l2_summary_buttons, 1)
    print("Added Auto Next and Lock to theme_level2.html")

# Ensure closeLesson clears timer
if 'if (window.l2AutoNextTimer)' not in l2_html:
    l2_html = l2_html.replace('function closeLesson() {', 'function closeLesson() {\n      if (window.l2AutoNextTimer) { clearInterval(window.l2AutoNextTimer); window.l2AutoNextTimer = null; }', 1)

with sftp.open('/tmp/theme_level2.html', 'w') as f:
    f.write(l2_html.encode('utf-8'))


# =============================================================================
# 3. UPDATE theme/theme_level3.html
# =============================================================================
print("Reading theme/theme_level3.html...")
with sftp.open('/var/www/kidobits/theme/theme_level3.html', 'r') as f:
    l3_html = f.read().decode('utf-8')

# Add lock script to head if missing
if 'kidobits_curriculum_lock.js' not in l3_html:
    l3_html = l3_html.replace('</head>', '  <script src="js/kidobits_curriculum_lock.js"></script>\n</head>', 1)
    print("Added lock script to theme_level3.html")

# Fix duplicate praise in mic match:
old_l3_mic_praise = """          playEmmaMp3('/kidobits/audio/l3/praise_reading.mp3', () => {
            setTimeout(() => {
              handleChildSuccess(it, 'mic');
            }, 400);
          });"""

new_l3_mic_praise = """          // Single praise playback handled inside handleChildSuccess
          handleChildSuccess(it, 'mic');"""

if old_l3_mic_praise in l3_html:
    l3_html = l3_html.replace(old_l3_mic_praise, new_l3_mic_praise, 1)
    print("Fixed duplicate praise in theme_level3.html")

# Add Auto-Next button & timer in renderSummary:
old_l3_summary_buttons = """          <div class="space-y-2 pt-1">
            ${hasNext ? `
              <button onclick="openLesson('${nextLid}')" class="w-full py-3 rounded-2xl bg-gradient-to-r from-[#8B7CFF] to-purple-600 hover:from-[#7A6AE6] hover:to-purple-700 text-white font-black text-sm uppercase tracking-wide flex items-center justify-center gap-2 shadow-lg shadow-purple-500/25 active:scale-98">
                <span>▶ ไปบทเรียนถัดไป (${nextLid}) ทันที</span>
              </button>
            ` : `
              <button onclick="alert('🏆 ยินดีด้วย! หนูพิชิต Level 3 ครบทั้ง 16 บทเรียนแล้ว!')" class="w-full py-3 rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-400 text-slate-950 font-black text-sm shadow-xl">
                <span>🏆 รับเกียรติบัตร Level 3 Master Storyteller</span>
              </button>
            `}
            <button onclick="openLesson('${STATE.lid}')" class="w-full py-2 rounded-2xl bg-white hover:bg-slate-50 text-slate-700 font-bold text-xs border border-slate-300">
              🔄 เล่นบทนี้อีกครั้ง
            </button>
            <button onclick="closeLesson()" class="w-full py-2 rounded-2xl bg-purple-50 hover:bg-purple-100 text-purple-700 font-bold text-xs border border-purple-200">
              🏠 กลับสู่แผนที่รวมด่าน
            </button>
          </div>
        </div>
      `;

      emmaSpeak(`Wonderful work! You completed lesson ${STATE.lid}. See you in the next lesson!`, `/kidobits/audio/l3/prompt_lesson_done.mp3`);
    }"""

new_l3_summary_buttons = """          <div class="space-y-2 pt-1">
            ${hasNext ? `
              <button id="btnAutoNextL3" onclick="if(window.l3AutoNextTimer) clearInterval(window.l3AutoNextTimer); openLesson('${nextLid}')" class="w-full py-3.5 rounded-2xl bg-gradient-to-r from-[#8B7CFF] to-purple-600 hover:from-[#7A6AE6] hover:to-purple-700 text-white font-black text-sm uppercase tracking-wide flex items-center justify-center gap-2 shadow-lg shadow-purple-500/25 active:scale-98 cursor-pointer">
                <span>▶ ไปบทเรียนถัดไป (${nextLid}) ทันที</span>
                <span id="l3AutoCount" class="bg-black/25 text-white text-xs px-2.5 py-0.5 rounded-full font-mono">3s</span>
              </button>
            ` : `
              <button onclick="alert('🏆 ยินดีด้วย! หนูพิชิต Level 3 ครบทั้ง 16 บทเรียนแล้ว!')" class="w-full py-3 rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-400 text-slate-950 font-black text-sm shadow-xl">
                <span>🏆 รับเกียรติบัตร Level 3 Master Storyteller</span>
              </button>
            `}
            <button onclick="if(window.l3AutoNextTimer) clearInterval(window.l3AutoNextTimer); openLesson('${STATE.lid}')" class="w-full py-2 rounded-2xl bg-white hover:bg-slate-50 text-slate-700 font-bold text-xs border border-slate-300 cursor-pointer">
              🔄 เล่นบทนี้อีกครั้ง
            </button>
            <button onclick="if(window.l3AutoNextTimer) clearInterval(window.l3AutoNextTimer); closeLesson()" class="w-full py-2 rounded-2xl bg-purple-50 hover:bg-purple-100 text-purple-700 font-bold text-xs border border-purple-200 cursor-pointer">
              🏠 กลับสู่แผนที่รวมด่าน
            </button>
          </div>
        </div>
      `;

      emmaSpeak(`Wonderful work! You completed lesson ${STATE.lid}. See you in the next lesson!`, `/kidobits/audio/l3/prompt_lesson_done.mp3`);

      // Update curriculum lock
      if (window.KidobitsLock) {
        KidobitsLock.markCompleted('phonics', STATE.lid, nextNum);
      }

      // Auto-Next Timer (3 seconds)
      if (hasNext) {
        let remain = 3;
        const countEl = document.getElementById('l3AutoCount');
        if (window.l3AutoNextTimer) clearInterval(window.l3AutoNextTimer);
        window.l3AutoNextTimer = setInterval(() => {
          remain--;
          if (countEl) countEl.textContent = remain + 's';
          if (remain <= 0) {
            clearInterval(window.l3AutoNextTimer);
            openLesson(nextLid);
          }
        }, 1000);
      }
    }"""

if old_l3_summary_buttons in l3_html:
    l3_html = l3_html.replace(old_l3_summary_buttons, new_l3_summary_buttons, 1)
    print("Added Auto Next and Lock to theme_level3.html")

# Ensure closeLesson clears timer
if 'if (window.l3AutoNextTimer)' not in l3_html:
    l3_html = l3_html.replace('function closeLesson() {', 'function closeLesson() {\n      if (window.l3AutoNextTimer) { clearInterval(window.l3AutoNextTimer); window.l3AutoNextTimer = null; }', 1)

with sftp.open('/tmp/theme_level3.html', 'w') as f:
    f.write(l3_html.encode('utf-8'))

sftp.close()

def run_sudo_cmd(cmd):
    full_cmd = f"echo 'OpenHands@ERP2026' | sudo -S bash -c \"{cmd}\""
    stdin, stdout, stderr = ssh.exec_command(full_cmd)
    return stdout.read().decode('utf-8'), stderr.read().decode('utf-8')

print("Deploying updated files with sudo...")
run_sudo_cmd("cp /tmp/chinese.html /var/www/kidobits/chinese.html")
run_sudo_cmd("cp /tmp/theme_level2.html /var/www/kidobits/theme/theme_level2.html")
run_sudo_cmd("cp /tmp/theme_level3.html /var/www/kidobits/theme/theme_level3.html")
run_sudo_cmd("chown www-data:www-data /var/www/kidobits/chinese.html /var/www/kidobits/theme/theme_level2.html /var/www/kidobits/theme/theme_level3.html")

print("Checking git diff stat...")
stdin, stdout, stderr = ssh.exec_command("cd /var/www/kidobits && git diff --stat")
print(stdout.read().decode('utf-8'))

print("Committing and pushing...")
msg = "fix: remove duplicate praise and add 3s auto-next progression to Phonics L2/L3 and Chinese"
cmd = f"cd /var/www/kidobits && git add chinese.html theme/theme_level2.html theme/theme_level3.html && git commit -m \\\"{msg}\\\" && git push origin main"
out, err = run_sudo_cmd(cmd)
print("OUT:\n", out)
print("ERR:\n", err)

ssh.close()
print("All finished!")
