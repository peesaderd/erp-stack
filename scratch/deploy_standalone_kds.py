import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=30)
sftp = ssh.open_sftp()

# 1. Upload PosKdsStandalone.vue
sftp.put('scratch/PosKdsStandalone.vue', '/home/openhands/super-appsheet/frontend/src/views/PosKdsStandalone.vue')
print('Uploaded PosKdsStandalone.vue')

# 2. Upload PosRestodash.vue
sftp.put('scratch/PosRestodash.vue', '/home/openhands/super-appsheet/frontend/src/views/PosRestodash.vue')
print('Uploaded PosRestodash.vue')

# 3. Update main.js
with sftp.open('/home/openhands/super-appsheet/frontend/src/main.js', 'r') as f:
    main_code = f.read().decode('utf-8')

# Update /kitchen route
main_code = main_code.replace(
    '{ path: "/kitchen", name: "PosKitchenFullscreen", component: PosKitchenFullscreen },',
    '{ path: "/kitchen", name: "PosKitchenFullscreen", component: () => import("./views/PosKdsStandalone.vue") },'
)

# Add /pos/kds and /kds routes before /pos/restodash
kds_routes = '''  {
    path: '/pos/kds',
    name: 'PosKdsStandalone',
    component: () => import('./views/PosKdsStandalone.vue')
  },
  {
    path: '/kds',
    redirect: '/pos/kds'
  },
  {
    path: '/pos/restodash','''

if "path: '/pos/kds'" not in main_code:
    main_code = main_code.replace("  {\n    path: '/pos/restodash',", kds_routes)

with sftp.open('/home/openhands/super-appsheet/frontend/src/main.js', 'w') as f:
    f.write(main_code)
print('Updated main.js with Standalone KDS routes')

sftp.close()

# 4. Build Vite on Remote
print('Starting Vite build on remote...')
stdin, stdout, stderr = ssh.exec_command('cd /home/openhands/super-appsheet/frontend && npm run build')
build_out = stdout.read().decode('utf-8')
print('BUILD:\n', build_out)

# 5. Reload PM2
stdin, stdout, stderr = ssh.exec_command('pm2 reload super-appsheet-frontend')
print('PM2:\n', stdout.read().decode('utf-8'))

# 6. Git commit & push
cmd = 'cd /home/openhands/super-appsheet && git add frontend/src/views/PosKdsStandalone.vue frontend/src/views/PosRestodash.vue frontend/src/main.js && git commit -m "feat(kds): create dedicated standalone KDS screen at /pos/kds with live sound alerts, timers, and cashier sync" && git push origin theme/bakehouse'
stdin, stdout, stderr = ssh.exec_command(cmd)
print('GIT STDOUT:\n', stdout.read().decode('utf-8'))
print('GIT STDERR:\n', stderr.read().decode('utf-8'))

ssh.close()
print('All deployed successfully!')
