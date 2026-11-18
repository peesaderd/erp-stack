import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_patcher = """
import re

# =========================================================================
# 1. PATCH theme_phonicsLesson.html
# =========================================================================
lesson_path = '/var/www/kidobits/theme/theme_phonicsLesson.html'
with open(lesson_path, 'r', encoding='utf-8') as f:
    lesson_html = f.read()

# Add script include if not present
if 'kidobits_wallet.js' not in lesson_html:
    lesson_html = lesson_html.replace('</head>', '<script src="/js/kidobits_wallet.js"></script>\\n</head>')

# Add reward call in step 5 complete
if 'KidobitsWallet.addReward' not in lesson_html:
    # Hook into renderStep5
    step5_pattern = 'function renderStep5() {'
    step5_hook = '''function renderStep5() {
      try {
        if (window.KidobitsWallet) {
          KidobitsWallet.addReward(10, 20, {
            subject: 'Phonics',
            subjectIcon: '🔤',
            lessonId: (typeof curLessonId !== 'undefined' ? curLessonId : 'L1.01'),
            title: 'Phonics ' + (typeof curLessonId !== 'undefined' ? curLessonId : 'Lesson'),
            url: 'theme_phonicsLesson.html?lesson=' + (typeof curLessonId !== 'undefined' ? curLessonId : 'L1.01')
          });
        }
      } catch(e) { console.warn('Wallet reward hook error', e); }
'''
    lesson_html = lesson_html.replace(step5_pattern, step5_hook)

    # Add visual reward badge in modal
    reward_badge_ui = '''
          <div class="flex items-center justify-center gap-3 my-3">
            <span class="bg-[#FFF8E7] border border-[#FFE082] px-3.5 py-1.5 rounded-full text-xs font-black text-[#FF8F00] shadow-sm animate-bounce">
              ⭐ +10 ดาว
            </span>
            <span class="bg-[#E8F5E9] border border-[#A5D6A7] px-3.5 py-1.5 rounded-full text-xs font-black text-[#2E7D32] shadow-sm animate-bounce">
              🪙 +20 เหรียญ
            </span>
          </div>
'''
    if '🔥 7 วันต่อเนื่อง' in lesson_html:
        lesson_html = lesson_html.replace('🔥 7 วันต่อเนื่อง</span>', '🔥 7 วันต่อเนื่อง</span>\\n' + reward_badge_ui)

with open(lesson_path, 'w', encoding='utf-8') as f:
    f.write(lesson_html)
print("1. Patched theme_phonicsLesson.html successfully")

# =========================================================================
# 2. PATCH theme_home.html (The Hub: Continue Lesson + Mini Leaderboard)
# =========================================================================
home_path = '/var/www/kidobits/theme/theme_home.html'
with open(home_path, 'r', encoding='utf-8') as f:
    home_html = f.read()

# Add wallet include
if 'kidobits_wallet.js' not in home_html:
    home_html = home_html.replace('</head>', '<script src="/js/kidobits_wallet.js"></script>\\n</head>')

# Add Hub Dynamic Widgets (Continue Lesson & Mini Leaderboard)
hub_enhancement = '''
<script>
// --- Kidobits Hub Dynamic Engine (Continue Lesson, Live Stats & Leaderboard) ---
(function() {
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
})();
</script>
'''

if 'kidobits-continue-lesson-card' not in home_html:
    home_html = home_html.replace('</body>', hub_enhancement + '\\n</body>')

with open(home_path, 'w', encoding='utf-8') as f:
    f.write(home_html)
print("2. Patched theme_home.html successfully")

# =========================================================================
# 3. PATCH theme_leaderboard.html (Dynamic Ranking from Wallet)
# =========================================================================
lead_path = '/var/www/kidobits/theme/theme_leaderboard.html'
with open(lead_path, 'r', encoding='utf-8') as f:
    lead_html = f.read()

if 'kidobits_wallet.js' not in lead_html:
    lead_html = lead_html.replace('</head>', '<script src="/js/kidobits_wallet.js"></script>\\n</head>')

lead_script = '''
<script>
(function() {
  function renderLiveLeaderboard() {
    if (!window.KidobitsWallet) return;
    const lead = KidobitsWallet.getLeaderboard();

    // Check if container already injected
    if (document.getElementById('live-leaderboard-container')) return;

    // Find main content container
    const root = document.getElementById('root');
    if (!root) return;

    // Create a live leaderboard overlay/replacement
    const overlay = document.createElement('div');
    overlay.id = 'live-leaderboard-container';
    overlay.className = 'w-full max-w-[430px] mx-auto p-4 pb-24 font-sans';
    
    let listRows = '';
    lead.ranking.forEach((r, idx) => {
      const isTop3 = idx < 3;
      const rankBadge = idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : `${idx + 1}.`;
      const isMe = r.isUser;
      const rowBg = isMe ? 'bg-[#F3EFFF] border-2 border-[#6C5CE7] shadow-sm' : 'bg-white border border-[#EBE3F5]';

      listRows += `
        <div class="flex items-center justify-between p-3 rounded-2xl ${rowBg} mb-2 transition active:scale-[0.99]">
          <div class="flex items-center gap-3">
            <span class="w-6 font-black text-center text-sm ${isMe ? 'text-[#6C5CE7]' : 'text-gray-500'}">${rankBadge}</span>
            <span class="w-9 h-9 rounded-full bg-[#FFF0F5] flex items-center justify-center text-lg border border-[#F3EDF8]">
              ${r.avatar || '👧'}
            </span>
            <div>
              <b class="text-xs sm:text-sm font-extrabold ${isMe ? 'text-[#6C5CE7]' : 'text-gray-800'}">${r.name}</b>
              ${isMe ? '<span class="block text-[10px] text-[#8075FF] font-black">อันดับของคุณ</span>' : ''}
            </div>
          </div>
          <span class="font-black text-xs sm:text-sm text-[#FF8F00] bg-[#FFF8E7] px-3 py-1 rounded-full border border-[#FFE082]">
            ⭐ ${r.stars.toLocaleString()}
          </span>
        </div>
      `;
    });

    overlay.innerHTML = `
      <!-- Header -->
      <div class="flex items-center justify-between mb-4">
        <button onclick="location.href='theme_home.html'" class="bg-white border border-[#EBE3F5] px-3.5 py-1.5 rounded-full text-xs font-extrabold text-[#5B4B8A] shadow-sm hover:bg-[#F9F5FF] active:scale-95 transition">
          ← กลับ Hub
        </button>
        <h2 class="font-extrabold text-base text-[#2D3436]">Leaderboard 🏆</h2>
        <div class="w-12"></div>
      </div>

      <!-- Top 3 Podium Card -->
      <div class="bg-gradient-to-br from-[#FFD32A]/20 via-[#FFA801]/10 to-transparent border border-[#FFEAA7] rounded-[28px] p-4 text-center mb-4">
        <h3 class="font-black text-sm text-[#D35400] mb-3">🌟 Top 3 ยอดนักเรียนประจำสัปดาห์</h3>
        <div class="flex items-end justify-center gap-3">
          <!-- Rank 2 -->
          <div class="flex flex-col items-center">
            <span class="text-xl">🥈</span>
            <div class="w-11 h-11 rounded-full bg-white shadow-sm flex items-center justify-center text-xl border-2 border-slate-300">
              ${lead.top3[1]?.avatar || '🐱'}
            </div>
            <span class="text-[11px] font-bold mt-1 text-gray-700">${lead.top3[1]?.name || 'Emma'}</span>
            <span class="text-[10px] font-black text-[#FF8F00]">⭐ ${lead.top3[1]?.stars || 1150}</span>
            <div class="h-14 w-16 bg-slate-200/80 rounded-t-xl mt-1"></div>
          </div>
          <!-- Rank 1 -->
          <div class="flex flex-col items-center">
            <span class="text-2xl animate-bounce">👑</span>
            <div class="w-14 h-14 rounded-full bg-white shadow-md flex items-center justify-center text-2xl border-4 border-[#FFD32A]">
              ${lead.top3[0]?.avatar || '🦁'}
            </div>
            <span class="text-xs font-black mt-1 text-[#D35400]">${lead.top3[0]?.name || 'Leo'}</span>
            <span class="text-[11px] font-black text-[#FF8F00]">⭐ ${lead.top3[0]?.stars || 1280}</span>
            <div class="h-20 w-20 bg-gradient-to-t from-[#FFD32A] to-[#FFEAA7] rounded-t-xl mt-1 flex items-center justify-center text-white font-black text-xs">#1</div>
          </div>
          <!-- Rank 3 -->
          <div class="flex flex-col items-center">
            <span class="text-xl">🥉</span>
            <div class="w-11 h-11 rounded-full bg-white shadow-sm flex items-center justify-center text-xl border-2 border-amber-600/40">
              ${lead.top3[2]?.avatar || '🐶'}
            </div>
            <span class="text-[11px] font-bold mt-1 text-gray-700">${lead.top3[2]?.name || 'Noah'}</span>
            <span class="text-[10px] font-black text-[#FF8F00]">⭐ ${lead.top3[2]?.stars || 980}</span>
            <div class="h-10 w-16 bg-amber-100 rounded-t-xl mt-1"></div>
          </div>
        </div>
      </div>

      <!-- Ranking List -->
      <div class="space-y-1">
        ${listRows}
      </div>

      <!-- Sticky Bottom My Rank Bar -->
      <div class="fixed bottom-3 left-3 right-3 max-w-[406px] mx-auto bg-black text-white p-3.5 px-4 rounded-full shadow-2xl flex items-center justify-between z-30">
        <div class="flex items-center gap-2">
          <span class="text-lg">⭐</span>
          <div>
            <span class="text-[10px] text-gray-300 font-bold block leading-none">อันดับของคุณในสัปดาห์นี้</span>
            <b class="text-sm font-black text-[#55EFC4]">อันดับที่ ${lead.userRank} (คุณ)</b>
          </div>
        </div>
        <button onclick="location.href='theme_phonicsHome.html'" class="bg-[#6C5CE7] hover:bg-[#5b4cc4] text-white px-4 py-2 rounded-full font-black text-xs active:scale-95 transition">
          สะสมดาวเพิ่ม ▶
        </button>
      </div>
    `;

    // Replace or overlay
    root.style.display = 'none';
    document.body.appendChild(overlay);
    console.log('Dynamic Leaderboard rendered!');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(renderLiveLeaderboard, 400));
  } else {
    setTimeout(renderLiveLeaderboard, 400);
  }
})();
</script>
'''

if 'live-leaderboard-container' not in lead_html:
    lead_html = lead_html.replace('</body>', lead_script + '\\n</body>')

with open(lead_path, 'w', encoding='utf-8') as f:
    f.write(lead_html)
print("3. Patched theme_leaderboard.html successfully")

# =========================================================================
# 4. PATCH theme_shop.html (Dynamic Coins & Real Purchase)
# =========================================================================
shop_path = '/var/www/kidobits/theme/theme_shop.html'
with open(shop_path, 'r', encoding='utf-8') as f:
    shop_html = f.read()

if 'kidobits_wallet.js' not in shop_html:
    shop_html = shop_html.replace('</head>', '<script src="/js/kidobits_wallet.js"></script>\\n</head>')

shop_script = '''
<script>
(function() {
  function renderLiveShop() {
    if (!window.KidobitsWallet) return;
    const user = KidobitsWallet.getUser();

    if (document.getElementById('live-shop-container')) return;
    const root = document.getElementById('root');
    if (!root) return;

    const items = [
      { id: 'hat_starry', name: '🎩 หมวกดวงดาววิเศษ', desc: 'หมวกประกายดาวสุดเท่สำหรับอวาตาร์ของคุณ', price: 100, type: 'hat', icon: '🎩' },
      { id: 'hat_crown', name: '👑 มงกุฎเจ้าชาย/เจ้าหญิง', desc: 'มงกุฎทองคำประดับอัญมณีเจิดจรัส', price: 200, type: 'hat', icon: '👑' },
      { id: 'hat_gamer', name: '🎧 หูฟังเกมเมอร์นีออน', desc: 'หูฟังเรืองแสง RGB โฟนิกส์สุดคูล', price: 150, type: 'hat', icon: '🎧' },
      { id: 'pet_cat', name: '🐱 สัตว์เลี้ยง: เจ้าเหมียวส้ม', desc: 'เพื่อนคู่ใจเดินตามไปทุกบทเรียน', price: 180, type: 'pet', icon: '🐱' },
      { id: 'theme_space', name: '🚀 ธีม: ท่องอวกาศ', desc: 'เปลี่ยนฉากหลังหน้า Hub เป็นดวงดาวระยิบระยับ', price: 250, type: 'theme', icon: '🚀' }
    ];

    let itemsHtml = '';
    items.forEach(it => {
      const isOwned = user.inventory && user.inventory.includes(it.id);
      const isEquipped = user.avatarHat === it.id;
      const canAfford = user.coins >= it.price;

      let btnHtml = '';
      if (isEquipped) {
        btnHtml = `<button class="px-4 py-2 rounded-full font-black text-xs bg-[#E8F5E9] text-[#2E7D32] border border-[#A5D6A7]" disabled>สวมใส่อยู่ ✅</button>`;
      } else if (isOwned) {
        btnHtml = `<button onclick="equipItem('${it.id}')" class="px-4 py-2 rounded-full font-black text-xs bg-black text-white hover:bg-gray-800 active:scale-95 transition">กดสวมใส่</button>`;
      } else if (canAfford) {
        btnHtml = `<button onclick="buyShopItem('${it.id}', ${it.price}, '${it.type}')" class="px-4 py-2 rounded-full font-black text-xs bg-[#FF8F00] text-white hover:bg-[#e68200] active:scale-95 transition shadow-sm">ซื้อ (🪙 ${it.price})</button>`;
      } else {
        btnHtml = `<button class="px-4 py-2 rounded-full font-black text-xs bg-gray-100 text-gray-400 border border-gray-200" disabled>เหรียญไม่พอ (🪙 ${it.price})</button>`;
      }

      itemsHtml += `
        <div class="bg-white border-2 border-[#EBE3F5] rounded-[24px] p-4 flex items-center justify-between gap-3 shadow-sm hover:border-[#6C5CE7] transition mb-3">
          <div class="flex items-center gap-3">
            <span class="w-12 h-12 rounded-2xl bg-[#FFF0F5] flex items-center justify-center text-2xl border border-[#F3EDF8] shadow-inner">
              ${it.icon}
            </span>
            <div>
              <h4 class="font-extrabold text-sm text-[#2D3436]">${it.name}</h4>
              <p class="text-[11px] text-gray-500 font-medium">${it.desc}</p>
              <span class="inline-block font-black text-xs text-[#FF8F00] mt-1">🪙 ${it.price} เหรียญ</span>
            </div>
          </div>
          <div class="shrink-0">
            ${btnHtml}
          </div>
        </div>
      `;
    });

    const overlay = document.createElement('div');
    overlay.id = 'live-shop-container';
    overlay.className = 'w-full max-w-[430px] mx-auto p-4 pb-24 font-sans';
    overlay.innerHTML = `
      <!-- Header -->
      <div class="flex items-center justify-between mb-3">
        <button onclick="location.href='theme_home.html'" class="bg-white border border-[#EBE3F5] px-3.5 py-1.5 rounded-full text-xs font-extrabold text-[#5B4B8A] shadow-sm hover:bg-[#F9F5FF] active:scale-95 transition">
          ← กลับ Hub
        </button>
        <h2 class="font-extrabold text-base text-[#2D3436]">Rewards Shop 🛍️</h2>
        <div class="w-12"></div>
      </div>

      <!-- Coin Balance Card -->
      <div class="bg-gradient-to-r from-[#FF9F43] to-[#FECA57] rounded-[26px] p-4 text-white shadow-md mb-4 flex items-center justify-between">
        <div>
          <span class="text-xs font-bold text-white/90 uppercase tracking-wide">กระเป๋าเหรียญของคุณ</span>
          <h3 class="font-black text-2xl leading-none mt-1">🪙 ${user.coins.toLocaleString()} <span class="text-sm font-bold text-white/90">เหรียญ</span></h3>
          <p class="text-[11px] text-white/80 font-medium mt-1">สะสมได้จากการจบบทเรียนและ Daily Challenge</p>
        </div>
        <button onclick="location.href='theme_phonicsHome.html'" class="bg-white text-[#D35400] px-3.5 py-2 rounded-full font-black text-xs shadow hover:bg-gray-100 active:scale-95 transition">
          หาเหรียญเพิ่ม ▶
        </button>
      </div>

      <!-- Shop Items List -->
      <h3 class="font-black text-xs uppercase tracking-wider text-gray-400 mb-2">ไอเทมสำหรับอวาตาร์ & ธีม</h3>
      <div>
        ${itemsHtml}
      </div>
    `;

    root.style.display = 'none';
    document.body.appendChild(overlay);
    console.log('Dynamic Shop rendered!');
  }

  window.buyShopItem = function(id, price, type) {
    const res = KidobitsWallet.buyItem(id, price, type);
    if (res.success) {
      alert('🎉 ยินดีด้วย! ซื้อไอเทมสำเร็จและสวมใส่ให้อวาตาร์แล้ว');
      location.reload();
    } else {
      alert('⚠️ เหรียญของคุณไม่พอสำหรับไอเทมนี้ เข้าเรียนเพื่อสะสมเหรียญเพิ่มนะ!');
    }
  };

  window.equipItem = function(id) {
    const u = KidobitsWallet.getUser();
    u.avatarHat = id;
    KidobitsWallet.saveUser(u);
    alert('✨ สวมใส่ไอเทมเรียบร้อยแล้ว!');
    location.reload();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(renderLiveShop, 400));
  } else {
    setTimeout(renderLiveShop, 400);
  }
})();
</script>
'''

if 'live-shop-container' not in shop_html:
    shop_html = shop_html.replace('</body>', shop_script + '\\n</body>')

with open(shop_path, 'w', encoding='utf-8') as f:
    f.write(shop_html)
print("4. Patched theme_shop.html successfully")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_leaderboard_reward.py', 'w') as f:
    f.write(remote_patcher)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S python3 /tmp/patch_leaderboard_reward.py")
print(stdout.read().decode('utf-8'))
print(stderr.read().decode('utf-8'))

ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S chown -R www-data:www-data /var/www/kidobits/theme/")
ssh.close()
