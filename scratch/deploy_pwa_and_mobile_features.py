import paramiko
import os

brain_dir = r'C:\Users\ADMIN\.gemini\antigravity\brain\00f15b47-0b14-4bb2-93bf-bae12846dfe6'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)
sftp = ssh.open_sftp()

# 1. Upload PWA Icons
for filename in ['pos-icon-512.png', 'pos-icon-192.png', 'pos-icon-maskable-512.png', 'favicon.png']:
    local_p = os.path.join(brain_dir, filename)
    remote_p = f'/home/openhands/super-appsheet/frontend/public/images/{filename}'
    sftp.put(local_p, remote_p)
    print(f'Uploaded {filename} -> {remote_p}')

# Also upload favicon to public/favicon.ico
sftp.put(os.path.join(brain_dir, 'favicon.png'), '/home/openhands/super-appsheet/frontend/public/favicon.ico')

# 2. Upload PosRestodash.vue
sftp.put('scratch/PosRestodash.vue', '/home/openhands/super-appsheet/frontend/src/views/PosRestodash.vue')
print('Uploaded PosRestodash.vue')

# 3. Write manifest.webmanifest
manifest_content = '''{
  "name": "Restodash Smart POS",
  "short_name": "Restodash",
  "description": "ระบบ POS ร้านอาหารและแจ้งเตือนออเดอร์เรียลไทม์",
  "id": "/pos/restodash",
  "start_url": "/pos/restodash",
  "scope": "/",
  "display": "standalone",
  "background_color": "#0F172A",
  "theme_color": "#1D4ED8",
  "lang": "th",
  "dir": "ltr",
  "orientation": "any",
  "categories": ["business", "food"],
  "icons": [
    {
      "src": "/images/pos-icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "/images/pos-icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "/images/pos-icon-maskable-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    }
  ],
  "shortcuts": [
    {
      "name": "หน้าร้าน POS",
      "short_name": "POS",
      "description": "เปิดหน้าสั่งอาหารและคิดเงิน POS",
      "url": "/pos/restodash",
      "icons": [{ "src": "/images/pos-icon-192.png", "sizes": "192x192" }]
    },
    {
      "name": "จอครัว (KDS)",
      "short_name": "Kitchen",
      "description": "เปิดหน้าดูออเดอร์ครัว",
      "url": "/pos/kitchen",
      "icons": [{ "src": "/images/pos-icon-192.png", "sizes": "192x192" }]
    }
  ]
}
'''
with sftp.open('/home/openhands/super-appsheet/frontend/public/manifest.webmanifest', 'w') as f:
    f.write(manifest_content)
print('Updated manifest.webmanifest')

# 4. Update index.html for favicon
with sftp.open('/home/openhands/super-appsheet/frontend/index.html', 'r') as f:
    html = f.read().decode('utf-8')

html = html.replace(
    '''<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📋</text></svg>" />''',
    '''<link rel="icon" type="image/png" href="/images/pos-icon-192.png" />'''
)
html = html.replace('<meta name="theme-color" content="#111827" />', '<meta name="theme-color" content="#1D4ED8" />')

with sftp.open('/home/openhands/super-appsheet/frontend/index.html', 'w') as f:
    f.write(html)
print('Updated index.html')

sftp.close()

# 5. Build Vite on Remote
print('Starting Vite build on remote...')
stdin, stdout, stderr = ssh.exec_command('cd /home/openhands/super-appsheet/frontend && npm run build')
print('BUILD:\n', stdout.read().decode('utf-8'))

# 6. Reload PM2
stdin, stdout, stderr = ssh.exec_command('pm2 reload super-appsheet-frontend')
print('PM2:\n', stdout.read().decode('utf-8'))

# 7. Git commit & push
cmd = 'cd /home/openhands/super-appsheet && git add frontend/public/images/ frontend/public/manifest.webmanifest frontend/index.html frontend/src/views/PosRestodash.vue && git commit -m "feat(pwa): update PWA icons, bottom nav, mobile responsive settings, and direct table payment" && git push origin theme/bakehouse'
stdin, stdout, stderr = ssh.exec_command(cmd)
print('GIT STDOUT:\n', stdout.read().decode('utf-8'))
print('GIT STDERR:\n', stderr.read().decode('utf-8'))

ssh.close()
print('Finished all deployments!')
