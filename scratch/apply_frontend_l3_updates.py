import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')
sftp = ssh.open_sftp()

remote_script = """import os
import shutil

# 1. Update theme_phonicsLevel.html
LEVEL_HTML = '/var/www/kidobits/theme/theme_phonicsLevel.html'
shutil.copy2(LEVEL_HTML, '/home/openhands/backups/theme_phonicsLevel.html.bak_l3')

with open(LEVEL_HTML, 'r', encoding='utf-8') as f:
    l_html = f.read()

lv3_lessons_block = '''    const LV3_LESSONS = [
      { n: 1, id: "L3.01", title: "sh", th: "เสียง sh /ʃ/", chips: ["ship","shop","fish","dish"], status: "ยังไม่เล่น" },
      { n: 2, id: "L3.02", title: "ch", th: "เสียง ch /tʃ/", chips: ["chip","chop","chin","much"], status: "ยังไม่เล่น" },
      { n: 3, id: "L3.03", title: "th unvoiced", th: "เสียง th /θ/", chips: ["thin","bath","moth","path"], status: "ยังไม่เล่น" },
      { n: 4, id: "L3.04", title: "th voiced", th: "เสียง th /ð/", chips: ["this","that","them","then"], status: "ยังไม่เล่น" },
      { n: 5, id: "L3.05", title: "ck and ng", th: "เสียง ck /k/ และ ng /ŋ/", chips: ["duck","sock","back","ring","sing","king"], status: "ยังไม่เล่น" },
      { n: 6, id: "L3.06", title: "wh; cumulative consonant review", th: "อ่าน wh เป็น /w/ และทบทวน", chips: ["when","whip","which","whack"], status: "ยังไม่เล่น" },
      { n: 7, id: "L3.07", title: "Initial s blends", th: "พยัญชนะควบ s", chips: ["stop","spin","swim","skip"], status: "ยังไม่เล่น" },
      { n: 8, id: "L3.08", title: "Initial l blends", th: "พยัญชนะควบ l", chips: ["black","clap","flag","plum"], status: "ยังไม่เล่น" },
      { n: 9, id: "L3.09", title: "Initial r blends", th: "พยัญชนะควบ r", chips: ["frog","crab","drum","trip"], status: "ยังไม่เล่น" },
      { n: 10, id: "L3.10", title: "Final blends -nd -st", th: "เสียงควบท้าย -nd -st", chips: ["hand","sand","nest","fast"], status: "ยังไม่เล่น" },
      { n: 11, id: "L3.11", title: "Final blends -mp -nt", th: "เสียงควบท้าย -mp -nt", chips: ["lamp","jump","tent","mint"], status: "ยังไม่เล่น" },
      { n: 12, id: "L3.12", title: "Three-consonant blends", th: "เสียงควบสามตัว", chips: ["spring","string","splash","scrub"], status: "ยังไม่เล่น" },
      { n: 13, id: "L3.13", title: "Digraph vs blend", th: "แยกเสียงรวมและเสียงควบ", chips: ["ship","slip","chop","clap"], status: "ยังไม่เล่น" },
      { n: 14, id: "L3.14", title: "Word-building with blends", th: "สร้างคำจากหน่วยเสียง", chips: ["frog","stop","flag","hand"], status: "ยังไม่เล่น" },
      { n: 15, id: "L3.15", title: "Decodable consonant-pattern sentences", th: "อ่านประโยคที่มี digraph และ blend", chips: ["The ship is big","The frog can jump","A fish is in the pond"], status: "ยังไม่เล่น" },
      { n: 16, id: "L3.16", title: "Level 3 checkpoint", th: "ทดสอบ digraph และ blend", chips: ["shop","thin","duck","stop","crab","hand"], status: "ยังไม่เล่น" }
    ];'''

old_level_logic = '''    const q = new URLSearchParams(location.search);
    const lv = parseInt(q.get('lv') || '1', 10);

    const isLv2 = (lv === 2);
    const lessons = isLv2 ? LV2_LESSONS : LV1_LESSONS;

    // Set Hero UI
    const heroCard = document.getElementById('hero-card');
    const heroMascot = document.getElementById('hero-mascot');
    const heroTitle = document.getElementById('hero-title');
    const heroSub = document.getElementById('hero-sub');
    const heroBar = document.getElementById('hero-bar');
    const heroProg = document.getElementById('hero-progress-text');

    if (isLv2) {
      heroCard.className = "bg-gradient-to-br from-[#7ED9A8] to-[#4EB87E] rounded-[24px] p-5 text-white shadow-lg relative overflow-hidden";
      heroMascot.textContent = "🐸";
      heroTitle.textContent = "ระดับ 2 • Blending & CVC";
      heroSub.textContent = "16 บทเรียน • 16/16 พร้อมเล่น";
      heroBar.style.width = "19%";
      heroProg.textContent = "✅ ผ่านแล้ว 3/16 • 19%";
    } else {
      heroCard.className = "bg-gradient-to-br from-[#8B7CFF] to-[#A798FF] rounded-[24px] p-5 text-white shadow-lg relative overflow-hidden";
      heroMascot.textContent = "🐱";
      heroTitle.textContent = "ระดับ 1 • Phonemic Awareness & Alphabet";
      heroSub.textContent = "12 บทเรียน • 12/12 พร้อมเล่น";
      heroBar.style.width = "100%";
      heroProg.textContent = "✅ ผ่านแล้ว 12/12 • 100%";
    }'''

new_level_logic = lv3_lessons_block + '''\\n
    const q = new URLSearchParams(location.search);
    const lv = parseInt(q.get('lv') || '1', 10);

    const isLv3 = (lv === 3);
    const isLv2 = (lv === 2);
    const lessons = isLv3 ? LV3_LESSONS : (isLv2 ? LV2_LESSONS : LV1_LESSONS);

    // Set Hero UI
    const heroCard = document.getElementById('hero-card');
    const heroMascot = document.getElementById('hero-mascot');
    const heroTitle = document.getElementById('hero-title');
    const heroSub = document.getElementById('hero-sub');
    const heroBar = document.getElementById('hero-bar');
    const heroProg = document.getElementById('hero-progress-text');

    if (isLv3) {
      heroCard.className = "bg-gradient-to-br from-[#FFB84D] to-[#F39C12] rounded-[24px] p-5 text-white shadow-lg relative overflow-hidden";
      heroMascot.textContent = "🔗";
      heroTitle.textContent = "ระดับ 3 • Digraphs & Consonant Blends";
      heroSub.textContent = "16 บทเรียน • 16/16 พร้อมเล่น";
      heroBar.style.width = "0%";
      heroProg.textContent = "ยังไม่เริ่มเล่น • 0/16";
    } else if (isLv2) {
      heroCard.className = "bg-gradient-to-br from-[#7ED9A8] to-[#4EB87E] rounded-[24px] p-5 text-white shadow-lg relative overflow-hidden";
      heroMascot.textContent = "🐸";
      heroTitle.textContent = "ระดับ 2 • Blending & CVC";
      heroSub.textContent = "16 บทเรียน • 16/16 พร้อมเล่น";
      heroBar.style.width = "19%";
      heroProg.textContent = "✅ ผ่านแล้ว 3/16 • 19%";
    } else {
      heroCard.className = "bg-gradient-to-br from-[#8B7CFF] to-[#A798FF] rounded-[24px] p-5 text-white shadow-lg relative overflow-hidden";
      heroMascot.textContent = "🐱";
      heroTitle.textContent = "ระดับ 1 • Phonemic Awareness & Alphabet";
      heroSub.textContent = "12 บทเรียน • 12/12 พร้อมเล่น";
      heroBar.style.width = "100%";
      heroProg.textContent = "✅ ผ่านแล้ว 12/12 • 100%";
    }'''

if old_level_logic in l_html:
    l_html = l_html.replace(old_level_logic, new_level_logic)
    with open(LEVEL_HTML, 'w', encoding='utf-8') as f:
        f.write(l_html)
    print("Updated theme_phonicsLevel.html with Level 3 successfully!")
else:
    print("Could not find old_level_logic in theme_phonicsLevel.html")


# 2. Update theme_phonicsLesson.html
LESSON_HTML = '/var/www/kidobits/theme/theme_phonicsLesson.html'
shutil.copy2(LESSON_HTML, '/home/openhands/backups/theme_phonicsLesson.html.bak_l3')

with open(LESSON_HTML, 'r', encoding='utf-8') as f:
    les_html = f.read()

# Header & Meta Info
old_header_info = '''    // Header & Meta Info
    const isLv2 = LID.startsWith('L2');
    const lvNum = isLv2 ? 2 : 1;
    document.getElementById('hero-icon').textContent = isLv2 ? "🐸" : "🐱";
    document.getElementById('cover-avatar').textContent = isLv2 ? "🐸" : "🐱";
    document.getElementById('badge-code').textContent = LID;'''

new_header_info = '''    // Header & Meta Info
    const isLv3 = LID.startsWith('L3');
    const isLv2 = LID.startsWith('L2');
    const lvNum = isLv3 ? 3 : (isLv2 ? 2 : 1);
    document.getElementById('hero-icon').textContent = isLv3 ? "🔗" : (isLv2 ? "🐸" : "🐱");
    document.getElementById('cover-avatar').textContent = isLv3 ? "🔗" : (isLv2 ? "🐸" : "🐱");
    document.getElementById('badge-code').textContent = LID;'''

if old_header_info in les_html:
    les_html = les_html.replace(old_header_info, new_header_info)
    print("Updated Header & Meta Info in theme_phonicsLesson.html")

# LESSON_META for Level 3
old_meta_target = '''      "L2.16": { n: 16, title: "Level 2 checkpoint", th: "ทดสอบการผสมเสียงและอ่านคำ" }'''
new_meta_addition = '''      "L2.16": { n: 16, title: "Level 2 checkpoint", th: "ทดสอบการผสมเสียงและอ่านคำ" },

      "L3.01": { n: 1, title: "sh", th: "เสียง sh /ʃ/" },
      "L3.02": { n: 2, title: "ch", th: "เสียง ch /tʃ/" },
      "L3.03": { n: 3, title: "th unvoiced", th: "เสียง th /θ/" },
      "L3.04": { n: 4, title: "th voiced", th: "เสียง th /ð/" },
      "L3.05": { n: 5, title: "ck and ng", th: "เสียง ck /k/ และ ng /ŋ/" },
      "L3.06": { n: 6, title: "wh; cumulative consonant review", th: "อ่าน wh เป็น /w/ และทบทวน" },
      "L3.07": { n: 7, title: "Initial s blends", th: "พยัญชนะควบ s" },
      "L3.08": { n: 8, title: "Initial l blends", th: "พยัญชนะควบ l" },
      "L3.09": { n: 9, title: "Initial r blends", th: "พยัญชนะควบ r" },
      "L3.10": { n: 10, title: "Final blends -nd -st", th: "เสียงควบท้าย -nd -st" },
      "L3.11": { n: 11, title: "Final blends -mp -nt", th: "เสียงควบท้าย -mp -nt" },
      "L3.12": { n: 12, title: "Three-consonant blends", th: "เสียงควบสามตัว" },
      "L3.13": { n: 13, title: "Digraph vs blend", th: "แยกเสียงรวมและเสียงควบ" },
      "L3.14": { n: 14, title: "Word-building with blends", th: "สร้างคำจากหน่วยเสียง" },
      "L3.15": { n: 15, title: "Decodable consonant-pattern sentences", th: "อ่านประโยคที่มี digraph และ blend" },
      "L3.16": { n: 16, title: "Level 3 checkpoint", th: "ทดสอบ digraph และ blend" }'''

if old_meta_target in les_html:
    les_html = les_html.replace(old_meta_target, new_meta_addition)
    print("Updated LESSON_META with Level 3 in theme_phonicsLesson.html")

# Client-side WORD_ALIASES
old_client_alias_target = '''      "win": ["win", "wen", "when", "one", "wind", "wing", "wins"],'''
new_client_aliases = '''      "win": ["win", "wen", "when", "one", "wind", "wing", "wins"],

      // Level 3 Words
      "back": ["back", "pack", "bag", "bark", "bek", "backs", "beck"],
      "bath": ["bath", "pass", "bad", "bat", "baths", "bass", "beth"],
      "black": ["black", "blank", "plak", "block", "blacks", "bleck"],
      "chin": ["chin", "jin", "shin", "tin", "chen", "chins", "gin"],
      "chip": ["chip", "jib", "ship", "tip", "cheep", "chips", "jip"],
      "chop": ["chop", "shop", "job", "top", "chup", "chops", "chap"],
      "clap": ["clap", "club", "cap", "flap", "crab", "claps", "clep"],
      "crab": ["crab", "clap", "grab", "crop", "crap", "crabs", "cram"],
      "dish": ["dish", "this", "fish", "ditch", "des", "dishes", "tish"],
      "drum": ["drum", "dram", "drop", "trum", "drums", "trom"],
      "duck": ["duck", "doc", "tuck", "dog", "dark", "ducks", "dak"],
      "fast": ["fast", "first", "fat", "pass", "fasts", "fest"],
      "fish": ["fish", "fit", "wish", "finish", "fishes", "fiss"],
      "flag": ["flag", "flak", "flex", "black", "flap", "flags", "fleg"],
      "frog": ["frog", "fog", "frock", "fok", "frong", "frogs", "frak"],
      "hand": ["hand", "hen", "head", "and", "hands", "hend"],
      "jump": ["jump", "champ", "jam", "junk", "jumps", "jomp"],
      "king": ["king", "keen", "kin", "kick", "kings", "keng"],
      "lamp": ["lamp", "lamb", "lab", "lump", "lamps", "lemp"],
      "mint": ["mint", "men", "mid", "meant", "mints", "ment"],
      "moth": ["moth", "moss", "boss", "mod", "moths", "muff"],
      "much": ["much", "match", "march", "mutt", "mudge", "mach"],
      "nest": ["nest", "net", "next", "mess", "nests", "nes"],
      "path": ["path", "pass", "pat", "part", "past", "paths"],
      "plum": ["plum", "plan", "pluck", "lump", "plums", "plom"],
      "pond": ["pond", "bond", "pawn", "point", "ponds", "pont"],
      "ring": ["ring", "rink", "rim", "rain", "rings", "wring"],
      "sand": ["sand", "send", "sun", "sound", "sands", "sant"],
      "scrub": ["scrub", "scrap", "strap", "shrub", "scrubs", "skrub"],
      "ship": ["ship", "sheep", "seep", "sit", "chips", "ships"],
      "shop": ["shop", "chop", "shot", "sharp", "shops", "chock"],
      "sing": ["sing", "seen", "sin", "sink", "sings", "seng"],
      "skip": ["skip", "scape", "skeep", "slit", "skips", "skep"],
      "slip": ["slip", "sleep", "slap", "snip", "slips", "slep"],
      "sock": ["sock", "suck", "shock", "soak", "socks", "sok"],
      "spin": ["spin", "speed", "span", "spoon", "spins", "spen"],
      "splash": ["splash", "flash", "plush", "splashes", "splat"],
      "spring": ["spring", "sprint", "string", "springs", "spreng"],
      "stop": ["stop", "step", "stock", "top", "stops", "stob"],
      "string": ["string", "spring", "stream", "strings", "streng"],
      "swim": ["swim", "sweet", "swing", "swum", "swims", "swem"],
      "tent": ["tent", "ten", "tan", "dent", "tents", "tend"],
      "that": ["that", "dat", "thet", "at", "tats", "thad"],
      "them": ["them", "dem", "den", "then", "ten", "thems"],
      "then": ["then", "den", "ten", "than", "them", "thens"],
      "thin": ["thin", "tin", "fin", "din", "thins", "then"],
      "this": ["this", "dis", "tis", "zis", "thees"],
      "trip": ["trip", "drip", "grip", "track", "trips", "treep"],
      "whack": ["whack", "walk", "track", "quack", "wake", "whacks", "wack"],
      "when": ["when", "wen", "win", "one", "then", "whens"],
      "which": ["which", "witch", "wish", "rich", "with", "wich"],
      "whip": ["whip", "wip", "weep", "rip", "hip", "whips"],'''

if old_client_alias_target in les_html:
    les_html = les_html.replace(old_client_alias_target, new_client_aliases)
    print("Updated client-side WORD_ALIASES with Level 3 in theme_phonicsLesson.html")

with open(LESSON_HTML, 'w', encoding='utf-8') as f:
    f.write(les_html)

# Sudo chown & chmod
os.system("echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_phonicsLevel.html /var/www/kidobits/theme/theme_phonicsLesson.html")
print("Finished applying frontend updates!")
"""

with sftp.file('/tmp/apply_frontend_l3.py', 'w') as f:
    f.write(remote_script)

stdin, stdout, stderr = ssh.exec_command("python3 /tmp/apply_frontend_l3.py")
out = stdout.read().decode('utf-8')
err = stderr.read().decode('utf-8')
print("STDOUT:\n", out)
if err:
    print("STDERR:\n", err)

sftp.close()
ssh.close()
