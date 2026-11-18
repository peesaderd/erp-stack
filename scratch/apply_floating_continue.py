import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_patch = """
import re

# =========================================================================
# 1. CLEAN UP theme_home.html (Remove Continue card & Mini Leaderboard)
# =========================================================================
home_path = '/var/www/kidobits/theme/theme_home.html'
with open(home_path, 'r', encoding='utf-8') as f:
    home_html = f.read()

# Pattern matching the injection engine
pat_home = r'<script>\\s*// --- Kidobits Hub Dynamic Engine[\\s\\S]*?window\\.addEventListener\\(\\'kidobits_wallet_updated\\', initHubWidgets\\);\\s*\\}\\)\\(\\);\\s*</script>'

clean_home_engine = '''<script>
// --- Kidobits Hub Live Stats Engine ---
(function() {
  function initHubWidgets() {
    if (!window.KidobitsWallet) return;
    const user = KidobitsWallet.getUser();

    // Update Header Counters
    document.querySelectorAll('*').forEach(el => {
      if (el.children.length === 0) {
        let t = el.innerText || el.textContent || '';
        if (t.includes('🔥') && !el.dataset.walletDone) {
          el.innerText = `🔥 ${user.streak}`;
          el.dataset.walletDone = '1';
        } else if (t.includes('🪙') && !el.dataset.walletDone) {
          el.innerText = `🪙 ${user.coins}`;
          el.dataset.walletDone = '1';
        }
      }
    });

    // Remove any continue lesson / leaderboard cards if present
    const card = document.getElementById('kidobits-continue-lesson-card');
    if (card) card.remove();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(initHubWidgets, 400));
  } else {
    setTimeout(initHubWidgets, 400);
  }
  window.addEventListener('kidobits_wallet_updated', initHubWidgets);
})();
</script>'''

if re.search(pat_home, home_html):
    home_html = re.sub(pat_home, clean_home_engine, home_html)
    with open('/tmp/theme_home.html', 'w', encoding='utf-8') as f:
        f.write(home_html)
    print("Patched theme_home.html: removed Continue and Leaderboard sections from Hub")
else:
    print("Could not match Hub Dynamic Engine regex in theme_home.html")

# =========================================================================
# 2. UPDATE theme_phonicsLesson.html with Floating Continue Toast
# =========================================================================
lesson_path = '/var/www/kidobits/theme/theme_phonicsLesson.html'
with open(lesson_path, 'r', encoding='utf-8') as f:
    lesson_html = f.read()

# Add CSS for .resumetoast
toast_css = '''
    /* Floating Continue Toast (ยกมาจาก v2/lesson.html) */
    .resumetoast {
      position: fixed;
      left: 50%;
      transform: translateX(-50%);
      bottom: 24px;
      z-index: 9999;
      background: #1E9E5A;
      color: #fff;
      padding: 10px 18px;
      border-radius: 999px;
      font-size: 0.88rem;
      font-weight: 700;
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
      display: flex;
      gap: 10px;
      align-items: center;
      max-width: 92vw;
      animation: toastFadeIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
      transition: opacity 0.35s ease, transform 0.35s ease;
      white-space: nowrap;
    }
    .resumetoast button {
      background: rgba(255, 255, 255, 0.22);
      border: 0;
      color: #fff;
      padding: 5px 12px;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 800;
      cursor: pointer;
      transition: background 0.15s, transform 0.1s;
    }
    .resumetoast button:hover {
      background: rgba(255, 255, 255, 0.38);
    }
    .resumetoast button:active {
      transform: scale(0.95);
    }
    .resumetoast.toast-out {
      opacity: 0;
      transform: translate(-50%, 15px);
      pointer-events: none;
    }
    @keyframes toastFadeIn {
      from { opacity: 0; transform: translate(-50%, 15px); }
      to { opacity: 1; transform: translate(-50%, 0); }
    }
  </style>'''

if '.resumetoast' not in lesson_html:
    lesson_html = lesson_html.replace('</style>', toast_css, 1)
    print("Added .resumetoast CSS to theme_phonicsLesson.html")

# Replace startLessonWithAudio and add resumeToast engine
old_start_block = '''    // Start Lesson With Audio Unlock & Auto-Resume
    async function startLessonWithAudio() {
      unlockAudio();
      const cover = document.getElementById('start-cover');
      if (cover) cover.classList.add('gone');
      await openSession(LID);
      const targetStep = parseInt(q.get('step') || '0', 10);
      if (targetStep > 1 && targetStep <= 5) {
        showSoundBadge(`▶️ เรียนต่อ: ขั้นที่ ${targetStep} (${STEPS[targetStep - 1] || ''})`);
        setTimeout(() => jumpToStep(targetStep), 500);
      }
    }'''

new_resume_block = '''    /* ---------- per-lesson progress (resume / marked) ---------- */
    const PKEY = 'kb_prog_v1';
    function progAll() {
      try { return JSON.parse(localStorage.getItem(PKEY)) || {}; } catch(e) { return {}; }
    }
    function progLoad() {
      try {
        const all = progAll();
        if (all[LID] && !all[LID].done && all[LID].step != null) {
          const st = (all[LID].step >= 1 && all[LID].step <= 5) ? all[LID].step : (all[LID].step + 1);
          return { step: st, itemIndex: all[LID].i || 0 };
        }
      } catch(e) {}
      try {
        if (window.KidobitsWallet) {
          const u = window.KidobitsWallet.getUser();
          if (u.lastLesson && u.lastLesson.lessonId === LID && !u.lastLesson.done && u.lastLesson.step > 1) {
            return { step: u.lastLesson.step, itemIndex: 0 };
          }
        }
      } catch(e) {}
      return null;
    }
    function progSaveLocal(stepNo, idx = 0, isDone = false) {
      try {
        const all = progAll();
        all[LID] = {
          step: stepNo,
          i: idx,
          done: isDone,
          updatedAt: Date.now()
        };
        all.__last = LID;
        localStorage.setItem(PKEY, JSON.stringify(all));
      } catch(e) {}
    }
    function progClear() {
      try {
        const a = progAll();
        delete a[LID];
        localStorage.setItem(PKEY, JSON.stringify(a));
      } catch(e) {}
      try {
        fetch(`${API_BASE}/progress/clear`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: 'guest', lesson_id: LID })
        }).catch(()=>{});
      } catch(e) {}
    }

    let resumeToastTimer = null;
    /* ป้าย Floating ปุ่ม Continue หน้าบทเรียน (หายเองใน 6 วินาที ถ้าไม่กด) */
    function resumeToast(savedStep, onAction) {
      const existing = document.getElementById('resumetoast');
      if (existing) existing.remove();
      if (resumeToastTimer) clearTimeout(resumeToastTimer);

      const stepName = STEPS[savedStep - 1] || '';
      const el = document.createElement('div');
      el.id = 'resumetoast';
      el.className = 'resumetoast';
      el.innerHTML = `
        <span>▶️ เล่นต่อ: ขั้นที่ ${savedStep} (${stepName})</span>
        <button id="rsContinue" class="bg-white/30 text-white font-black">เล่นต่อ</button>
        <button id="rsReset">เริ่มใหม่</button>
      `;
      document.body.appendChild(el);

      // หายไปเองใน 6 วินาที ถ้าไม่กด
      resumeToastTimer = setTimeout(() => {
        try {
          el.classList.add('toast-out');
          setTimeout(() => el.remove(), 400);
        } catch(e) {}
      }, 6000);

      const btnGo = el.querySelector('#rsContinue');
      if (btnGo) {
        btnGo.onclick = (e) => {
          e.stopPropagation();
          clearTimeout(resumeToastTimer);
          try { el.remove(); } catch(e) {}
          if (typeof onAction === 'function') onAction('continue');
        };
      }

      const btnReset = el.querySelector('#rsReset');
      if (btnReset) {
        btnReset.onclick = (e) => {
          e.stopPropagation();
          clearTimeout(resumeToastTimer);
          try { el.remove(); } catch(e) {}
          if (typeof onAction === 'function') onAction('reset');
        };
      }
    }

    // Start Lesson With Audio Unlock & Auto-Resume
    async function startLessonWithAudio(forcedStep = null) {
      unlockAudio();
      const cover = document.getElementById('start-cover');
      if (cover) cover.classList.add('gone');

      await openSession(LID);

      const queryStep = parseInt(q.get('step') || '0', 10);
      const saved = progLoad();
      const targetStep = forcedStep || queryStep || (saved ? saved.step : null);

      if (targetStep && targetStep > 1 && targetStep <= 5) {
        setTimeout(() => {
          jumpToStep(targetStep);
          // แสดงป้าย Floating toast แจ้งว่าเล่นต่อจากขั้นที่ X (หายเองใน 6 วินาที)
          resumeToast(targetStep, (act) => {
            if (act === 'reset') {
              progClear();
              jumpToStep(1);
            }
          });
        }, 400);
      }
    }'''

if old_start_block in lesson_html:
    lesson_html = lesson_html.replace(old_start_block, new_resume_block)
    print("Patched startLessonWithAudio and added resumeToast engine to theme_phonicsLesson.html")

# Also add window load listener for Floating toast on cover screen
cover_click_old = '''    const sc = document.getElementById('start-cover');
    if (sc) {
      sc.addEventListener('click', (e) => {
        if (e.target === sc || e.target.closest('.tcinner')) {
          startLessonWithAudio();
        }
      });
    }'''

cover_click_new = '''    const sc = document.getElementById('start-cover');
    if (sc) {
      sc.addEventListener('click', (e) => {
        if (e.target.closest('#resumetoast')) return;
        if (e.target === sc || e.target.closest('.tcinner')) {
          startLessonWithAudio();
        }
      });
    }

    // Initial check when page loads: Show Floating Continue Toast if saved progress exists
    window.addEventListener('load', async () => {
      let saved = progLoad();
      if (!saved) {
        try {
          const res = await fetch(`${API_BASE}/progress/get?user_id=guest&lesson_id=${LID}`);
          const d = await res.json();
          if (d && d.ok && d.found && d.progress && !d.progress.done && d.progress.step > 1) {
            saved = { step: d.progress.step, itemIndex: d.progress.item_index || 0 };
          }
        } catch(e) {}
      }

      if (saved && saved.step > 1) {
        // Floating Continue button: หายไปเองใน 6 วินาที ถ้าไม่กด
        resumeToast(saved.step, (action) => {
          if (action === 'continue') {
            startLessonWithAudio(saved.step);
          } else if (action === 'reset') {
            progClear();
            startLessonWithAudio(1);
          }
        });
      }
    });'''

if cover_click_old in lesson_html:
    lesson_html = lesson_html.replace(cover_click_old, cover_click_new)
    print("Patched cover_click and added window load resumeToast check")

# Save progress to local storage too
if 'progSaveLocal(' not in lesson_html:
    lesson_html = lesson_html.replace(
        "currentStepNo = (data.progress && data.progress.step) ? data.progress.step : currentStepNo;\\n\\n        // Sync progress to API",
        "currentStepNo = (data.progress && data.progress.step) ? data.progress.step : currentStepNo;\\n        progSaveLocal(currentStepNo, (currentItem ? currentItem.index || 0 : 0), false);\\n\\n        // Sync progress to API"
    )
    print("Added progSaveLocal call on advance")

with open('/tmp/theme_phonicsLesson.html', 'w', encoding='utf-8') as f:
    f.write(lesson_html)

"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_floating_continue.py', 'w') as f:
    f.write(remote_patch)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/patch_floating_continue.py")
print("Patch stdout:\n", stdout.read().decode())
print("Patch stderr:\n", stderr.read().decode())

# Deploy with sudo
stdin, stdout, stderr = ssh.exec_command("""
echo 'OpenHands@ERP2026' | sudo -S cp /tmp/theme_home.html /var/www/kidobits/theme/theme_home.html
echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_home.html
echo 'OpenHands@ERP2026' | sudo -S cp /tmp/theme_phonicsLesson.html /var/www/kidobits/theme/theme_phonicsLesson.html
echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_phonicsLesson.html
""")
print("Deploy stdout:\n", stdout.read().decode())
print("Deploy stderr:\n", stderr.read().decode())

ssh.close()
