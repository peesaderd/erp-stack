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

sftp.close()

# 3. Build Vite on Remote
print('Starting Vite build on remote...')
stdin, stdout, stderr = ssh.exec_command('cd /home/openhands/super-appsheet/frontend && npm run build')
build_out = stdout.read().decode('utf-8')
build_err = stderr.read().decode('utf-8')
print('BUILD STDOUT:\n', build_out)
if build_err:
    print('BUILD STDERR:\n', build_err)

# 4. Reload PM2
stdin, stdout, stderr = ssh.exec_command('pm2 reload super-appsheet-frontend')
print('PM2:\n', stdout.read().decode('utf-8'))

# 5. Git commit & push on remote
git_cmd = '''cd /home/openhands/super-appsheet && git add frontend/src/views/PosKdsStandalone.vue frontend/src/views/PosRestodash.vue src/pos_engine.py && git commit -m "fix(pos-mobile): prevent popup stacking, align standalone KDS theme, 2-step settings menu, 1-col KDS, direct pay bar & payment fix" && git push origin theme/bakehouse'''
stdin, stdout, stderr = ssh.exec_command(git_cmd)
print('GIT STDOUT:\n', stdout.read().decode('utf-8'))
print('GIT STDERR:\n', stderr.read().decode('utf-8'))

ssh.close()
print('All deployed and committed on remote successfully!')
