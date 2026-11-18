import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

patch_script = """
import re

path = '/var/www/kidobits/theme/theme_home.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Check if already patched
if 'theme_phonicsHome.html' in content:
    print('Already contains theme_phonicsHome.html link!')
else:
    nav_patch = '''
<script>
// Intercept Phonics clicks from Hub to open Phonics Lobby
document.addEventListener('click', function(e) {
  const btn = e.target.closest('button, a');
  if (!btn) return;
  const txt = (btn.innerText || btn.textContent || '').trim();

  // 1. Phonics Hero Banner
  if (txt.includes('Kidobits Phonics') || txt.includes('เริ่มเรียนโฟนิกส์')) {
    e.preventDefault();
    e.stopPropagation();
    window.location.href = 'theme_phonicsHome.html';
    return;
  }

  // 2. Phonics Grid Button
  if (txt.includes('Phonics โฟนิกส์') || (txt.includes('Phonics') && txt.includes('โฟนิกส์'))) {
    e.preventDefault();
    e.stopPropagation();
    window.location.href = 'theme_phonicsHome.html';
    return;
  }

  // 3. Bottom nav Phonics button
  if (txt === 'Phonics' || (txt.includes('Phonics') && btn.closest('nav'))) {
    e.preventDefault();
    e.stopPropagation();
    window.location.href = 'theme_phonicsHome.html';
    return;
  }

  // 4. Lessons category button
  if (txt.includes('Lessons') && txt.includes('บทเรียน')) {
    e.preventDefault();
    e.stopPropagation();
    window.location.href = 'theme_phonicsHome.html';
    return;
  }
}, true);
</script>
</body>
'''
    new_content = content.replace('</body>', nav_patch)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Successfully patched theme_home.html to link theme_phonicsHome.html!')
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_home_nav.py', 'w') as f:
    f.write(patch_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S python3 /tmp/patch_home_nav.py")
print(stdout.read().decode('utf-8'))
print(stderr.read().decode('utf-8'))

# Set ownership
ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/theme/theme_home.html")
ssh.close()
