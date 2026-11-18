import paramiko
import json

def run():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)
    sftp = ssh.open_sftp()

    # --- 1. Update manifest.json: orientation -> portrait (via tmp + sudo cp) ---
    manifest_raw = sftp.file('/var/www/kidobits/manifest.json', 'r').read().decode('utf-8')
    manifest = json.loads(manifest_raw)
    manifest['orientation'] = 'portrait'
    manifest_new = json.dumps(manifest, ensure_ascii=False, indent=2)
    with sftp.file('/tmp/manifest.json', 'w') as f:
        f.write(manifest_new.encode('utf-8'))
    stdin, stdout, stderr = ssh.exec_command('echo "OpenHands@ERP2026" | sudo -S cp /tmp/manifest.json /var/www/kidobits/manifest.json && echo "OpenHands@ERP2026" | sudo -S chmod 664 /var/www/kidobits/manifest.json')
    stdout.read(); stderr.read()
    print("manifest.json updated: orientation=portrait")

    # --- 2. Pages to patch: add manifest link + device_orientation.js ---
    # Each tuple: (remote_path, injection_anchor, inject_manifest)
    pages = [
        '/var/www/kidobits/theme/theme_phonicsLesson.html',
        '/var/www/kidobits/theme/theme_math_lobby.html',
        '/var/www/kidobits/theme/theme_chinese_lobby.html',
        '/var/www/kidobits/theme/theme_phonicsHome.html',
        '/var/www/kidobits/theme/theme_phonicsLevel.html',
        '/var/www/kidobits/theme/theme_oliver_hub.html',
    ]

    # Snippet to inject right before </head>
    # For pages that already have manifest, skip that line
    DEVICE_JS_TAG = '  <script src="/theme/js/kidobits_device_orientation.js"></script>\n'
    MANIFEST_TAG  = '  <link rel="manifest" href="/manifest.json">\n'

    for page in pages:
        try:
            html = sftp.file(page, 'r').read().decode('utf-8')
        except Exception as e:
            print(f"SKIP {page}: {e}")
            continue

        changed = False

        # Add manifest link if not present
        if 'rel="manifest"' not in html:
            # Inject right before </head>
            html = html.replace('</head>', MANIFEST_TAG + '</head>', 1)
            changed = True
            print(f"  + manifest tag added: {page}")

        # Add device_orientation.js if not present
        if 'kidobits_device_orientation.js' not in html:
            html = html.replace('</head>', DEVICE_JS_TAG + '</head>', 1)
            changed = True
            print(f"  + device_orientation.js tag added: {page}")

        if changed:
            with sftp.file('/tmp/_kb_patch.html', 'w') as f:
                f.write(html.encode('utf-8'))
            basename = page.split('/')[-1]
            stdin, stdout, stderr = ssh.exec_command(f'echo "OpenHands@ERP2026" | sudo -S cp /tmp/_kb_patch.html {page} && echo "OpenHands@ERP2026" | sudo -S chmod 775 {page}')
            stdout.read(); stderr.read()
            print(f"  Saved: {page}")
        else:
            print(f"  No change needed: {page}")

    sftp.close()
    ssh.close()
    print("\nAll done!")

if __name__ == '__main__':
    run()
