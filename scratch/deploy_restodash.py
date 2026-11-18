import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

sftp = ssh.open_sftp()
sftp.put(
    r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\PosRestodash.vue',
    '/home/openhands/super-appsheet/frontend/src/views/PosRestodash.vue'
)
sftp.close()
print("Uploaded PosRestodash.vue to remote server.")

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8') + stderr.read().decode('utf-8')

print("=== Run npm run build ===")
build_out = run("cd /home/openhands/super-appsheet/frontend && npm run build")
print(build_out[-1000:] if len(build_out) > 1000 else build_out)

print("=== Restart super-appsheet-frontend PM2 ===")
print(run("pm2 restart super-appsheet-frontend"))
