import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

# 1. Upload PosRestodash.vue
sftp = ssh.open_sftp()
local_vue = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\PosRestodash.vue'
remote_vue = '/home/openhands/super-appsheet/frontend/src/views/PosRestodash.vue'
sftp.put(local_vue, remote_vue)
sftp.close()
print("Uploaded PosRestodash.vue successfully.")

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='ignore') + stderr.read().decode('utf-8', errors='ignore')

# 2. Check main.js and add route /pos/restodash/settings redirect if not present
main_js = run("cat /home/openhands/super-appsheet/frontend/src/main.js")
if '/pos/restodash/settings' not in main_js:
    target_str = "    path: '/pos/restodash',\n    name: 'PosRestodash',\n    component: () => import('./views/PosRestodash.vue')\n  },"
    replace_str = target_str + "\n  {\n    path: '/pos/restodash/settings',\n    redirect: '/pos/restodash?tab=settings'\n  },"
    if target_str in main_js:
        updated_main = main_js.replace(target_str, replace_str)
        sftp = ssh.open_sftp()
        with sftp.file('/home/openhands/super-appsheet/frontend/src/main.js', 'w') as f:
            f.write(updated_main)
        sftp.close()
        print("Added /pos/restodash/settings route to main.js")

# 3. Build frontend
print("Running npm run build...")
build_res = run("cd /home/openhands/super-appsheet/frontend && npm run build")
print(build_res[-600:] if len(build_res) > 600 else build_res)

# 4. Restart PM2 frontend
print("Restarting PM2...")
pm2_res = run("pm2 restart super-appsheet-frontend")
print(pm2_res)
