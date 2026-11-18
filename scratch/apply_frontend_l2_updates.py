import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_code = """
import os
import shutil

# 1. Update theme_phonicsLevel.html
LEVEL_HTML = '/var/www/kidobits/theme/theme_phonicsLevel.html'
shutil.copy2(LEVEL_HTML, '/home/openhands/backups/theme_phonicsLevel.html.bak_l2')

with open(LEVEL_HTML, 'r', encoding='utf-8') as f:
    l_html = f.read()

old_lv2 = '''    const LV2_LESSONS = [
      { n: 1, id: "L2.01", title: "s a t p — first blends", th: "ผสมคำสระ a", chips: ["sat","pat","tap","at"], status: "ยังไม่เล่น" },
      { n: 2, id: "L2.02", title: "i n m — short i", th: "ผสมเสียง i n m", chips: ["pin","sit","tin","tip"], status: "ยังไม่เล่น" },
      { n: 3, id: "L2.03", title: "Short a word family -at", th: "อ่านคำลงท้าย -at", chips: ["cat","hat","mat","bat"], status: "ยังไม่เล่น" },
      { n: 4, id: "L2.04", title: "Short a word family -an", th: "อ่านคำลงท้าย -an", chips: ["can","fan","man","pan"], status: "ยังไม่เล่น" },
      { n: 5, id: "L2.05", title: "Short a word family -ap", th: "อ่านคำลงท้าย -ap", chips: ["cap","map","nap","tap"], status: "ยังไม่เล่น" },
      { n: 6, id: "L2.06", title: "Short e word family -en", th: "อ่านคำลงท้าย -en", chips: ["hen","men","pen","ten"], status: "ยังไม่เล่น" },
      { n: 7, id: "L2.07", title: "Short e word family -et", th: "อ่านคำลงท้าย -et", chips: ["bed","net","pet","wet"], status: "ยังไม่เล่น" },
      { n: 8, id: "L2.08", title: "Short i word family -in", th: "อ่านคำลงท้าย -in", chips: ["bin","fin","pin","win"], status: "ยังไม่เล่น" },
      { n: 9, id: "L2.09", title: "Short i word family -it", th: "อ่านคำลงท้าย -it", chips: ["fit","hit","kit","sit"], status: "ยังไม่เล่น" },
      { n: 10, id: "L2.10", title: "Short o word family -og", th: "อ่านคำลงท้าย -og", chips: ["dog","fog","log","jog"], status: "ยังไม่เล่น" },
      { n: 11, id: "L2.11", title: "Short o word family -op", th: "อ่านคำลงท้าย -op", chips: ["hop","mop","pop","top"], status: "ยังไม่เล่น" },
      { n: 12, id: "L2.12", title: "Short u word family -ug", th: "อ่านคำลงท้าย -ug", chips: ["bug","hug","mug","rug"], status: "ยังไม่เล่น" },
      { n: 13, id: "L2.13", title: "Short u word family -un", th: "อ่านคำลงท้าย -un", chips: ["bun","fun","run","sun"], status: "ยังไม่เล่น" },
      { n: 14, id: "L2.14", title: "Mixed Short Vowels 1", th: "ทบทวนสระผสม 1", chips: ["bag","beg","big","bog","bug"], status: "ยังไม่เล่น" },
      { n: 15, id: "L2.15", title: "Mixed Short Vowels 2", th: "ทบทวนสระผสม 2", chips: ["cat","cot","cut","fan","fin"], status: "ยังไม่เล่น" },
      { n: 16, id: "L2.16", title: "Level 2 Review & Story", th: "สรุป Level 2 & นิทาน", chips: ["fat","cat","sat","mat"], status: "ยังไม่เล่น" }
    ];'''

new_lv2 = '''    const LV2_LESSONS = [
      { n: 1, id: "L2.01", title: "s a t p — first blends", th: "ผสมคำสระ a", chips: ["sat","pat","tap","at"], status: "ยังไม่เล่น" },
      { n: 2, id: "L2.02", title: "i n m — short i", th: "ผสมเสียง i n m", chips: ["pin","sit","tin","tip"], status: "ยังไม่เล่น" },
      { n: 3, id: "L2.03", title: "Short a word family -at", th: "อ่านคำลงท้าย -at", chips: ["cat","hat","mat","bat"], status: "ยังไม่เล่น" },
      { n: 4, id: "L2.04", title: "Short a word family -an", th: "อ่านคำลงท้าย -an", chips: ["can","fan","man","pan"], status: "ยังไม่เล่น" },
      { n: 5, id: "L2.05", title: "Short a word family -ap", th: "อ่านคำลงท้าย -ap", chips: ["cap","map","nap","tap"], status: "ยังไม่เล่น" },
      { n: 6, id: "L2.06", title: "Short e word family -en", th: "อ่านคำลงท้าย -en", chips: ["pen","hen","ten"], status: "ยังไม่เล่น" },
      { n: 7, id: "L2.07", title: "Short e word family -et", th: "อ่านคำลงท้าย -et", chips: ["net","pet","wet","jet"], status: "ยังไม่เล่น" },
      { n: 8, id: "L2.08", title: "Short i word family -ig", th: "อ่านคำลงท้าย -ig", chips: ["pig","big","dig","wig"], status: "ยังไม่เล่น" },
      { n: 9, id: "L2.09", title: "Short i word family -in", th: "อ่านคำลงท้าย -in", chips: ["pin","fin","win","bin"], status: "ยังไม่เล่น" },
      { n: 10, id: "L2.10", title: "Short o word family -og", th: "อ่านคำลงท้าย -og", chips: ["dog","log","fog","jog"], status: "ยังไม่เล่น" },
      { n: 11, id: "L2.11", title: "Short o word family -ot", th: "อ่านคำลงท้าย -ot", chips: ["pot","hot","dot","cot"], status: "ยังไม่เล่น" },
      { n: 12, id: "L2.12", title: "Short u word family -ug", th: "อ่านคำลงท้าย -ug", chips: ["bug","rug","mug","hug"], status: "ยังไม่เล่น" },
      { n: 13, id: "L2.13", title: "Short u word family -un", th: "อ่านคำลงท้าย -un", chips: ["sun","run","fun","bun"], status: "ยังไม่เล่น" },
      { n: 14, id: "L2.14", title: "Mixed CVC words", th: "เลือกสระที่ถูกต้อง", chips: ["cat","pen","pig","dog","sun"], status: "ยังไม่เล่น" },
      { n: 15, id: "L2.15", title: "Read short CVC sentences", th: "อ่านประโยคง่าย", chips: ["Sam sat","A cat sat","A pig sat","A dog sat"], status: "ยังไม่เล่น" },
      { n: 16, id: "L2.16", title: "Level 2 checkpoint", th: "ทดสอบการผสมเสียงและอ่านคำ", chips: ["map","hen","pin","log","sun"], status: "ยังไม่เล่น" }
    ];'''

if old_lv2 in l_html:
    l_html = l_html.replace(old_lv2, new_lv2)
    with open(LEVEL_HTML, 'w', encoding='utf-8') as f:
        f.write(l_html)
    print("Updated theme_phonicsLevel.html LV2_LESSONS successfully!")
else:
    print("Could not match old_lv2 in theme_phonicsLevel.html")

# 2. Update theme_phonicsLesson.html
LESSON_HTML = '/var/www/kidobits/theme/theme_phonicsLesson.html'
shutil.copy2(LESSON_HTML, '/home/openhands/backups/theme_phonicsLesson.html.bak_l2')

with open(LESSON_HTML, 'r', encoding='utf-8') as f:
    les_html = f.read()

# Update LESSON_META for L2
old_meta_l2 = '''      "L2.01": { n: 1, title: "s a t p — first blends", th: "ผสมคำสระ a" },
      "L2.02": { n: 2, title: "i n m — short i", th: "ผสมเสียง i n m" },
      "L2.03": { n: 3, title: "Short a word family -at", th: "อ่านคำลงท้าย -at" },
      "L2.04": { n: 4, title: "Short a word family -an", th: "อ่านคำลงท้าย -an" },
      "L2.05": { n: 5, title: "Short a word family -ap", th: "อ่านคำลงท้าย -ap" },
      "L2.06": { n: 6, title: "Short e word family -en", th: "อ่านคำลงท้าย -en" },
      "L2.07": { n: 7, title: "Short e word family -et", th: "อ่านคำลงท้าย -et" },
      "L2.08": { n: 8, title: "Short i word family -in", th: "อ่านคำลงท้าย -in" },
      "L2.09": { n: 9, title: "Short i word family -it", th: "อ่านคำลงท้าย -it" },
      "L2.10": { n: 10, title: "Short o word family -og", th: "อ่านคำลงท้าย -og" },
      "L2.11": { n: 11, title: "Short o word family -op", th: "อ่านคำลงท้าย -op" },
      "L2.12": { n: 12, title: "Short u word family -ug", th: "อ่านคำลงท้าย -ug" },
      "L2.13": { n: 13, title: "Short u word family -un", th: "อ่านคำลงท้าย -un" },
      "L2.14": { n: 14, title: "Mixed Short Vowels 1", th: "ทบทวนสระผสม 1" },
      "L2.15": { n: 15, title: "Mixed Short Vowels 2", th: "ทบทวนสระผสม 2" },
      "L2.16": { n: 16, title: "Level 2 Review & Story", th: "สรุป Level 2 & นิทาน" }'''

new_meta_l2 = '''      "L2.01": { n: 1, title: "s a t p — first blends", th: "ผสมคำสระ a" },
      "L2.02": { n: 2, title: "i n m — short i", th: "ผสมเสียง i n m" },
      "L2.03": { n: 3, title: "Short a word family -at", th: "อ่านคำลงท้าย -at" },
      "L2.04": { n: 4, title: "Short a word family -an", th: "อ่านคำลงท้าย -an" },
      "L2.05": { n: 5, title: "Short a word family -ap", th: "อ่านคำลงท้าย -ap" },
      "L2.06": { n: 6, title: "Short e word family -en", th: "อ่านคำลงท้าย -en" },
      "L2.07": { n: 7, title: "Short e word family -et", th: "อ่านคำลงท้าย -et" },
      "L2.08": { n: 8, title: "Short i word family -ig", th: "อ่านคำลงท้าย -ig" },
      "L2.09": { n: 9, title: "Short i word family -in", th: "อ่านคำลงท้าย -in" },
      "L2.10": { n: 10, title: "Short o word family -og", th: "อ่านคำลงท้าย -og" },
      "L2.11": { n: 11, title: "Short o word family -ot", th: "อ่านคำลงท้าย -ot" },
      "L2.12": { n: 12, title: "Short u word family -ug", th: "อ่านคำลงท้าย -ug" },
      "L2.13": { n: 13, title: "Short u word family -un", th: "อ่านคำลงท้าย -un" },
      "L2.14": { n: 14, title: "Mixed CVC words", th: "เลือกสระที่ถูกต้อง" },
      "L2.15": { n: 15, title: "Read short CVC sentences", th: "อ่านประโยคง่าย" },
      "L2.16": { n: 16, title: "Level 2 checkpoint", th: "ทดสอบการผสมเสียงและอ่านคำ" }'''

if old_meta_l2 in les_html:
    les_html = les_html.replace(old_meta_l2, new_meta_l2)
    print("Updated LESSON_META for Level 2 in theme_phonicsLesson.html")

# Update client-side WORD_ALIASES in theme_phonicsLesson.html
client_aliases_str = '''
      "at": ["at", "add", "ad", "et", "ed", "hat", "att"],
      "big": ["big", "pig", "beak", "bic", "beg", "bick", "bigs"],
      "bin": ["bin", "been", "bean", "pin", "bing", "bins"],
      "bug": ["bug", "back", "buck", "bag", "bog", "bugs"],
      "bun": ["bun", "ban", "pan", "burn", "buns"],
      "cap": ["cap", "cup", "cab", "cat", "caps"],
      "cot": ["cot", "cut", "cod", "cat", "caught", "cots"],
      "dig": ["dig", "dick", "deek", "deck", "digs"],
      "dot": ["dot", "dat", "dock", "duck", "dots"],
      "fin": ["fin", "thin", "fan", "pin", "thing", "fins"],
      "fog": ["fog", "fork", "fox", "fock", "frog", "fogs"],
      "fun": ["fun", "fan", "fang", "fine", "funs"],
      "hot": ["hot", "hat", "heart", "hard", "hod"],
      "hug": ["hug", "hack", "hook", "hawk", "hugs"],
      "jet": ["jet", "jed", "check", "jack", "chat", "jets"],
      "jog": ["jog", "jock", "chock", "shock", "joke", "jogs"],
      "pan": ["pan", "pen", "pin", "fan", "pam", "pans"],
      "pat": ["pat", "pet", "pad", "bad", "bat", "pats"],
      "pet": ["pet", "pat", "ped", "bet", "pets"],
      "pig": ["pig", "pick", "peek", "peg", "pigs"],
      "pin": ["pin", "pen", "bin", "tin", "peen", "ping", "pins"],
      "pot": ["pot", "pod", "part", "hot", "pots"],
      "rug": ["rug", "rag", "rock", "rack", "rugs"],
      "run": ["run", "ran", "rum", "one", "ren", "runs"],
      "sat": ["sat", "set", "sad", "sed", "sack", "sap", "sats"],
      "sit": ["sit", "set", "seed", "sick", "seat", "sits"],
      "sun": ["sun", "son", "san", "some", "sung", "suns"],
      "ten": ["ten", "tin", "tan", "den", "tens"],
      "tip": ["tip", "tib", "deep", "dip", "teep", "tips"],
      "win": ["win", "wen", "when", "one", "wind", "wing", "wins"],
'''
alias_pos = les_html.find('const WORD_ALIASES = {')
if alias_pos != -1:
    alias_pos += len('const WORD_ALIASES = {')
    les_html = les_html[:alias_pos] + client_aliases_str + les_html[alias_pos:]
    print("Added L2 WORD_ALIASES to theme_phonicsLesson.html")

# Update playSentenceAudio to have word sequence fallback
old_psa = '''    function playSentenceAudio() {
      unlockAudio();
      const lid = currentLesson ? (currentLesson.id || currentLessonId) : currentLessonId;
      const lidClean = String(lid).toLowerCase().replace(".", "_"); const sentAudio = currentItem.sentence_audio || `/kidobits/v2/audio/sent_${lidClean}.mp3`;
      playAudio(sentAudio, `🔊 ${currentItem.sentence || currentItem.word}`);
    }'''

new_psa = '''    function playSentenceAudio() {
      unlockAudio();
      const lid = currentLesson ? (currentLesson.id || currentLessonId) : currentLessonId;
      const lidClean = String(lid).toLowerCase().replace(".", "_");
      const sentAudio = currentItem.sentence_audio || `/kidobits/v2/audio/sent_${lidClean}.mp3`;
      playAudio(sentAudio, `🔊 ${currentItem.sentence || currentItem.word}`, () => {}, (err) => {
        // Fallback: play words of sentence sequentially
        if (currentItem && currentItem.words && currentItem.words.length) {
          const wordList = currentItem.words.map(w => w.toLowerCase().replace(/[^a-z]/g, ''));
          let wIdx = 0;
          function playNextWord() {
            if (wIdx < wordList.length) {
              const curW = wordList[wIdx++];
              playAudio(`/kidobits/v2/audio/word_${curW}.mp3`, `🔊 ${curW}`, playNextWord, playNextWord);
            }
          }
          playNextWord();
        }
      });
    }'''

if old_psa in les_html:
    les_html = les_html.replace(old_psa, new_psa)
    print("Updated playSentenceAudio with word fallback")

with open(LESSON_HTML, 'w', encoding='utf-8') as f:
    f.write(les_html)

print("Saved theme_phonicsLesson.html successfully!")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/apply_frontend_l2.py', 'w') as f:
    f.write(remote_code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/apply_frontend_l2.py')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("ERR:", err)

# Ensure permissions
ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S chown -R www-data:www-data /var/www/kidobits/theme")

ssh.close()
