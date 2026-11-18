with open('scratch/theme_phonicsLesson_l1.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_func = """    // Helper: Play isolated phonics sound (Active for Level 1 & Level 3, legacy untouched for L2)
    function playLetterSound(l, onEnd) {
      const clean = String(l || '').toLowerCase().trim().replace(/[^a-z0-9]/g, '');
      const lid = (currentItem && currentItem.lesson_id) || new URLSearchParams(location.search).get('id') || '';
      const lv = (currentItem && currentItem.level) || 0;
      const isPhonicsTarget = lv === 1 || lv === 3 || lid.toUpperCase().startsWith('L1') || lid.toUpperCase().startsWith('L3');

      if (isPhonicsTarget) {
        const phonicsUrl = `/kidobits/v2/audio/phonics_bank/ph_${clean}.mp3`;
        playAudio(phonicsUrl, `เสียง /${clean}/`, onEnd);
      } else {
        playAudio(`sp_${clean}.mp3`, `เสียง /${clean}/`, onEnd);
      }
    }"""

new_func = """    // Helper: Play isolated phonics sound (Active for Levels 1, 2, and 3 with safe fallback)
    function playLetterSound(l, onEnd) {
      const clean = String(l || '').toLowerCase().trim().replace(/[^a-z0-9]/g, '');
      const phonicsUrl = `/kidobits/v2/audio/phonics_bank/ph_${clean}.mp3`;
      playAudio(phonicsUrl, `เสียง /${clean}/`, onEnd, () => {
        // Fallback to legacy sp_ if missing
        playAudio(`sp_${clean}.mp3`, `เสียง /${clean}/`, onEnd, onEnd);
      });
    }"""

if old_func in content:
    content = content.replace(old_func, new_func, 1)
    print("Updated playLetterSound for Level 2 (Universal phonics bank with safe fallback).")
else:
    print("ERROR: old_func not found!")

with open('scratch/theme_phonicsLesson_l2.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Saved scratch/theme_phonicsLesson_l2.html")
