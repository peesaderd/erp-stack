with open('scratch/theme_phonicsLesson.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Define playLetterSound right above runTeacherSpellDemo
target_spell_demo = "    // Teacher Spell Demo in Step 1\n    function runTeacherSpellDemo() {"

replacement_spell_demo = """    // Helper: Play isolated phonics sound (Active for Level 3, legacy untouched for L1 & L2)
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
    }

    // Teacher Spell Demo in Step 1
    function runTeacherSpellDemo() {"""

if target_spell_demo in content:
    content = content.replace(target_spell_demo, replacement_spell_demo, 1)
    print("Added playLetterSound helper.")
else:
    print("ERROR: target_spell_demo not found!")

# 2. Update line 785 in runTeacherSpellDemo
target_demo_call = "playAudio(`sp_${l.toLowerCase()}.mp3`, `เสียง /${l.toLowerCase()}/`, () => {"
replacement_demo_call = "playLetterSound(l, () => {"

if target_demo_call in content:
    content = content.replace(target_demo_call, replacement_demo_call, 1)
    print("Updated teacher demo call to playLetterSound.")
else:
    print("ERROR: target_demo_call not found!")

# 3. Update line 1059 in handleTypeLetter
target_type_call = "playAudio(`sp_${l.toLowerCase()}.mp3`, `เสียง /${l.toLowerCase()}/`);"
replacement_type_call = "playLetterSound(l);"

if target_type_call in content:
    content = content.replace(target_type_call, replacement_type_call, 1)
    print("Updated handleTypeLetter call to playLetterSound.")
else:
    print("ERROR: target_type_call not found!")

with open('scratch/theme_phonicsLesson_updated.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Saved scratch/theme_phonicsLesson_updated.html")
