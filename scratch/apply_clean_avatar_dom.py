import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='ignore'), stderr.read().decode('utf-8', errors='ignore')

clean_fix_code = '''
with open('/var/www/kidobits/theme/js/kidobits_real_sync.js', 'r', encoding='utf-8') as f:
    c = f.read()

# Replace avatar rendering in initProfilePage
import re

profile_render_clean = """        // 2. Update Avatar Circle in Profile Header Card
        const avatarCircle = document.querySelector('.w-24.h-24.rounded-full') || document.querySelector('div[class*="w-24"][class*="h-24"]');
        if (avatarCircle && avatarConfig && avatarConfig.avatar_url) {
          const url = avatarConfig.avatar_url;
          if (url.startsWith('http') || url.startsWith('data:')) {
            const existingImg = avatarCircle.querySelector('img');
            if (!existingImg || existingImg.getAttribute('data-src') !== url) {
              avatarCircle.className = 'w-24 h-24 rounded-full bg-white mx-auto border-4 border-white shadow overflow-hidden mt-2 flex items-center justify-center';
              avatarCircle.innerHTML = '';
              const img = document.createElement('img');
              img.setAttribute('data-src', url);
              img.src = url;
              img.className = 'w-full h-full rounded-full object-cover';
              img.onerror = function() {
                avatarCircle.innerHTML = '<span class="text-5xl">' + (avatarConfig.face || '👦') + '</span>';
              };
              avatarCircle.appendChild(img);
            }
          } else if (avatarConfig.face) {
            if (!avatarCircle.querySelector('img')) {
              avatarCircle.innerHTML = '<span class="text-5xl">' + avatarConfig.face + '</span>';
            }
          }
        }"""

pattern = r'// 2\. Update Avatar Circle in Profile Header Card.*?avatarCircle\.appendChild\(img\);.*?}\s*}\s*}'
# If that pattern doesn't match cleanly, let's find the section
start_marker = '// 2. Update Avatar Circle in Profile Header Card'
end_marker = '// 3. Sync real stars, streak, lessons'

idx_start = c.find(start_marker)
idx_end = c.find(end_marker)

if idx_start != -1 and idx_end != -1:
    c = c[:idx_start] + profile_render_clean + '\n\n        ' + c[idx_end:]
    print('Clean profile avatar rendering replaced!')
else:
    print('Markers not found:', idx_start, idx_end)

with open('/var/www/kidobits/theme/js/kidobits_real_sync.js', 'w', encoding='utf-8') as f:
    f.write(c)

with open('/var/www/kidobits/js/kidobits_real_sync.js', 'w', encoding='utf-8') as f:
    f.write(c)

print('Updated both files with DOM image creation!')
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/clean_avatar_fix.py', 'w') as f:
    f.write(clean_fix_code)
sftp.close()

out, err = run("sudo python3 /tmp/clean_avatar_fix.py")
print("=== CLEAN FIX RESULT ===")
print(out, err)

ssh.close()
