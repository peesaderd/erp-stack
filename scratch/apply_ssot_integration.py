import paramiko

def patch_ssot_integration():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)
    sftp = ssh.open_sftp()
    
    SSOT_SCRIPT_TAG = '  <script src="/theme/js/kidobits_student_ssot.js"></script>\n'

    # --- 1. theme_home.html ---
    home_html = sftp.file('/var/www/kidobits/theme/theme_home.html', 'r').read().decode('utf-8')
    if '/theme/js/kidobits_student_ssot.js' not in home_html:
        home_html = home_html.replace('</head>', SSOT_SCRIPT_TAG + '</head>', 1)
    
    # Set default text to Putter
    home_html = home_html.replace('Hello, น้องเอ็มม่า 👋', 'Hello, Putter 👋')
    home_html = home_html.replace('Hello, Peesaderd 👋', 'Hello, Putter 👋')
    
    # Update syncHeader to use KidobitsStudent.getName()
    home_html = home_html.replace(
        "displayName = (user.student_name || user.child_name || user.nickname).trim();",
        "displayName = (window.KidobitsStudent ? KidobitsStudent.getName() : 'Putter');"
    )
    
    with sftp.file('/tmp/theme_home.html', 'w') as f:
        f.write(home_html.encode('utf-8'))
    stdin, stdout, stderr = ssh.exec_command('echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_home.html /var/www/kidobits/theme/theme_home.html && echo "OpenHands@ERP2026" | sudo -S chmod 775 /var/www/kidobits/theme/theme_home.html')
    stdout.read(); stderr.read()
    print("1. theme_home.html patched with SSOT")

    # --- 2. kidobits_real_sync.js ---
    sync_js = sftp.file('/var/www/kidobits/theme/js/kidobits_real_sync.js', 'r').read().decode('utf-8')
    # Where student name is saved in handleFullAvatarSave
    old_save_snippet = "localStorage.setItem(STUDENT_KEY, JSON.stringify(studentData));"
    new_save_snippet = """localStorage.setItem(STUDENT_KEY, JSON.stringify(studentData));
      if (window.KidobitsStudent && KidobitsStudent.saveProfile) {
        KidobitsStudent.saveProfile(studentData);
      }"""
    if old_save_snippet in sync_js and "KidobitsStudent.saveProfile" not in sync_js:
        sync_js = sync_js.replace(old_save_snippet, new_save_snippet)
        with sftp.file('/tmp/kidobits_real_sync.js', 'w') as f:
            f.write(sync_js.encode('utf-8'))
        cmd = ('echo "OpenHands@ERP2026" | sudo -S cp /tmp/kidobits_real_sync.js /var/www/kidobits/theme/js/kidobits_real_sync.js && '
               'echo "OpenHands@ERP2026" | sudo -S cp /tmp/kidobits_real_sync.js /var/www/kidobits/js/kidobits_real_sync.js && '
               'echo "OpenHands@ERP2026" | sudo -S chmod 664 /var/www/kidobits/theme/js/kidobits_real_sync.js /var/www/kidobits/js/kidobits_real_sync.js')
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read(); stderr.read()
        print("2. kidobits_real_sync.js patched with SSOT")

    # --- 3. theme_profile.html ---
    # Add SSOT script tag to theme_profile.html
    profile_html = sftp.file('/var/www/kidobits/theme/theme_profile.html', 'r').read().decode('utf-8')
    if '/theme/js/kidobits_student_ssot.js' not in profile_html:
        profile_html = profile_html.replace('</head>', SSOT_SCRIPT_TAG + '</head>', 1)
        # Also ensure syncThemeAuth calls KidobitsStudent.syncDOM()
        old_sync_call = "function syncThemeAuth() {"
        new_sync_call = "function syncThemeAuth() {\n    if (window.KidobitsStudent) KidobitsStudent.syncDOM();"
        profile_html = profile_html.replace(old_sync_call, new_sync_call, 1)
        
        with sftp.file('/tmp/theme_profile.html', 'w') as f:
            f.write(profile_html.encode('utf-8'))
        stdin, stdout, stderr = ssh.exec_command('echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_profile.html /var/www/kidobits/theme/theme_profile.html && echo "OpenHands@ERP2026" | sudo -S chmod 775 /var/www/kidobits/theme/theme_profile.html')
        stdout.read(); stderr.read()
        print("3. theme_profile.html patched with SSOT")

    # --- 4. Other theme pages ---
    other_pages = [
        '/var/www/kidobits/theme/theme_phonicsLesson.html',
        '/var/www/kidobits/theme/theme_chinese_lobby.html',
        '/var/www/kidobits/theme/theme_math_lobby.html',
        '/var/www/kidobits/theme/theme_phonicsHome.html',
        '/var/www/kidobits/theme/theme_phonicsLevel.html',
        '/var/www/kidobits/theme/theme_level2.html',
        '/var/www/kidobits/theme/theme_level3.html',
        '/var/www/kidobits/theme/theme_oliver_hub.html'
    ]
    for p in other_pages:
        try:
            content = sftp.file(p, 'r').read().decode('utf-8')
            if '/theme/js/kidobits_student_ssot.js' not in content:
                content = content.replace('</head>', SSOT_SCRIPT_TAG + '</head>', 1)
                with sftp.file('/tmp/_kb_ssot_patch.html', 'w') as f:
                    f.write(content.encode('utf-8'))
                stdin, stdout, stderr = ssh.exec_command(f'echo "OpenHands@ERP2026" | sudo -S cp /tmp/_kb_ssot_patch.html {p} && echo "OpenHands@ERP2026" | sudo -S chmod 775 {p}')
                stdout.read(); stderr.read()
                print(f"  + Added SSOT to {p}")
        except Exception as e:
            print(f"  Error on {p}: {e}")

    sftp.close()
    ssh.close()
    print("\nSSOT Integration fully applied!")

if __name__ == '__main__':
    patch_ssot_integration()
