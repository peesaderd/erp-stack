import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_patch = """
path = '/var/www/kidobits/theme/theme_phonicsLesson.html'
with open(path, 'r', encoding='utf-8') as f:
    html = f.read()

target = '''        // Play initial audio script from API (Filter out word spoiler for Step 1 Blending)
        const script1 = (currentItem && currentItem.step === 1)
          ? (currentScript || []).filter(it => !String(typeof it === 'string' ? it : (it.say || '')).includes('word_'))
          : currentScript;'''

replacement = '''        // Play initial audio script from API (Filter out word spoiler for Step 1 Blending)
        let script1 = (currentItem && currentItem.step === 1)
          ? (currentScript || []).filter(it => !String(typeof it === 'string' ? it : (it.say || '')).includes('word_'))
          : currentScript;

        // Hello friends greeting filter: Only play once per session
        try {
          const hasGreeted = sessionStorage.getItem('kidobits_has_greeted') === '1';
          if (hasGreeted) {
            script1 = (script1 || []).filter(it => {
              const u = String(typeof it === 'string' ? it : (it.say || ''));
              return !u.includes('teach_intro');
            });
          } else {
            const hasIntro = (script1 || []).some(it => {
              const u = String(typeof it === 'string' ? it : (it.say || ''));
              return u.includes('teach_intro');
            });
            if (hasIntro) {
              sessionStorage.setItem('kidobits_has_greeted', '1');
            }
          }
        } catch(e) { console.warn('sessionStorage error', e); }'''

if target in html:
    html = html.replace(target, replacement)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print("Successfully patched theme_phonicsLesson.html with session-based greeting!")
else:
    print("Target string not found in theme_phonicsLesson.html")
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/patch_greeting_session.py', 'w') as f:
    f.write(remote_patch)
sftp.close()

stdin, stdout, stderr = ssh.exec_command("echo 'OpenHands@ERP2026' | sudo -S python3 /tmp/patch_greeting_session.py")
print(stdout.read().decode('utf-8'))
print(stderr.read().decode('utf-8'))

# Also sync to local copy
sftp = ssh.open_sftp()
sftp.get('/var/www/kidobits/theme/theme_phonicsLesson.html', 'Kidobits/theme/theme_phonicsLesson.html')
sftp.close()
ssh.close()
print("Local copy synced.")
