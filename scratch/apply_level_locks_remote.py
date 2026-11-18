import re

print("Starting update for phonics_map and chinese_lobby...")

# 1. Update theme/js/kidobits_curriculum_lock.js to support isChineseTierUnlocked
with open('/var/www/kidobits/theme/js/kidobits_curriculum_lock.js', 'r', encoding='utf-8') as f:
    lock_js = f.read()

tier_fn = """  // Chinese Tier helper (early -> lower -> upper)
  function isChineseTierUnlocked(tierKey) {
    if (isBypass()) return true;
    if (tierKey === 'early' || tierKey === 1) return true;
    const sub = state.chinese || { unlockedLevel: 1 };
    const lv = sub.unlockedLevel || 1;
    if (tierKey === 'lower' || tierKey === 2) return lv >= 2;
    if (tierKey === 'upper' || tierKey === 3) return lv >= 3;
    return false;
  }
"""

if 'isChineseTierUnlocked' not in lock_js:
    lock_js = lock_js.replace('function isLevelUnlocked(', tier_fn + '\n  function isLevelUnlocked(', 1)
    lock_js = lock_js.replace('isLevelUnlocked: isLevelUnlocked,', 'isLevelUnlocked: isLevelUnlocked,\n    isChineseTierUnlocked: isChineseTierUnlocked,', 1)
    with open('/var/www/kidobits/theme/js/kidobits_curriculum_lock.js', 'w', encoding='utf-8') as f:
        f.write(lock_js)
    print("Updated kidobits_curriculum_lock.js with isChineseTierUnlocked")

# 2. Update theme/theme_phonics_map.html
with open('/var/www/kidobits/theme/theme_phonics_map.html', 'r', encoding='utf-8') as f:
    map_html = f.read()

# Add lock script tag if not present
if 'kidobits_curriculum_lock.js' not in map_html:
    map_html = map_html.replace('</body>', '<script src="js/kidobits_curriculum_lock.js"></script>\n</body>', 1)

# Add dynamic lock enforcement script in phonics map
map_lock_script = """  <script>
    document.addEventListener('DOMContentLoaded', function() {
      if (!window.KidobitsLock) return;

      // 1. Level 2 Lock Check
      const lv2Unlocked = KidobitsLock.isLevelUnlocked('phonics', 2);
      const lv2Btn = document.querySelector('a[href="theme_level2.html"]');
      if (!lv2Unlocked && lv2Btn) {
        const lv2Container = lv2Btn.closest('.bg-white.rounded-3xl');
        if (lv2Container) {
          lv2Container.classList.remove('border-orange-500', 'glow-orange');
          lv2Container.classList.add('border-slate-200', 'opacity-85');
          const badge = lv2Container.querySelector('.absolute.top-0.right-0');
          if (badge) {
            badge.className = 'absolute top-0 right-0 bg-slate-400 text-white text-[10px] font-extrabold uppercase px-4 py-1.5 rounded-bl-2xl flex items-center gap-1';
            badge.innerHTML = '<span>🔒</span> <span>ปลดล็อคเมื่อผ่าน Level 1</span>';
          }
        }
        const statusBox = lv2Btn.closest('.flex-shrink-0');
        if (statusBox) {
          const statusText = statusBox.querySelector('.text-\\\\[11px\\\\].text-orange-700') || statusBox.children[2];
          if (statusText) statusText.textContent = '🔒 ต้องผ่าน Level 1 ก่อน';
        }
        const lockBtn = document.createElement('button');
        lockBtn.className = 'w-full bg-slate-200 hover:bg-slate-300 text-slate-500 font-black text-xs py-2.5 px-3 rounded-xl transition shadow block text-center cursor-pointer select-none';
        lockBtn.innerHTML = '🔒 เริ่มเล่น Level 2 (ปลดล็อคเมื่อผ่าน Level 1)';
        lockBtn.onclick = function() {
          KidobitsLock.shakeAndNotify(this, 'Level 2: Fluent Reader', true);
        };
        lv2Btn.parentNode.replaceChild(lockBtn, lv2Btn);
      }

      // 2. Level 3 Lock Check
      const lv3Unlocked = KidobitsLock.isLevelUnlocked('phonics', 3);
      const lv3Btn = document.querySelector('a[href="theme_level3.html"]');
      if (!lv3Unlocked && lv3Btn) {
        const lv3Container = lv3Btn.closest('.bg-white.rounded-3xl');
        if (lv3Container) {
          lv3Container.classList.remove('border-purple-300');
          lv3Container.classList.add('border-slate-200', 'opacity-85');
          const badge = lv3Container.querySelector('.absolute.top-0.right-0');
          if (badge) {
            badge.className = 'absolute top-0 right-0 bg-slate-400 text-white text-[10px] font-extrabold uppercase px-4 py-1.5 rounded-bl-2xl flex items-center gap-1';
            badge.innerHTML = '<span>🔒</span> <span>ปลดล็อคเมื่อผ่าน Level 2</span>';
          }
        }
        const statusBox = lv3Btn.closest('.flex-shrink-0');
        if (statusBox) {
          const statusText = statusBox.querySelector('.text-\\\\[11px\\\\].text-purple-700') || statusBox.children[2];
          if (statusText) statusText.textContent = '🔒 ต้องผ่าน Level 2 ก่อน';
        }
        const lockBtn = document.createElement('button');
        lockBtn.className = 'w-full bg-slate-200 hover:bg-slate-300 text-slate-500 font-black text-xs py-2.5 px-3 rounded-xl transition shadow block text-center cursor-pointer select-none';
        lockBtn.innerHTML = '🔒 เริ่มเล่น Level 3 (ปลดล็อคเมื่อผ่าน Level 2)';
        lockBtn.onclick = function() {
          KidobitsLock.shakeAndNotify(this, 'Level 3: Master Storyteller', true);
        };
        lv3Btn.parentNode.replaceChild(lockBtn, lv3Btn);
      }
    });
  </script>
"""

if 'Level 2 Lock Check' not in map_html:
    map_html = map_html.replace('</body>', map_lock_script + '\n</body>', 1)
    with open('/var/www/kidobits/theme/theme_phonics_map.html', 'w', encoding='utf-8') as f:
        f.write(map_html)
    print("Updated theme_phonics_map.html with Level 2 and Level 3 Lock Check")

# 3. Update theme/theme_chinese_lobby.html
with open('/var/www/kidobits/theme/theme_chinese_lobby.html', 'r', encoding='utf-8') as f:
    chinese_html = f.read()

# In renderLessons(): check tier lock
old_chinese_render = """      tiers.forEach(tier => {
        if (currentFilter !== 'all' && currentFilter !== tier.key) return;

        const items = CHINESE_DATA[tier.key] || [];
        if (items.length === 0) return;"""

new_chinese_render = """      tiers.forEach(tier => {
        if (currentFilter !== 'all' && currentFilter !== tier.key) return;

        const items = CHINESE_DATA[tier.key] || [];
        if (items.length === 0) return;

        const isTierUnlocked = window.KidobitsLock ? KidobitsLock.isChineseTierUnlocked(tier.key) : (tier.key === 'early');"""

if old_chinese_render in chinese_html:
    chinese_html = chinese_html.replace(old_chinese_render, new_chinese_render, 1)

# In items.forEach: check isTierUnlocked
old_chinese_item_lock = """          const lessonIdx = idx + 1;
          const isUnlocked = window.KidobitsLock ? KidobitsLock.isUnlocked('chinese', tier.key, lessonIdx) : (lessonIdx === 1);"""

new_chinese_item_lock = """          const lessonIdx = idx + 1;
          const isUnlocked = isTierUnlocked && (window.KidobitsLock ? KidobitsLock.isUnlocked('chinese', tier.key, lessonIdx) : (lessonIdx === 1));"""

if old_chinese_item_lock in chinese_html:
    chinese_html = chinese_html.replace(old_chinese_item_lock, new_chinese_item_lock, 1)

with open('/var/www/kidobits/theme/theme_chinese_lobby.html', 'w', encoding='utf-8') as f:
    f.write(chinese_html)
print("Updated theme_chinese_lobby.html: lower and upper tiers locked until early tier completed")

print("All updates completed successfully!")
