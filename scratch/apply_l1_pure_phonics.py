with open('scratch/theme_phonicsLesson_l2.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Helper function check
helper_is_level1 = """    function checkIsLevel1() {
      const lid = (currentItem && currentItem.lesson_id) || new URLSearchParams(location.search).get('id') || '';
      const lv = (currentItem && currentItem.level) || 0;
      return lv === 1 || lid.toUpperCase().startsWith('L1');
    }
"""

# Insert checkIsLevel1 right above playLetterSound
target_pos = "    // Helper: Play isolated phonics sound (Active for Levels 1, 2, and 3 with safe fallback)"
replacement_pos = helper_is_level1 + "\n" + target_pos

content = content.replace(target_pos, replacement_pos, 1)

# 1. Update runTeacherSpellDemo to NOT speak the full word in Level 1
old_demo_end = """        } else {
          // Speak full target word
          setTimeout(() => {
            if (currentItem && currentItem.step === 1) {
              playAudio(`word_${word}.mp3`, `🔊 ${word}`);
            }
          }, 400);
        }"""

new_demo_end = """        } else {
          // For Level 1, keep pure phonics sound without spoiler full word
          if (!checkIsLevel1()) {
            setTimeout(() => {
              if (currentItem && currentItem.step === 1) {
                playAudio(`word_${word}.mp3`, `🔊 ${word}`);
              }
            }, 400);
          }
        }"""

content = content.replace(old_demo_end, new_demo_end, 1)

# 2. Update playAudioScript call sites in Step 1 to filter out word_ in Level 1
# Call site 1 (line 593 in startLesson)
old_call1 = """        // Play initial audio script from API
        playAudioScript(currentScript, () => {"""

new_call1 = """        // Play initial audio script from API (Filter out word spoiler for Level 1 Step 1)
        const script1 = (currentItem && currentItem.step === 1 && checkIsLevel1())
          ? (currentScript || []).filter(it => !String(typeof it === 'string' ? it : (it.say || '')).includes('word_'))
          : currentScript;
        playAudioScript(script1, () => {"""

content = content.replace(old_call1, new_call1, 1)

# Call site 2 (line 700 in submitAnswer)
old_call2 = """        // Play audio script of next item
        playAudioScript(currentScript, () => {"""

new_call2 = """        // Play audio script of next item (Filter out word spoiler for Level 1 Step 1)
        const script2 = (currentItem && currentItem.step === 1 && checkIsLevel1())
          ? (currentScript || []).filter(it => !String(typeof it === 'string' ? it : (it.say || '')).includes('word_'))
          : currentScript;
        playAudioScript(script2, () => {"""

content = content.replace(old_call2, new_call2, 1)

# Call site 3 (line 745 in changeStep)
old_call3 = """        playAudioScript(currentScript, () => {
          if (currentItem && currentItem.step === 1) {"""

new_call3 = """        const script3 = (currentItem && currentItem.step === 1 && checkIsLevel1())
          ? (currentScript || []).filter(it => !String(typeof it === 'string' ? it : (it.say || '')).includes('word_'))
          : currentScript;
        playAudioScript(script3, () => {
          if (currentItem && currentItem.step === 1) {"""

content = content.replace(old_call3, new_call3, 1)

# 3. Update replayCurrentScript
old_replay = """    function replayCurrentScript() {
      unlockAudio();
      if (currentScript && currentScript.length) {"""

new_replay = """    function replayCurrentScript() {
      unlockAudio();
      if (currentItem && currentItem.step === 1 && checkIsLevel1()) {
        runTeacherSpellDemo();
        return;
      }
      if (currentScript && currentScript.length) {"""

content = content.replace(old_replay, new_replay, 1)

# 4. Update Step 1 Button in renderCurrentStep
old_btn = """          <div>
            <button onclick="playTargetWord()" class="bg-[#FFC93C] text-black px-7 py-2.5 rounded-full font-extrabold text-sm shadow hover:bg-[#FFB82E] active:scale-95 transition">
              🔊 ฟังคำนี้
            </button>
          </div>"""

new_btn = """          <div>
            <button onclick="${checkIsLevel1() ? 'runTeacherSpellDemo()' : 'playTargetWord()'}" class="bg-[#FFC93C] text-black px-7 py-2.5 rounded-full font-extrabold text-sm shadow hover:bg-[#FFB82E] active:scale-95 transition cursor-pointer">
              🔊 ${checkIsLevel1() ? 'ฟังครูสะกด' : 'ฟังคำนี้'}
            </button>
          </div>"""

content = content.replace(old_btn, new_btn, 1)

with open('scratch/theme_phonicsLesson_l1_spelling.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Saved scratch/theme_phonicsLesson_l1_spelling.html")
