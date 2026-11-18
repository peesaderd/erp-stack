import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

update_script = """
with open('/var/www/kidobits/theme/theme_phonicsLesson.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update VAD constants
old_vad = '''    const STT_URL = '/kidobits/stt';
    const MIN_SPEECH_MS = 350;
    const VOICE_LO_HZ = 200;
    const SPEECH_RMS = 0.045;
    const REC_WINDOW_MS = 6000;
    const SILENCE_HOLD_MS = 900;
    const NO_SPEECH_MS = 4500;'''

new_vad = '''    const STT_URL = '/kidobits/stt';
    const MIN_SPEECH_MS = 200;
    const VOICE_LO_HZ = 200;
    const SPEECH_RMS = 0.030;
    const REC_WINDOW_MS = 5000;
    const SILENCE_HOLD_MS = 600;
    const NO_SPEECH_MS = 4500;'''

assert old_vad in content, "old_vad not found"
content = content.replace(old_vad, new_vad)

# 2. Update advanceNextItem and add jumpToStep
old_adv = '''    async function advanceNextItem() {
      if (!currentSessionId) return;
      try {
        const res = await fetch(`${API_BASE}/session/advance`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session: currentSessionId })
        });
        const data = await res.json();
        if (!data || !data.ok) return;

        if (data.done) {
          renderSummary();
          return;
        }

        currentItem = data.item; window.currentItem = currentItem;
        currentExpect = data.expect;
        currentScript = data.script || [];
        currentStepNo = (data.progress && data.progress.step) ? data.progress.step : currentStepNo;

        typedLetters = [];
        isCorrect = false;

        renderStepTabs();
        renderCurrentStep();

        // Play audio script of next item
        playAudioScript(currentScript, () => {
          if (currentItem && currentItem.step === 1) {
            runTeacherSpellDemo();
          } else if (currentItem && currentItem.step === 4) {
            setTimeout(startMicStep4, 400);
          } else if (currentItem && currentItem.step === 5) {
            setTimeout(startMicStep5, 400);
          }
        });
      } catch (err) {
        console.error('Advance error:', err);
      }
    }'''

new_adv = '''    async function advanceNextItem(force = false) {
      if (!currentSessionId) return;
      stopAllAudio();
      micAttemptId++;
      try {
        const res = await fetch(`${API_BASE}/session/advance`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session: currentSessionId, force: !!force })
        });
        const data = await res.json();
        if (!data || !data.ok) {
          if (!force) {
            return advanceNextItem(true);
          }
          return;
        }

        if (data.done) {
          renderSummary();
          return;
        }

        currentItem = data.item; window.currentItem = currentItem;
        currentExpect = data.expect;
        currentScript = data.script || [];
        currentStepNo = (data.progress && data.progress.step) ? data.progress.step : currentStepNo;

        typedLetters = [];
        isCorrect = false;

        renderStepTabs();
        renderCurrentStep();

        // Play audio script of next item
        playAudioScript(currentScript, () => {
          if (currentItem && currentItem.step === 1) {
            runTeacherSpellDemo();
          } else if (currentItem && currentItem.step === 4) {
            setTimeout(startMicStep4, 400);
          } else if (currentItem && currentItem.step === 5) {
            setTimeout(startMicStep5, 400);
          }
        });
      } catch (err) {
        console.error('Advance error:', err);
      }
    }

    async function jumpToStep(targetStep) {
      if (!currentSessionId) return;
      stopAllAudio();
      micAttemptId++;
      try {
        const res = await fetch(`${API_BASE}/session/jump`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session: currentSessionId, step: targetStep, index: 0 })
        });
        const data = await res.json();
        if (!data || !data.ok) {
          console.warn('Jump rejected:', data);
          return;
        }

        currentItem = data.item; window.currentItem = currentItem;
        currentExpect = data.expect;
        currentScript = data.script || [];
        currentStepNo = (data.progress && data.progress.step) ? data.progress.step : currentStepNo;

        typedLetters = [];
        isCorrect = false;

        renderStepTabs();
        renderCurrentStep();

        playAudioScript(currentScript, () => {
          if (currentItem && currentItem.step === 1) {
            runTeacherSpellDemo();
          } else if (currentItem && currentItem.step === 4) {
            setTimeout(startMicStep4, 400);
          } else if (currentItem && currentItem.step === 5) {
            setTimeout(startMicStep5, 400);
          }
        });
      } catch (err) {
        console.error('Jump error:', err);
      }
    }'''

assert old_adv in content, "old_adv not found"
content = content.replace(old_adv, new_adv)

# 3. Update renderStepTabs
old_tabs = '''    function renderStepTabs() {
      const tabsEl = document.getElementById('step-tabs');
      const curStepIdx = (currentItem ? currentItem.step : 1) - 1;

      tabsEl.innerHTML = STEPS.map((s, idx) => {
        const isActive = (idx === curStepIdx);
        const isDone = completedSteps.includes(idx);
        const activeBg = isLv2 ? "bg-[#7ED9A8] text-white shadow-sm" : "bg-[#8B7CFF] text-white shadow-sm";
        const doneBg = "bg-[#D9F8E7] text-[#1B9A62] border border-[#BDE8CC]";
        const idleBg = "bg-white border border-[#EBE3F5] text-[#5B4B8A]";

        return `
          <button class="shrink-0 px-3.5 py-1.5 rounded-full text-xs font-extrabold transition ${isActive ? activeBg : isDone ? doneBg : idleBg}">
            ${idx + 1}. ${s} ${isDone && !isActive ? '✓' : ''}
          </button>
        `;
      }).join('');'''

new_tabs = '''    function renderStepTabs() {
      const tabsEl = document.getElementById('step-tabs');
      const curStepIdx = (currentItem ? currentItem.step : 1) - 1;

      tabsEl.innerHTML = STEPS.map((s, idx) => {
        const stepNum = idx + 1;
        const isActive = (idx === curStepIdx);
        const isDone = completedSteps.includes(idx);
        const activeBg = isLv2 ? "bg-[#7ED9A8] text-white shadow-sm ring-2 ring-[#1B9A62]" : "bg-[#8B7CFF] text-white shadow-sm ring-2 ring-[#5B4B8A]";
        const doneBg = "bg-[#D9F8E7] text-[#1B9A62] border border-[#BDE8CC] hover:bg-[#c2f3d6]";
        const idleBg = "bg-white border border-[#EBE3F5] text-[#5B4B8A] hover:bg-[#F4F1FA]";

        return `
          <button onclick="jumpToStep(${stepNum})" class="shrink-0 px-3.5 py-1.5 rounded-full text-xs font-extrabold cursor-pointer transition active:scale-95 ${isActive ? activeBg : isDone ? doneBg : idleBg}">
            ${stepNum}. ${s} ${isDone && !isActive ? '✓' : ''}
          </button>
        `;
      }).join('');'''

assert old_tabs in content, "old_tabs not found"
content = content.replace(old_tabs, new_tabs)

# 4. Update handleNext
old_handle_next = '''    function handleNext() {
      advanceNextItem();
    }'''

new_handle_next = '''    function handleNext() {
      advanceNextItem(true);
    }'''

assert old_handle_next in content, "old_handle_next not found"
content = content.replace(old_handle_next, new_handle_next)

# 5. Update startMicStep4 matching
old_hit = "const isHit = (heard === target) || res.fuzzy_ok || (heard.includes(target));"
new_hit = "const heardTokens = heard.split(/\\\\s+/).filter(Boolean);\\n      const isHit = (heard === target) || res.fuzzy_ok || (heard.includes(target)) || heardTokens.includes(target);"

assert old_hit in content, "old_hit not found"
content = content.replace(old_hit, new_hit)

with open('/tmp/theme_phonicsLesson.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS: HTML modified and saved to /tmp/theme_phonicsLesson.html")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_html2.py', 'w') as f:
    f.write(update_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/patch_html2.py")
print("patch out:", stdout.read().decode())
print("patch err:", stderr.read().decode())

# Copy to /var/www/kidobits/theme/theme_phonicsLesson.html
stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S cp /tmp/theme_phonicsLesson.html /var/www/kidobits/theme/theme_phonicsLesson.html")
print("cp:", stdout.read().decode(), stderr.read().decode())

stdin, stdout, stderr = ssh.exec_command("ls -la /var/www/kidobits/theme/theme_phonicsLesson.html")
print("file stat:", stdout.read().decode())

ssh.close()
