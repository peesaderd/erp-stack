import paramiko
import re

css_content = """/* Kidobits Universal Font System (Profile Standard)
 * English & Display: Baloo 2 (Rounded, friendly kids font)
 * Thai & Body: Prompt (Clean, modern Thai font)
 */
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700;800&family=Prompt:wght@400;500;600;700;800&display=swap');

html, body, button, input, select, textarea {
  font-family: 'Baloo 2', 'Prompt', system-ui, -apple-system, sans-serif !important;
}

.font-thai {
  font-family: 'Prompt', 'Baloo 2', sans-serif !important;
}

.font-display {
  font-family: 'Baloo 2', 'Prompt', sans-serif !important;
}
"""

def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)
    sftp = ssh.open_sftp()

    # 1. Upload kidobits_fonts.css
    with sftp.file('/tmp/kidobits_fonts.css', 'w') as f:
        f.write(css_content.encode('utf-8'))
    
    cmd = ('echo "OpenHands@ERP2026" | sudo -S cp /tmp/kidobits_fonts.css /var/www/kidobits/theme/kidobits_fonts.css '
           '&& echo "OpenHands@ERP2026" | sudo -S cp /tmp/kidobits_fonts.css /var/www/kidobits/kidobits_fonts.css '
           '&& echo "OpenHands@ERP2026" | sudo -S chmod 664 /var/www/kidobits/theme/kidobits_fonts.css /var/www/kidobits/kidobits_fonts.css')
    stdin, stdout, stderr = ssh.exec_command(cmd)
    stdout.read(); stderr.read()
    print("1. kidobits_fonts.css created and deployed.")

    # 2. Patch theme_home.html for Student Name greeting & font
    home_html = sftp.file('/var/www/kidobits/theme/theme_home.html', 'r').read().decode('utf-8')
    
    # Change hardcoded Peesaderd to น้องเอ็มม่า
    home_html = home_html.replace('Hello, Peesaderd 👋', 'Hello, น้องเอ็มม่า 👋')
    
    # Update displayName logic in syncHeader
    old_greeting_logic = """        let displayName = '';
        if (student && student.displayPreference === 'parent' && user && user.name) {
          displayName = user.name;
        } else if (student && student.name && student.name.trim()) {
          displayName = student.name.trim();
        } else if (user && user.name) {
          displayName = user.name;
        } else {
          displayName = 'น้องเอ็มม่า';
        }"""

    new_greeting_logic = """        let displayName = '';
        // Always prioritize Student Name (never show Parent name in Hello greeting)
        if (student && student.name && student.name.trim()) {
          displayName = student.name.trim();
        } else if (student && student.nickname && student.nickname.trim()) {
          displayName = student.nickname.trim();
        } else if (user && (user.student_name || user.child_name || user.nickname)) {
          displayName = (user.student_name || user.child_name || user.nickname).trim();
        } else {
          displayName = 'น้องเอ็มม่า';
        }"""

    if old_greeting_logic in home_html:
        home_html = home_html.replace(old_greeting_logic, new_greeting_logic)
        print("2. Replaced greeting logic in theme_home.html")
    else:
        # Fallback regex replace
        pattern = r"let displayName = '';[\s\S]*?displayName = 'น้องเอ็มม่า';\s*\}"
        home_html = re.sub(pattern, new_greeting_logic, home_html)
        print("2. Regex replaced greeting logic in theme_home.html")

    # Add font stylesheet to theme_home.html if not present
    FONT_TAG = '  <link rel="stylesheet" href="/theme/kidobits_fonts.css">\n'
    if '/theme/kidobits_fonts.css' not in home_html:
        home_html = home_html.replace('</head>', FONT_TAG + '</head>', 1)
        print("2. Added kidobits_fonts.css link to theme_home.html")

    with sftp.file('/tmp/theme_home.html', 'w') as f:
        f.write(home_html.encode('utf-8'))
    stdin, stdout, stderr = ssh.exec_command('echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_home.html /var/www/kidobits/theme/theme_home.html && echo "OpenHands@ERP2026" | sudo -S chmod 775 /var/www/kidobits/theme/theme_home.html')
    stdout.read(); stderr.read()
    print("2. theme_home.html saved!")

    # 3. Add font stylesheet link to other main theme pages
    pages = [
        '/var/www/kidobits/theme/theme_phonicsLesson.html',
        '/var/www/kidobits/theme/theme_chinese_lobby.html',
        '/var/www/kidobits/theme/theme_math_lobby.html',
        '/var/www/kidobits/theme/theme_phonicsHome.html',
        '/var/www/kidobits/theme/theme_phonicsLevel.html',
        '/var/www/kidobits/theme/theme_level2.html',
        '/var/www/kidobits/theme/theme_level3.html',
        '/var/www/kidobits/theme/theme_oliver_hub.html',
        '/var/www/kidobits/theme/theme_games.html',
        '/var/www/kidobits/theme/theme_profile.html'
    ]

    for p in pages:
        try:
            content = sftp.file(p, 'r').read().decode('utf-8')
            if '/theme/kidobits_fonts.css' not in content:
                content = content.replace('</head>', FONT_TAG + '</head>', 1)
                with sftp.file('/tmp/_kb_font_patch.html', 'w') as f:
                    f.write(content.encode('utf-8'))
                stdin, stdout, stderr = ssh.exec_command(f'echo "OpenHands@ERP2026" | sudo -S cp /tmp/_kb_font_patch.html {p} && echo "OpenHands@ERP2026" | sudo -S chmod 775 {p}')
                stdout.read(); stderr.read()
                print(f"  + Added font link to {p}")
            else:
                print(f"  - Font link already in {p}")
        except Exception as e:
            print(f"  Error on {p}: {e}")

    sftp.close()
    ssh.close()
    print("\nAll fonts and greeting successfully updated!")

if __name__ == '__main__':
    deploy()
