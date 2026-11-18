import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_py = '''
import re

files = [
    '/var/www/kidobits/theme/theme_home.html',
    '/var/www/kidobits/theme/theme_phonicsHome.html',
    '/var/www/kidobits/theme/theme_phonicsLevel.html',
    '/var/www/kidobits/theme/theme_azPlayer.html',
]

snippet = """<style>
/* Never show player feedback pill in the Phonics Lobby */
button[class*="border-[#FF9A4D]"] + p[class*="bg-[#E8FFF0]"] {
  display: none !important;
}
</style>
<script src="/kidobits/js/kb-az-engine.js?v=20261111_v999"></script>
<script src="/kidobits/js/kb-lesson.v2.js?v=20261111_v999"></script>
"""

for path in files:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    # Remove any existing kb-az-engine or kb-lesson script tags or injected style
    text = re.sub(r'<style>\s*/\* Never show player feedback.*?<\/style>\s*', '', text, flags=re.DOTALL)
    text = re.sub(r'<script src="/kidobits/js/kb-az-engine.*?></script>\s*', '', text)
    text = re.sub(r'<script src="/kidobits/js/kb-lesson.*?></script>\s*', '', text)

    # Insert snippet before <title>
    pos = text.find('<title>')
    if pos != -1:
        text = text[:pos] + snippet + text[pos:]
    else:
        # Fallback to after <head>
        hpos = text.find('<head>') + 6
        text = text[:hpos] + snippet + text[hpos:]

    tmp_path = '/tmp/' + path.split('/')[-1]
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"Prepared {tmp_path}, len: {len(text)}")
'''

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_all_themes.py', 'w') as f:
    f.write(remote_py)
sftp.close()

cmd = '''python3 /tmp/patch_all_themes.py && echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_home.html /var/www/kidobits/theme/theme_home.html && echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_phonicsHome.html /var/www/kidobits/theme/theme_phonicsHome.html && echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_phonicsLevel.html /var/www/kidobits/theme/theme_phonicsLevel.html && echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_azPlayer.html /var/www/kidobits/theme/theme_azPlayer.html && echo "OpenHands@ERP2026" | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_*.html'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print("Result:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
ssh.close()
