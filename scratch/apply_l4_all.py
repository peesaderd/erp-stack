import paramiko
import json

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

# 1. Update lessons.json on server
sftp = ssh.open_sftp()
with sftp.open('/home/openhands/emma-phonics/data/lessons.json', 'r') as f:
    lessons_db = json.load(f)

# Backup lessons.json
stdin, stdout, stderr = ssh.exec_command('cp /home/openhands/emma-phonics/data/lessons.json /home/openhands/emma-phonics/data/lessons.json.bak_pre_l4')
stdout.channel.recv_exit_status()

l4_meta = {
    "L4.01": {"title": "Magic e: a_e", "desc": "สระเสียงยาว a_e", "goal": "สระเสียงยาว a_e", "targets": "cap, cape, tap, tape, mad, made"},
    "L4.02": {"title": "Magic e: i_e", "desc": "สระเสียงยาว i_e", "goal": "สระเสียงยาว i_e", "targets": "pin, pine, kit, kite, rid, ride"},
    "L4.03": {"title": "Magic e: o_e", "desc": "สระเสียงยาว o_e", "goal": "สระเสียงยาว o_e", "targets": "hop, hope, not, note, rod, rode"},
    "L4.04": {"title": "Magic e: u_e", "desc": "สระเสียงยาว u_e", "goal": "สระเสียงยาว u_e", "targets": "cub, cube, tub, tube, cut, cute"},
    "L4.05": {"title": "ai and ay", "desc": "สระเสียงยาว ai / ay", "goal": "สระเสียงยาว ai / ay", "targets": "rain, train, tail, day, play, stay"},
    "L4.06": {"title": "ee and ea", "desc": "สระเสียงยาว ee / ea", "goal": "สระเสียงยาว ee / ea", "targets": "see, tree, green, sea, leaf, team"},
    "L4.07": {"title": "oa and ow", "desc": "สระเสียงยาว oa / ow", "goal": "สระเสียงยาว oa / ow", "targets": "boat, coat, road, snow, grow, slow"},
    "L4.08": {"title": "igh and y", "desc": "สระเสียงยาว igh / y", "goal": "สระเสียงยาว igh / y", "targets": "night, light, bright, my, fly, cry"},
    "L4.09": {"title": "ue and ew", "desc": "สระเสียงยาว ue / ew", "goal": "สระเสียงยาว ue / ew", "targets": "blue, true, glue, new, few, grew"},
    "L4.10": {"title": "oo: long", "desc": "เสียง oo สระอูยาว", "goal": "เสียง oo สระอูยาว", "targets": "moon, food, spoon, pool"},
    "L4.11": {"title": "oo: short", "desc": "เสียง oo สระอุสั้น", "goal": "เสียง oo สระอุสั้น", "targets": "book, look, cook, foot"},
    "L4.12": {"title": "ie and e_e", "desc": "สระเสียงยาว ie / e_e", "goal": "สระเสียงยาว ie / e_e", "targets": "pie, tie, lie, these, theme"},
    "L4.13": {"title": "Long vs Short", "desc": "เปรียบเทียบสระสั้นและยาว", "goal": "เปรียบเทียบสระสั้นและยาว", "targets": "cap, cape, pin, pine, hop, hope, cub, cube"},
    "L4.14": {"title": "Mixed Vowel Teams", "desc": "ทบทวนสระผสม", "goal": "ทบทวนสระผสม", "targets": "rain, tree, boat, night, blue"},
    "L4.15": {"title": "Long-vowel sentences", "desc": "ฝึกอ่านประโยคสระเสียงยาว", "goal": "ฝึกอ่านประโยคสระเสียงยาว", "targets": "I can ride a bike. / The goat is on the road. / We see a green tree."},
    "L4.16": {"title": "Level 4 Checkpoint", "desc": "ทดสอบวัดระดับ Level 4", "goal": "ทดสอบวัดระดับ Level 4", "targets": "cake, bike, home, rain, moon, night"}
}

l4_sentences = {
    "L4.01": [{"sentence": "The man made a cape with tape.", "words": ["The", "man", "made", "a", "cape", "with", "tape"]}],
    "L4.02": [{"sentence": "I ride a bike to fly a kite.", "words": ["I", "ride", "a", "bike", "to", "fly", "a", "kite"]}],
    "L4.03": [{"sentence": "I hope you note the red rod.", "words": ["I", "hope", "you", "note", "the", "red", "rod"]}],
    "L4.04": [{"sentence": "The cute cub is in the tube.", "words": ["The", "cute", "cub", "is", "in", "the", "tube"]}],
    "L4.05": [{"sentence": "We can stay and play in the rain.", "words": ["We", "can", "stay", "and", "play", "in", "the", "rain"]}],
    "L4.06": [{"sentence": "We see a green tree by the sea.", "words": ["We", "see", "a", "green", "tree", "by", "the", "sea"]}],
    "L4.07": [{"sentence": "A slow boat is on the road in snow.", "words": ["A", "slow", "boat", "is", "on", "the", "road", "in", "snow"]}],
    "L4.08": [{"sentence": "A bright light shines in the night.", "words": ["A", "bright", "light", "shines", "in", "the", "night"]}],
    "L4.09": [{"sentence": "A few new birds flew in the blue sky.", "words": ["A", "few", "new", "birds", "flew", "in", "the", "blue", "sky"]}],
    "L4.10": [{"sentence": "The spoon is in the cool food pool.", "words": ["The", "spoon", "is", "in", "the", "cool", "food", "pool"]}],
    "L4.11": [{"sentence": "Look at the good cook with the book.", "words": ["Look", "at", "the", "good", "cook", "with", "the", "book"]}],
    "L4.12": [{"sentence": "Tie the tie and eat the pie.", "words": ["Tie", "the", "tie", "and", "eat", "the", "pie"]}],
    "L4.13": [{"sentence": "A cap and a cape by the pine tree.", "words": ["A", "cap", "and", "a", "cape", "by", "the", "pine", "tree"]}],
    "L4.14": [{"sentence": "The boat sailed in the rain under the moon.", "words": ["The", "boat", "sailed", "in", "the", "rain", "under", "the", "moon"]}],
    "L4.15": [
        {"sentence": "I can ride a bike.", "words": ["I", "can", "ride", "a", "bike"]},
        {"sentence": "The goat is on the road.", "words": ["The", "goat", "is", "on", "the", "road"]},
        {"sentence": "We see a green tree.", "words": ["We", "see", "a", "green", "tree"]}
    ],
    "L4.16": [{"sentence": "We eat cake at home in the bright night.", "words": ["We", "eat", "cake", "at", "home", "in", "the", "bright", "night"]}]
}

for lid, meta in l4_meta.items():
    if lid in lessons_db:
        lessons_db[lid]["id"] = lid
        lessons_db[lid]["title"] = meta["title"]
        lessons_db[lid]["desc"] = meta["desc"]
        lessons_db[lid]["goal"] = meta["goal"]
        lessons_db[lid]["targets"] = meta["targets"]
        lessons_db[lid]["rv"] = l4_sentences.get(lid, [])

with sftp.open('/home/openhands/emma-phonics/data/lessons.json', 'w') as f:
    json.dump(lessons_db, f, indent=2, ensure_ascii=False)
sftp.close()
print("Updated /home/openhands/emma-phonics/data/lessons.json")

# 2. Update api_server.py with Level 4 WORD_ALIASES
sftp_obj = ssh.open_sftp()
with sftp_obj.open('/home/openhands/emma-phonics/api_server.py', 'r') as f:
    api_code = f.read().decode('utf-8')

l4_aliases_code = """
    # Level 4 Words (Magic e & Vowel Teams)
    "bike": {"bike", "bite", "pike", "like", "bick", "bikes"},
    "blue": {"blue", "blew", "blow", "clue", "glue", "blues"},
    "boat": {"boat", "board", "bolt", "boot", "bought", "boats"},
    "book": {"book", "back", "buck", "look", "took", "books"},
    "bright": {"bright", "bride", "brite", "bite", "right", "brights"},
    "cake": {"cake", "kake", "cook", "kick", "coke", "cakes"},
    "cape": {"cape", "cave", "tape", "cap", "cope", "capes"},
    "coat": {"coat", "code", "cot", "goat", "cold", "coats"},
    "cook": {"cook", "coke", "look", "book", "hook", "cooks"},
    "cry": {"cry", "try", "fry", "dry", "cray", "cries"},
    "cub": {"cub", "cup", "cab", "club", "cubs"},
    "cube": {"cube", "cute", "tube", "cub", "cubs", "cubes"},
    "cut": {"cut", "cat", "cot", "cup", "gut", "cuts"},
    "cute": {"cute", "cube", "cut", "cat", "mute", "cutes"},
    "day": {"day", "they", "de", "pay", "bay", "days"},
    "few": {"few", "pew", "view", "flew", "fu", "fews"},
    "fly": {"fly", "fry", "fli", "ply", "flies"},
    "food": {"food", "foot", "feed", "good", "foods"},
    "foot": {"foot", "food", "fit", "boot", "feet", "foots"},
    "glue": {"glue", "blue", "gloo", "clue", "glues"},
    "green": {"green", "grin", "clean", "cream", "grain", "greens"},
    "grew": {"grew", "grow", "glue", "crew", "true", "grews"},
    "grow": {"grow", "glow", "go", "row", "grows"},
    "home": {"home", "hope", "comb", "hole", "homes"},
    "hop": {"hop", "hot", "pop", "top", "hope", "hops"},
    "hope": {"hope", "hop", "home", "hole", "rope", "hopes"},
    "kit": {"kit", "kid", "hit", "cat", "kite", "kits"},
    "kite": {"kite", "kit", "bite", "night", "tight", "kites"},
    "leaf": {"leaf", "leave", "live", "lift", "reef", "leafs"},
    "lie": {"lie", "line", "light", "lye", "lies"},
    "light": {"light", "lite", "night", "right", "white", "lights"},
    "look": {"look", "lock", "luck", "cook", "book", "looks"},
    "mad": {"mad", "mat", "man", "map", "made", "mads"},
    "made": {"made", "maid", "make", "mate", "mad", "mades"},
    "moon": {"moon", "noon", "mood", "room", "moons"},
    "my": {"my", "mine", "me", "mai", "by"},
    "new": {"new", "knew", "now", "no", "few", "news"},
    "night": {"night", "knight", "light", "right", "bite", "nights"},
    "not": {"not", "nut", "knot", "nod", "note", "nots"},
    "note": {"note", "not", "node", "boat", "wrote", "notes"},
    "pie": {"pie", "pi", "tie", "bye", "pies"},
    "pine": {"pine", "pin", "fine", "nine", "line", "pines"},
    "play": {"play", "clay", "pay", "pray", "place", "plays"},
    "pool": {"pool", "pull", "fool", "cool", "tool", "pools"},
    "rain": {"rain", "reign", "ran", "ring", "train", "rains"},
    "rid": {"rid", "red", "read", "ride", "rids"},
    "ride": {"ride", "rid", "side", "wide", "tide", "rides"},
    "road": {"road", "rode", "row", "load", "boat", "roads"},
    "rod": {"rod", "rot", "red", "rock", "rode", "rods"},
    "rode": {"rode", "road", "row", "rose", "rope", "rodes"},
    "sea": {"sea", "see", "c", "say", "she", "seas"},
    "see": {"see", "sea", "c", "seen", "she", "sees"},
    "slow": {"slow", "snow", "so", "low", "blow", "slows"},
    "snow": {"snow", "slow", "no", "now", "so", "snows"},
    "spoon": {"spoon", "soon", "spun", "moon", "spoons"},
    "stay": {"stay", "say", "day", "play", "state", "stays"},
    "tail": {"tail", "tale", "tell", "nail", "fail", "tails"},
    "tape": {"tape", "take", "cape", "tap", "type", "tapes"},
    "team": {"team", "teem", "tim", "time", "theme", "teams"},
    "theme": {"theme", "team", "seem", "fem", "themes"},
    "these": {"these", "this", "thees", "thes", "theses"},
    "tie": {"tie", "tai", "die", "pie", "tight", "ties"},
    "train": {"train", "rain", "chain", "drain", "track", "trains"},
    "tree": {"tree", "three", "tea", "free", "try", "trees"},
    "true": {"true", "through", "crew", "blue", "trues"},
    "tube": {"tube", "cube", "tub", "tooth", "tubes"},
"""

if 'Level 4 Words' not in api_code:
    insert_pos = api_code.find('}\n\n# ---------------------------------------------------------------- audio map')
    if insert_pos != -1:
        updated_api_code = api_code[:insert_pos] + l4_aliases_code + api_code[insert_pos:]
        with sftp_obj.open('/home/openhands/emma-phonics/api_server.py', 'w') as f:
            f.write(updated_api_code.encode('utf-8'))
        print("Updated WORD_ALIASES in api_server.py")
    else:
        print("Could not find insert position in api_server.py")
else:
    print("Level 4 Words already in api_server.py")
sftp_obj.close()

# 3. Restart emma-phonics.service
stdin, stdout, stderr = ssh.exec_command('echo "OpenHands@ERP2026" | sudo -S systemctl restart emma-phonics.service')
stdout.channel.recv_exit_status()

# 4. Verify service status
stdin, stdout, stderr = ssh.exec_command('systemctl status emma-phonics.service | head -n 12')
print("\nService status:")
print(stdout.read().decode())

ssh.close()
