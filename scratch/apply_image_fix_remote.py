import paramiko
import json
import os

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = """
import json
import os
import shutil
import base64
import io
from PIL import Image

# 1. Load mapping
with open('/tmp/l5_final_mapping.json') as f:
    mapping = json.load(f)

# Old file name in /var/www/kidobits/v2/images/ -> true word name
IMG_DIR = '/var/www/kidobits/v2/images'
TEMP_DIR = '/tmp/fixed_images'
os.makedirs(TEMP_DIR, exist_ok=True)

# Copy all original images to temp with their true names
# mapping: {old_key: true_word}
# e.g. "bird": "car" -> /var/www/kidobits/v2/images/bird.png is actually car.png!
# e.g. "car": "star" -> /var/www/kidobits/v2/images/car.png is actually star.png!
# e.g. "park": "fork" -> /var/www/kidobits/v2/images/park.png is actually fork.png!
# e.g. "fork": "park" -> /var/www/kidobits/v2/images/fork.png is actually park.png!

# Let's read the original base64 from lesson.html directly to ensure zero degradation or overwrite conflict!
import re
with open('/var/www/kidobits/v2/lesson.html', 'r', encoding='utf-8') as f:
    text = f.read()

pos = text.find('const L5_IMG')
end_pos = text.find('};', pos)
chunk = text[pos:end_pos+2]
matches = dict(re.findall(r'"([a-zA-Z0-9_-]+)"\s*:\s*"data:image/[^;]+;base64,([^"]+)"', chunk))

# Manual overrides for any edge cases we personally verified
overrides = {
    'bird': 'car',      # red car
    'bear': 'toy',      # toy car
    'car': 'star',      # yellow star
    'star': 'girl',     # girl in yellow dress
    'girl': 'her',      # girl pointing to herself
    'chair': 'farm',    # farmhouse/barn
    'turn': 'chair',    # chair
    'park': 'fork',     # fork
    'fork': 'park',     # park with bench
    'fern': 'short',    # short pencil
    'short': 'burn',    # campfire/burn
    'air': 'fern',      # fern potted plant
    'burn': 'air',      # wind blowing cloud
    'blew': 'school',   # school building
    'boil': 'fair',     # fun fair ferris wheel
    'brown': 'paw',     # animal paw
    'cage': 'lamb',     # cute lamb
    'candle': 'phone',  # smartphone
    'lamb': 'candle',   # burning candle
    'cow': 'city',      # city skyscrapers
    'cloud': 'cow',     # cow with bell
    'city': 'sauce',    # sauce bottle
    'saw': 'giant',     # blue giant monster
    'small': 'tree',    # green tree in hands
    'boy': 'soil',      # plant in soil / earth
    'giant': 'coin',    # gold coin
    'cent': 'gem',      # shiny gem
}

for k, v in overrides.items():
    mapping[k] = v

count = 0
for old_key, true_word in mapping.items():
    if old_key in matches:
        b64_data = matches[old_key]
        raw_bytes = base64.b64decode(b64_data)
        out_file = os.path.join(IMG_DIR, f"{true_word.lower().strip()}.png")
        with open(out_file, 'wb') as out_f:
            out_f.write(raw_bytes)
        count += 1

print(f"Directly wrote {count} corrected images to {IMG_DIR}!")

# Update cache buster in theme_phonicsLesson.html to ?v=5 so all client browsers reload immediately!
with open('/var/www/kidobits/theme/theme_phonicsLesson.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('.png?v=2', '.png?v=5').replace('.png?v=3', '.png?v=5').replace('.png?v=4', '.png?v=5')

with open('/var/www/kidobits/theme/theme_phonicsLesson.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Updated theme_phonicsLesson.html cache buster to ?v=5!")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/apply_image_fix.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S python3 /tmp/apply_image_fix.py")
print(stdout.read().decode())
print(stderr.read().decode())

# Chown permissions
stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S chown -R www-data:www-data /var/www/kidobits/v2/images /var/www/kidobits/theme")
stdout.channel.recv_exit_status()
ssh.close()
