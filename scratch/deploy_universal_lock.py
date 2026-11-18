import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=10)

sftp = ssh.open_sftp()

# 1. Upload new kidobits_curriculum_lock.js to /tmp
with open(r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\new_kidobits_curriculum_lock.js', 'rb') as f:
    sftp.putfo(f, '/tmp/kidobits_curriculum_lock.js')

print("Uploaded /tmp/kidobits_curriculum_lock.js")

# 2. Update theme_phonicsLevel.html
with sftp.open('/var/www/kidobits/theme/theme_phonicsLevel.html', 'r') as f:
    phonics_html = f.read().decode('utf-8')

old_p_lock = "const isUnlocked = window.KidobitsLock ? KidobitsLock.isUnlocked('phonics', lessonIdx) : (lessonIdx === 1);"
new_p_lock = "const isUnlocked = window.KidobitsLock ? KidobitsLock.isUnlocked('phonics', lv, lessonIdx) : (lessonIdx === 1);"
old_p_comp = "const isCompleted = window.KidobitsLock ? KidobitsLock.isCompleted('phonics', item.id) : false;"
new_p_comp = "const isCompleted = window.KidobitsLock ? KidobitsLock.isCompleted('phonics', lv, item.id) : false;"

phonics_html = phonics_html.replace(old_p_lock, new_p_lock, 1)
phonics_html = phonics_html.replace(old_p_comp, new_p_comp, 1)

with sftp.open('/tmp/theme_phonicsLevel.html', 'w') as f:
    f.write(phonics_html)
print("Updated /tmp/theme_phonicsLevel.html")

# 3. Update theme_chinese_lobby.html
with sftp.open('/var/www/kidobits/theme/theme_chinese_lobby.html', 'r') as f:
    chinese_html = f.read().decode('utf-8')

old_c_lock = "const isUnlocked = window.KidobitsLock ? KidobitsLock.isUnlocked('chinese', lessonIdx) : (lessonIdx === 1);"
new_c_lock = "const isUnlocked = window.KidobitsLock ? KidobitsLock.isUnlocked('chinese', tier.key, lessonIdx) : (lessonIdx === 1);"
old_c_comp = "const isCompleted = window.KidobitsLock ? KidobitsLock.isCompleted('chinese', les.id) : (savedStars > 0);"
new_c_comp = "const isCompleted = window.KidobitsLock ? KidobitsLock.isCompleted('chinese', tier.key, les.id) : (savedStars > 0);"

chinese_html = chinese_html.replace(old_c_lock, new_c_lock, 1)
chinese_html = chinese_html.replace(old_c_comp, new_c_comp, 1)

with sftp.open('/tmp/theme_chinese_lobby.html', 'w') as f:
    f.write(chinese_html)
print("Updated /tmp/theme_chinese_lobby.html")

sftp.close()

# 4. Copy to production and commit
cmd = """
echo 'OpenHands@ERP2026' | sudo -S cp /tmp/kidobits_curriculum_lock.js /var/www/kidobits/theme/js/kidobits_curriculum_lock.js
echo 'OpenHands@ERP2026' | sudo -S cp /tmp/theme_phonicsLevel.html /var/www/kidobits/theme/theme_phonicsLevel.html
echo 'OpenHands@ERP2026' | sudo -S cp /tmp/theme_chinese_lobby.html /var/www/kidobits/theme/theme_chinese_lobby.html
echo 'OpenHands@ERP2026' | sudo -S chown www-data:www-data /var/www/kidobits/theme/js/kidobits_curriculum_lock.js /var/www/kidobits/theme/theme_phonicsLevel.html /var/www/kidobits/theme/theme_chinese_lobby.html
cd /var/www/kidobits
git status --short
git diff --stat
git add theme/js/kidobits_curriculum_lock.js theme/theme_phonicsLevel.html theme/theme_chinese_lobby.html
git commit -m "feat(curriculum): upgrade KidobitsLock to universal hierarchical level & placement engine"
git push origin main
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))

ssh.close()
