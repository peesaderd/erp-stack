import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = '''
import asyncio
import edge_tts
import json
import os
import shutil

VOICE = "en-US-EmmaNeural"
LESSONS_PATH = "/home/openhands/emma-phonics/data/lessons.json"

print("--- 2. GENERATING MISSING PHONEMES ---")
missing_phonemes = {
    "air": "air",
    "are": "air",
    "ear": "ear",
    "bl": "bl",
    "cl": "cl",
    "pl": "pl",
    "dr": "dr",
    "tr": "tr",
    "mp": "mp",
    "nd": "nd",
    "nt": "nt",
    "mb": "m",
    "ed": "ed",
    "ing": "ing",
    "le": "le",
    "re": "re",
    "un": "un"
}

tmp_ph_dir = "/tmp/l5_l6_phonics"
os.makedirs(tmp_ph_dir, exist_ok=True)

async def gen_phonemes():
    for name, text in missing_phonemes.items():
        dst = f"{tmp_ph_dir}/ph_{name}.mp3"
        comm = edge_tts.Communicate(text, VOICE)
        await comm.save(dst)
        print(f"Generated phoneme ph_{name}.mp3")

asyncio.run(gen_phonemes())

print("--- 3. GENERATING SENTENCE AUDIOS FOR L5 & L6 ---")
l5_sentences = {
    "l5_01": "The red car drove past the farm to the park.",
    "l5_02": "The short fork is next to the hot corn.",
    "l5_03": "The little bird saw her green fern.",
    "l5_04": "Sit in the chair and share the square.",
    "l5_05": "I hear a big brown bear near the tree.",
    "l5_06": "The boy found a shiny coin in the soil.",
    "l5_07": "A brown cow stood out by the big cloud.",
    "l5_08": "I saw a cute cat with a soft paw.",
    "l5_09": "A giant gem was found in the big city.",
    "l5_10": "Write on the phone and do not be wrong.",
    "l5_11": "A happy monkey ate a little apple.",
    "l5_12": "The white rabbit enjoyed a sunset picnic.",
    "l5_13": "Unlock the door and replay the happy song.",
    "l5_14": "The children were jumping and playing outside.",
    "l5_15": "They said two small birds flew to school.",
    "l5_16": "The rabbit saw a bright star in the cloud."
}

l6_sentences = {
    "l6_01": "We saw a nest by the tree in the park.",
    "l6_02": "You were there when they said the words.",
    "l6_03": "Stop! Can you jump and run fast?",
    "l6_04": "The dog ran to Ben and drank cool water.",
    "l6_05": "At night, Sam went to the park with Dad.",
    "l6_06": "First, Tom put a seed in a pot. Next, he gave it water.",
    "l6_07": "It rained at night, so the green grass was wet.",
    "l6_08": "The sky was dark, so Sam got his raincoat.",
    "l6_09": "Ben had a red kite. The wind blew the kite high.",
    "l6_10": "A lost pup sat by the tree. Ben took the pup home.",
    "l6_11": "A seed lay in the soil. Rain fell and a green shoot grew.",
    "l6_12": "Rain fell on the roof. Sam put on his boots.",
    "l6_13": "Can we play in the garden? asked little Ben.",
    "l6_14": "Ben found a shiny shell and gave it to Dad.",
    "l6_15": "The bird sat on a branch and sang in the sun.",
    "l6_16": "A fox ran to the tree and found a red toy box."
}

tmp_sent_dir = "/tmp/l5_l6_sents"
os.makedirs(tmp_sent_dir, exist_ok=True)

all_sents = {}
all_sents.update(l5_sentences)
all_sents.update(l6_sentences)

async def gen_sents():
    for key, text in all_sents.items():
        dst = f"{tmp_sent_dir}/sent_{key}.mp3"
        comm = edge_tts.Communicate(text, VOICE, rate="-5%")
        await comm.save(dst)
        print(f"Generated sentence sent_{key}.mp3 ({os.path.getsize(dst)} bytes)")

asyncio.run(gen_sents())

print("--- 4. UPDATING LESSONS.JSON METADATA & SENTENCES ---")
shutil.copy2(LESSONS_PATH, f"{LESSONS_PATH}.bak_pre_l5_l6")

with open(LESSONS_PATH, "r", encoding="utf-8") as f:
    lessons_db = json.load(f)

l5_meta = {
    "L5.01": {"title": "ar", "desc": "เสียง ar สระอาร์", "goal": "เสียง ar /ɑː/", "targets": "car, star, farm, park"},
    "L5.02": {"title": "or", "desc": "เสียง or สระออร์", "goal": "เสียง or /ɔː/", "targets": "fork, corn, storm, short"},
    "L5.03": {"title": "er ir ur", "desc": "สระเสียงเออร์ r-controlled", "goal": "เสียง er ir ur /ɜː/", "targets": "her, fern, bird, girl, turn, burn"},
    "L5.04": {"title": "air and are", "desc": "เสียง air / are สระแอร์", "goal": "เสียง air / are /eə/", "targets": "air, chair, fair, care, share, square"},
    "L5.05": {"title": "ear patterns", "desc": "เสียง ear สระเอียร์และแอร์", "goal": "เสียง ear patterns", "targets": "hear, near, dear, bear, pear, wear"},
    "L5.06": {"title": "oi and oy", "desc": "เสียง oi / oy สระออย", "goal": "เสียง oi / oy /ɔɪ/", "targets": "coin, boil, soil, boy, toy, enjoy"},
    "L5.07": {"title": "ou and ow", "desc": "เสียง ou / ow สระเอา", "goal": "เสียง ou / ow /aʊ/", "targets": "out, cloud, shout, cow, now, brown"},
    "L5.08": {"title": "au and aw", "desc": "เสียง au / aw สระออ", "goal": "เสียง au / aw /ɔː/", "targets": "haul, sauce, saw, paw, draw"},
    "L5.09": {"title": "Soft c and g", "desc": "พยัญชนะเสียงนุ่ม c /s/ และ g /dʒ/", "goal": "Soft c and g", "targets": "city, cent, face, giant, gem, cage"},
    "L5.10": {"title": "ph and silent consonants", "desc": "ph และพยัญชนะไม่ออกเสียง (kn, wr, mb)", "goal": "ph and silent consonants", "targets": "phone, graph, knee, know, write, wrong, lamb"},
    "L5.11": {"title": "Final -le, y and ey", "desc": "คำลงท้าย -le, y และ ey", "goal": "Final -le, y, ey", "targets": "apple, little, candle, happy, funny, key, monkey"},
    "L5.12": {"title": "Syllable division", "desc": "การแบ่งพยางค์คำ 2 พยางค์", "goal": "Syllable division", "targets": "rabbit, sunset, picnic, robot"},
    "L5.13": {"title": "Prefixes un- re-", "desc": "คำอุปสรรค un- และ re-", "goal": "Prefixes un- re-", "targets": "unhappy, unlock, redo, replay"},
    "L5.14": {"title": "Suffixes -ing and -ed", "desc": "คำปัจจัย -ing และ -ed", "goal": "Suffixes -ing and -ed", "targets": "jumping, playing, jumped, played, wanted"},
    "L5.15": {"title": "Exception words", "desc": "คำยกเว้นและการสะกดเสียงสระพิเศษ", "goal": "Exception words", "targets": "said, one, two, does, have, water, school"},
    "L5.16": {"title": "Level 5 checkpoint", "desc": "ทดสอบวัดระดับ Level 5", "goal": "Level 5 checkpoint", "targets": "star, bird, coin, cloud, knee, rabbit"}
}

l6_meta = {
    "L6.01": {"title": "Phrase reading", "desc": "ฝึกอ่านกลุ่มคำและวลีสั้น", "goal": "Phrase reading", "targets": "in the park, on the bed, by the tree"},
    "L6.02": {"title": "High-frequency words", "desc": "ทบทวนคำศัพท์พบบ่อย (Sight words)", "goal": "Sight words review", "targets": "the, said, was, were, there, you"},
    "L6.03": {"title": "Punctuation & expression", "desc": "การอ่านตามเครื่องหมายวรรคตอนและน้ำเสียง", "goal": "Punctuation & expression", "targets": "Stop!, Can you jump?, What a fun day!"},
    "L6.04": {"title": "Who and what", "desc": "จับใจความ: ใครและทำอะไร", "goal": "Comprehension: Who and what", "targets": "The dog ran to Ben. Ben gave it water."},
    "L6.05": {"title": "Where and when", "desc": "จับใจความ: ที่ไหนและเมื่อไหร่", "goal": "Comprehension: Where and when", "targets": "At night, Sam went to the park with Dad."},
    "L6.06": {"title": "First, next, last", "desc": "ลำดับเหตุการณ์ในเรื่องสั้น", "goal": "Sequencing: First, next, last", "targets": "First, Tom put a seed in a pot. Next, he gave it water."},
    "L6.07": {"title": "Cause and effect", "desc": "เหตุและผลในเรื่องราว", "goal": "Cause and effect", "targets": "It rained at night, so the grass was wet."},
    "L6.08": {"title": "Making predictions", "desc": "การคาดคะเนเหตุการณ์", "goal": "Making predictions", "targets": "The sky was dark. Sam got his raincoat."},
    "L6.09": {"title": "Story 1: The Red Kite", "desc": "นิทานสั้น: ว่าวสีแดง", "goal": "Story: The Red Kite", "targets": "Ben had a red kite. The wind blew the kite high."},
    "L6.10": {"title": "The Lost Pup", "desc": "นิทานสั้น: ลูกสุนัขหลงทาง", "goal": "Story: The Lost Pup", "targets": "A pup was lost. Ben took the pup home."},
    "L6.11": {"title": "The Seed", "desc": "นิทานสั้น: เมล็ดพืชเติบโต", "goal": "Story: The Seed", "targets": "A seed lay in the soil. Rain fell and a shoot grew."},
    "L6.12": {"title": "A Rainy Day", "desc": "นิทานสั้น: วันฝนตกแสนสนุก", "goal": "Story: A Rainy Day", "targets": "Rain fell on the roof. Sam put on his boots."},
    "L6.13": {"title": "Reading dialogue", "desc": "ฝึกอ่านบทสนทนาตัวละคร", "goal": "Reading dialogue", "targets": "Can we play? asked Ben."},
    "L6.14": {"title": "Retelling", "desc": "การเล่าเรื่องซ้ำด้วยตนเอง", "goal": "Retelling stories", "targets": "Ben found a shell. He gave it to Dad."},
    "L6.15": {"title": "Fluency practice", "desc": "ฝึกอ่านออกเสียงอย่างคล่องแคล่ว", "goal": "Fluency practice", "targets": "The bird sat on a branch and sang in the sun."},
    "L6.16": {"title": "Final reading assessment", "desc": "แบบทดสอบการอ่านวัดระดับจบหลักสูตร", "goal": "Final assessment", "targets": "A fox saw a small box with a note."}
}

for lid, meta in l5_meta.items():
    if lid in lessons_db:
        key_low = lid.lower().replace('.', '_')
        sent_txt = l5_sentences.get(key_low, "")
        words_list = sent_txt.replace(".", "").replace("!", "").replace(",", "").split()
        lessons_db[lid]["id"] = lid
        lessons_db[lid]["title"] = meta["title"]
        lessons_db[lid]["desc"] = meta["desc"]
        lessons_db[lid]["goal"] = meta["goal"]
        lessons_db[lid]["targets"] = meta["targets"]
        lessons_db[lid]["rv"] = [{"sentence": sent_txt, "words": words_list}]

for lid, meta in l6_meta.items():
    if lid in lessons_db:
        key_low = lid.lower().replace('.', '_')
        sent_txt = l6_sentences.get(key_low, "")
        words_list = sent_txt.replace(".", "").replace("!", "").replace(",", "").split()
        lessons_db[lid]["id"] = lid
        lessons_db[lid]["title"] = meta["title"]
        lessons_db[lid]["desc"] = meta["desc"]
        lessons_db[lid]["goal"] = meta["goal"]
        lessons_db[lid]["targets"] = meta["targets"]
        lessons_db[lid]["rv"] = [{"sentence": sent_txt, "words": words_list}]

with open(LESSONS_PATH, "w", encoding="utf-8") as f:
    json.dump(lessons_db, f, indent=2, ensure_ascii=False)

print(f"Updated {len(lessons_db)} lessons in {LESSONS_PATH} successfully!")
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/deploy_l5_l6.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/deploy_l5_l6.py')
print("PYTHON STDOUT:\n", stdout.read().decode())
print("PYTHON STDERR:\n", stderr.read().decode())

# Copy generated assets with sudo
cmd_cp = '''
echo "OpenHands@ERP2026" | sudo -S cp /var/www/kidobits/v2/pair/img/L1_robot_8f38ebc7.png /var/www/kidobits/v2/images/robot.png
echo "OpenHands@ERP2026" | sudo -S cp -r /tmp/l5_l6_phonics/* /var/www/kidobits/v2/audio/phonics_bank/
echo "OpenHands@ERP2026" | sudo -S cp -r /tmp/l5_l6_sents/* /var/www/kidobits/v2/audio/
echo "OpenHands@ERP2026" | sudo -S chown -R www-data:www-data /var/www/kidobits/v2/images/robot.png /var/www/kidobits/v2/audio/
echo "OpenHands@ERP2026" | sudo -S chmod 644 /var/www/kidobits/v2/images/robot.png /var/www/kidobits/v2/audio/phonics_bank/* /var/www/kidobits/v2/audio/sent_l5_*.mp3 /var/www/kidobits/v2/audio/sent_l6_*.mp3
'''
stdin, stdout, stderr = ssh.exec_command(cmd_cp)
stdout.channel.recv_exit_status()

# Verify counts
stdin, stdout, stderr = ssh.exec_command('ls -l /var/www/kidobits/v2/images/robot.png; ls /var/www/kidobits/v2/audio/phonics_bank/ | wc -l; ls /var/www/kidobits/v2/audio/sent_l* | wc -l')
print("VERIFICATION:\n", stdout.read().decode())

ssh.close()
