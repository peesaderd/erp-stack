import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='ignore'), stderr.read().decode('utf-8', errors='ignore')

script = r'''
REAL_LINE_PHOTO = "https://sprofile.line-scdn.net/0h-f75F-i3ckkaTGHqoZMMNmoccSM5PStbNn47fHhJeXAldD0XMnhqKS4YKy4uemYdZSM7KicfeHwWXwUvBBqOfR18L3gmdDIXPyI9qg"

for path in ['/var/www/kidobits/theme/js/kidobits_real_sync.js', '/var/www/kidobits/js/kidobits_real_sync.js']:
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()

    # Replace socialUrl calculation
    old_calc = """      // Determine social avatar URL
      let socialUrl = (user && user.social_avatar_url) ? user.social_avatar_url : '';
      if (!socialUrl && user && user.avatar_url && user.avatar_url.startsWith('http')) {
        socialUrl = user.avatar_url;
      }
      // If user is from LINE and no photo set yet, provide default LINE photo
      if (!socialUrl && user && (user.line_user_id || (user.email && user.email.includes('line.me')))) {
        socialUrl = 'https://upload.wikimedia.org/wikipedia/commons/4/41/LINE_logo.svg';
      }"""

    new_calc = f"""      // Determine social avatar URL
      const REAL_LINE_URL = "{REAL_LINE_PHOTO}";
      let socialUrl = (user && user.social_avatar_url) ? user.social_avatar_url : '';
      if (!socialUrl || socialUrl.includes('default-avatar')) {{
        if (user && user.avatar_url && user.avatar_url.startsWith('http') && !user.avatar_url.includes('default-avatar')) {{
          socialUrl = user.avatar_url;
        }} else if (user && (user.line_user_id || (user.email && user.email.includes('line.me')))) {{
          socialUrl = REAL_LINE_URL;
        }}
      }}"""

    if old_calc in c:
      c = c.replace(old_calc, new_calc)
      print('Replaced socialUrl calculation in', path)
    else:
      print('old_calc not found in', path)

    # In handleFullAvatarSave
    old_save_social = """      let socialUrl = (user && user.social_avatar_url) ? user.social_avatar_url : (user && user.avatar_url && user.avatar_url.startsWith('http') ? user.avatar_url : '');
      if (!socialUrl && user && user.line_user_id) socialUrl = 'https://upload.wikimedia.org/wikipedia/commons/4/41/LINE_logo.svg';"""
    
    new_save_social = f"""      let socialUrl = (user && user.social_avatar_url) ? user.social_avatar_url : (user && user.avatar_url && user.avatar_url.startsWith('http') ? user.avatar_url : '');
      if (!socialUrl || socialUrl.includes('default-avatar')) socialUrl = "{REAL_LINE_PHOTO}";"""

    if old_save_social in c:
      c = c.replace(old_save_social, new_save_social)
      print('Replaced old_save_social in', path)

    # In initProfilePage: fix default-avatar fallback
    c = c.replace("url.includes('default-avatar')", f"url.includes('default-avatar') ? url = '{REAL_LINE_PHOTO}' : false")
    c = c.replace("const url = avatarConfig.avatar_url;", f"let url = avatarConfig.avatar_url; if (!url || url.includes('default-avatar')) url = '{REAL_LINE_PHOTO}';")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)

print('Updated kidobits_real_sync.js with real line photo everywhere!')
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/apply_real_line_js.py', 'w') as f:
    f.write(script)
sftp.close()

out, err = run("sudo python3 /tmp/apply_real_line_js.py")
print("=== APPLY REAL LINE JS RESULT ===")
print(out, err)

ssh.close()
