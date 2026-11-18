import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = """
import re

# =========================================================================
# 1. PATCH theme_home.html
# =========================================================================
home_path = '/var/www/kidobits/theme/theme_home.html'
with open(home_path, 'r', encoding='utf-8') as f:
    home_html = f.read()

old_hub_engine = '''(function() {
  function initHubWidgets() {
    if (!window.KidobitsWallet) return;
    const user = KidobitsWallet.getUser();
    const lead = KidobitsWallet.getLeaderboard();

    // 1. Update Header Counters
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

    // 2. Inject Continue Lesson Card & Mini Leaderboard into DOM
    if (!document.getElementById('kidobits-continue-lesson-card')) {
      const heroBanner = Array.from(document.querySelectorAll('button')).find(x => 
        x.textContent.includes('Kidobits Phonics') || x.textContent.includes('เริ่มเรียนโฟนิกส์')
      );

      if (heroBanner && heroBanner.parentNode) {
        const last = user.lastLesson || {
          subject: 'Phonics',
          lessonId: 'L1.01',
          title: 'Level 1: -at family',
          url: 'theme_phonicsLesson.html?lesson=L1.01'
        };

        const container = document.createElement('div');
        container.id = 'kidobits-continue-lesson-card';
        container.className = 'w-full my-3 space-y-3';
        container.innerHTML = `
          <!-- Continue Lesson Hero Card -->
          <div class="bg-gradient-to-r from-[#6C5CE7] to-[#A29BFE] rounded-[26px] p-4 text-white shadow-md relative overflow-hidden">
            <div class="flex items-center justify-between mb-2">
              <span class="px-2.5 py-0.5 rounded-full bg-white/20 text-white text-[11px] font-black uppercase tracking-wide flex items-center gap-1.5 backdrop-blur-sm">
                ⚡ เรียนต่อจากครั้งที่แล้ว
              </span>
              <span class="text-xs font-bold text-white/90">
                ${last.subject}
              </span>
            </div>
            <div class="flex items-center justify-between gap-3">
              <div class="flex-1">
                <h3 class="font-extrabold text-base sm:text-lg leading-tight">${last.title}</h3>
                <p class="text-xs text-white/80 font-medium mt-0.5">กดเพื่อเล่นต่อทันที</p>
              </div>
              <a href="${last.url}" class="shrink-0 bg-white text-[#6C5CE7] px-4 py-2.5 rounded-full font-black text-xs shadow-md hover:bg-gray-100 active:scale-95 transition flex items-center gap-1.5">
                <span>เรียนต่อ</span> ▶
              </a>
            </div>
            <div class="w-full h-2 bg-black/15 rounded-full overflow-hidden mt-3">
              <div class="h-full bg-[#55EFC4] rounded-full" style="width: 75%"></div>
            </div>
          </div>

          <!-- Mini Leaderboard Card -->
          <div onclick="location.href='theme_leaderboard.html'" class="bg-white border-2 border-[#EBE3F5] rounded-[24px] p-3.5 shadow-sm hover:border-[#6C5CE7] active:scale-[0.99] transition cursor-pointer">
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2">
                <span class="text-2xl">🏆</span>
                <div>
                  <h4 class="font-extrabold text-xs sm:text-sm text-[#2D3436]">Leaderboard สัปดาห์นี้</h4>
                  <p class="text-[11px] text-[#636E72] font-semibold">
                    อันดับของคุณ: <b class="text-[#6C5CE7]">อันดับที่ ${lead.userRank}</b> (⭐ ${lead.userStars} ดาว)
                  </p>
                </div>
              </div>
              <span class="text-[11px] font-black text-[#6C5CE7] bg-[#F3EFFF] px-2.5 py-1 rounded-full">
                ดูอันดับ →
              </span>
            </div>
            <div class="flex items-center justify-between bg-[#F9F7FC] rounded-2xl p-2 px-3 text-[11px] font-bold text-[#555]">
              <span>🥇 ${lead.top3[0]?.name || 'Leo'}</span>
              <span>🥈 ${lead.top3[1]?.name || 'Emma'}</span>
              <span>🥉 ${lead.top3[2]?.name || 'Noah'}</span>
            </div>
          </div>
        `;

        heroBanner.parentNode.insertBefore(container, heroBanner);
        console.log('Continue Lesson and Mini Leaderboard injected into Hub!');
      }
    }
  }

  // Run on load and after DOM settlements
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(initHubWidgets, 400));
  } else {
    setTimeout(initHubWidgets, 400);
  }
  window.addEventListener('kidobits_wallet_updated', initHubWidgets);
})();'''

new_hub_engine = '''(function() {
  function renderContinueCard(last, lead) {
    let container = document.getElementById('kidobits-continue-lesson-card');
    const heroBanner = Array.from(document.querySelectorAll('button')).find(x => 
      x.textContent.includes('Kidobits Phonics') || x.textContent.includes('เริ่มเรียนโฟนิกส์')
    );
    if (!heroBanner || !heroBanner.parentNode) return;

    if (!container) {
      container = document.createElement('div');
      container.id = 'kidobits-continue-lesson-card';
      container.className = 'w-full my-3 space-y-3';
      heroBanner.parentNode.insertBefore(container, heroBanner);
    }

    const isDone = Boolean(last.done);
    const tagText = isDone ? '✅ เรียนจบแล้ว' : '⚡ เรียนต่อจากครั้งที่แล้ว';
    const subText = isDone ? 'ยอดเยี่ยมมาก! กดเพื่อเริ่มบทต่อไป หรือกดทบทวนบทนี้' : `ขั้นที่ ${last.step || 1} จาก 5 ขั้น · กดเพื่อเล่นต่อทันที`;
    const btnText = isDone ? 'บทต่อไป' : 'เรียนต่อ';
    const targetUrl = (isDone && last.nextLessonId) ? `theme_phonicsLesson.html?lesson=${last.nextLessonId}` : (last.url || `theme_phonicsLesson.html?lesson=${last.lessonId || 'L1.01'}`);
    const percent = last.percent || (isDone ? 100 : 20);

    container.innerHTML = `
      <!-- Continue Lesson Hero Card -->
      <div class="bg-gradient-to-r from-[#6C5CE7] to-[#A29BFE] rounded-[26px] p-4 text-white shadow-md relative overflow-hidden transition-all">
        <div class="flex items-center justify-between mb-2">
          <span class="px-2.5 py-0.5 rounded-full bg-white/20 text-white text-[11px] font-black uppercase tracking-wide flex items-center gap-1.5 backdrop-blur-sm">
            ${tagText}
          </span>
          <span class="text-xs font-bold text-white/90">
            ${last.subject || 'Phonics'}
          </span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <div class="flex-1">
            <h3 class="font-extrabold text-base sm:text-lg leading-tight">${last.title || last.lessonId}</h3>
            <p class="text-xs text-white/80 font-medium mt-0.5">${subText}</p>
          </div>
          <a href="${targetUrl}" class="shrink-0 bg-white text-[#6C5CE7] px-4 py-2.5 rounded-full font-black text-xs shadow-md hover:bg-gray-100 active:scale-95 transition flex items-center gap-1.5">
            <span>${btnText}</span> ▶
          </a>
        </div>
        <div class="w-full h-2 bg-black/15 rounded-full overflow-hidden mt-3">
          <div class="h-full bg-[#55EFC4] rounded-full transition-all duration-500" style="width: ${percent}%"></div>
        </div>
      </div>

      <!-- Mini Leaderboard Card -->
      <div onclick="location.href='theme_leaderboard.html'" class="bg-white border-2 border-[#EBE3F5] rounded-[24px] p-3.5 shadow-sm hover:border-[#6C5CE7] active:scale-[0.99] transition cursor-pointer">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <span class="text-2xl">🏆</span>
            <div>
              <h4 class="font-extrabold text-xs sm:text-sm text-[#2D3436]">Leaderboard สัปดาห์นี้</h4>
              <p class="text-[11px] text-[#636E72] font-semibold">
                อันดับของคุณ: <b class="text-[#6C5CE7]">อันดับที่ ${lead.userRank}</b> (⭐ ${lead.userStars} ดาว)
              </p>
            </div>
          </div>
          <span class="text-[11px] font-black text-[#6C5CE7] bg-[#F3EFFF] px-2.5 py-1 rounded-full">
            ดูอันดับ →
          </span>
        </div>
        <div class="flex items-center justify-between bg-[#F9F7FC] rounded-2xl p-2 px-3 text-[11px] font-bold text-[#555]">
          <span>🥇 ${lead.top3[0]?.name || 'Leo'}</span>
          <span>🥈 ${lead.top3[1]?.name || 'Emma'}</span>
          <span>🥉 ${lead.top3[2]?.name || 'Noah'}</span>
        </div>
      </div>
    `;
  }

  async function initHubWidgets() {
    if (!window.KidobitsWallet) return;
    const user = KidobitsWallet.getUser();
    const lead = KidobitsWallet.getLeaderboard();

    // 1. Update Header Counters
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

    // 2. Render initial cached card
    const initialLast = user.lastLesson || {
      subject: 'Phonics',
      lessonId: 'L1.01',
      title: 'Level 1: -at family',
      url: 'theme_phonicsLesson.html?lesson=L1.01',
      percent: 20
    };
    renderContinueCard(initialLast, lead);

    // 3. Asynchronously fetch latest progress from API server
    try {
      const apiLatest = await KidobitsWallet.fetchLatestProgress(user.userId || 'guest');
      if (apiLatest) {
        renderContinueCard(apiLatest, lead);
      }
    } catch(e) {
      console.warn('Failed to sync latest progress from API:', e);
    }
  }

  // Run on load and after DOM settlements
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(initHubWidgets, 400));
  } else {
    setTimeout(initHubWidgets, 400);
  }
  window.addEventListener('kidobits_wallet_updated', initHubWidgets);
})();'''

if old_hub_engine in home_html:
    home_html = home_html.replace(old_hub_engine, new_hub_engine)
    with open('/tmp/theme_home.html', 'w', encoding='utf-8') as f:
        f.write(home_html)
    print("Patched theme_home.html successfully")
else:
    print("Could not match old_hub_engine in theme_home.html")

# =========================================================================
# 2. PATCH theme_phonicsLesson.html
# =========================================================================
lesson_path = '/var/www/kidobits/theme/theme_phonicsLesson.html'
with open(lesson_path, 'r', encoding='utf-8') as f:
    lesson_html = f.read()

# Auto-jump to step if query parameter exists
old_start = '''    // Start Lesson With Audio Unlock
    function startLessonWithAudio() {
      unlockAudio();
      const cover = document.getElementById('start-cover');
      if (cover) cover.classList.add('gone');
      openSession(LID);
    }'''

new_start = '''    // Start Lesson With Audio Unlock & Auto-Resume
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

if old_start in lesson_html:
    lesson_html = lesson_html.replace(old_start, new_start)
    print("Patched startLessonWithAudio in theme_phonicsLesson.html")

# Sync progress on openSession
old_open = '''        currentSessionId = data.session; window.currentSessionId = currentSessionId;
        currentItem = data.item; window.currentItem = currentItem;
        currentExpect = data.expect;
        currentScript = data.script || [];
        currentStepNo = (data.progress && data.progress.step) ? data.progress.step : 1;
        totalStepCount = (data.progress && data.progress.step_count) ? data.progress.step_count : 5;'''

new_open = '''        currentSessionId = data.session; window.currentSessionId = currentSessionId;
        currentItem = data.item; window.currentItem = currentItem;
        currentExpect = data.expect;
        currentScript = data.script || [];
        currentStepNo = (data.progress && data.progress.step) ? data.progress.step : 1;
        totalStepCount = (data.progress && data.progress.step_count) ? data.progress.step_count : 5;

        // Sync progress to API
        try {
          if (window.KidobitsWallet) {
            KidobitsWallet.saveProgress({
              lessonId: LID,
              step: currentStepNo,
              itemIndex: (currentItem ? currentItem.index || 0 : 0),
              totalSteps: totalStepCount,
              done: false
            });
          }
        } catch(e) {}'''

if old_open in lesson_html:
    lesson_html = lesson_html.replace(old_open, new_open)
    print("Patched openSession in theme_phonicsLesson.html")

# Sync progress on advanceNextItem
old_adv = '''        renderStepTabs();
        renderCurrentStep();'''

new_adv = '''        renderStepTabs();
        renderCurrentStep();

        // Sync progress to API
        try {
          if (window.KidobitsWallet) {
            KidobitsWallet.saveProgress({
              lessonId: LID,
              step: currentStepNo,
              itemIndex: (currentItem ? currentItem.index || 0 : 0),
              totalSteps: totalStepCount,
              done: false
            });
          }
        } catch(e) {}'''

if old_adv in lesson_html:
    lesson_html = lesson_html.replace(old_adv, new_adv, 1) # first match
    print("Patched advanceNextItem in theme_phonicsLesson.html")

with open('/tmp/theme_phonicsLesson.html', 'w', encoding='utf-8') as f:
    f.write(lesson_html)

# =========================================================================
# 3. PATCH v2/lesson.html (Sync v2 progress to Continue API)
# =========================================================================
v2_path = '/var/www/kidobits/v2/lesson.html'
with open(v2_path, 'r', encoding='utf-8') as f:
    v2_html = f.read()

old_v2_save = '''    all.__last = LID;
    localStorage.setItem(PKEY, JSON.stringify(all));
  }catch(e){}
}'''

new_v2_save = '''    all.__last = LID;
    localStorage.setItem(PKEY, JSON.stringify(all));
  }catch(e){}
  try {
    fetch('/kidobits/api/progress/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: 'guest',
        lesson_id: LID,
        subject: 'Phonics',
        step: (STATE.step != null ? STATE.step + 1 : 1),
        item_index: STATE.i || 0,
        done: (STATE.step >= 4),
        url: `v2/lesson.html?id=${LID}&lv=${typeof LV !== 'undefined' ? LV : 1}`
      })
    }).catch(()=>{});
  } catch(e){}
}'''

if old_v2_save in v2_html:
    v2_html = v2_html.replace(old_v2_save, new_v2_save)
    with open('/tmp/v2_lesson.html', 'w', encoding='utf-8') as f:
        f.write(v2_html)
    print("Patched v2/lesson.html successfully")
else:
    print("Could not match old_v2_save in v2/lesson.html")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_frontends.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/patch_frontends.py")
print("Patch stdout:\n", stdout.read().decode())
print("Patch stderr:\n", stderr.read().decode())

# Move files into place with sudo
stdin, stdout, stderr = ssh.exec_command("""
echo 'OpenHands@ERP2026' | sudo -S cp /tmp/theme_home.html /var/www/kidobits/theme/theme_home.html
echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_home.html
echo 'OpenHands@ERP2026' | sudo -S cp /tmp/theme_phonicsLesson.html /var/www/kidobits/theme/theme_phonicsLesson.html
echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_phonicsLesson.html
if [ -f /tmp/v2_lesson.html ]; then
  echo 'OpenHands@ERP2026' | sudo -S cp /tmp/v2_lesson.html /var/www/kidobits/v2/lesson.html
  echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/v2/lesson.html
fi
""")
print("Move stdout:\n", stdout.read().decode())
print("Move stderr:\n", stderr.read().decode())

ssh.close()
