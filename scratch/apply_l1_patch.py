with open('scratch/theme_phonicsLesson_updated.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update playLetterSound to support both Level 1 and Level 3
old_play_letter = """    // Helper: Play isolated phonics sound (Active for Level 3, legacy untouched for L1 & L2)
    function playLetterSound(l, onEnd) {
      const clean = String(l || '').toLowerCase().trim().replace(/[^a-z0-9]/g, '');
      const isLevel3 = (currentItem && (currentItem.level === 3 || (currentItem.lesson_id && currentItem.lesson_id.startsWith('L3')))) ||
                       (new URLSearchParams(location.search).get('id') || '').toUpperCase().startsWith('L3');

      if (isLevel3) {
        const phonicsUrl = `/kidobits/v2/audio/phonics_bank/ph_${clean}.mp3`;
        playAudio(phonicsUrl, `เสียง /${clean}/`, onEnd);
      } else {
        playAudio(`sp_${clean}.mp3`, `เสียง /${clean}/`, onEnd);
      }
    }"""

new_play_letter = """    // Helper: Play isolated phonics sound (Active for Level 1 & Level 3, legacy untouched for L2)
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

if old_play_letter in content:
    content = content.replace(old_play_letter, new_play_letter, 1)
    print("Updated playLetterSound for Level 1 & 3.")
else:
    print("ERROR: old_play_letter not found!")

# 2. Add breathing room in handleTypeLetter before submitAnswer
old_submit_block = """      if (currentItem && currentItem.word) {
        if (typedLetters.join('') === currentItem.word) {
          submitAnswer(currentItem.word);
        }
      }"""

new_submit_block = """      if (currentItem && currentItem.word) {
        if (typedLetters.join('') === currentItem.word) {
          // Allow final letter sound to ring out naturally without being cut off
          setTimeout(() => {
            if (typedLetters.join('') === currentItem.word) {
              submitAnswer(currentItem.word);
            }
          }, 350);
        }
      }"""

if old_submit_block in content:
    content = content.replace(old_submit_block, new_submit_block, 1)
    print("Updated handleTypeLetter with 350ms breathing room.")
else:
    print("ERROR: old_submit_block not found!")

# 3. Add breathing room in runTeacherSpellDemo
old_demo_timing = """            idx++;
            setTimeout(spellNext, 250);
          });
        } else {
          // Speak full target word
          setTimeout(() => {
            if (currentItem && currentItem.step === 1) {
              playAudio(`word_${word}.mp3`, `🔊 ${word}`);
            }
          }, 200);"""

new_demo_timing = """            idx++;
            setTimeout(spellNext, 350);
          });
        } else {
          // Speak full target word
          setTimeout(() => {
            if (currentItem && currentItem.step === 1) {
              playAudio(`word_${word}.mp3`, `🔊 ${word}`);
            }
          }, 400);"""

if old_demo_timing in content:
    content = content.replace(old_demo_timing, new_demo_timing, 1)
    print("Updated runTeacherSpellDemo timing.")
else:
    print("ERROR: old_demo_timing not found!")

with open('scratch/theme_phonicsLesson_l1.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Saved scratch/theme_phonicsLesson_l1.html")
