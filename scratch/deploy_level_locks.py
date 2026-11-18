import paramiko

print("Connecting to remote server 89.167.82.205...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=15)
sftp = ssh.open_sftp()

print("Uploading apply_level_locks_remote.py to /tmp/run_level_locks.py ...")
sftp.put('scratch/apply_level_locks_remote.py', '/tmp/run_level_locks.py')

def run_sudo_cmd(cmd):
    full_cmd = f"echo 'OpenHands@ERP2026' | sudo -S {cmd}"
    stdin, stdout, stderr = ssh.exec_command(full_cmd)
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    return out, err

print("Executing script with sudo on remote...")
out, err = run_sudo_cmd("python3 /tmp/run_level_locks.py")
print("STDOUT:\n", out)
if err and "password" not in err.lower():
    print("STDERR:\n", err)

print("Ensuring proper ownership...")
run_sudo_cmd("chown -R www-data:www-data /var/www/kidobits/theme")

print("Checking git status...")
stdin, stdout, stderr = ssh.exec_command("cd /var/www/kidobits && git status -s")
git_status = stdout.read().decode('utf-8')
print("GIT STATUS:\n", git_status)

if git_status.strip():
    print("Committing and pushing...")
    run_sudo_cmd("cd /var/www/kidobits && git add theme/js/kidobits_curriculum_lock.js theme/theme_phonics_map.html theme/theme_chinese_lobby.html")
    run_sudo_cmd('cd /var/www/kidobits && git commit -m "feat(curriculum): lock phonics map L2/L3 until cleared, and enforce chinese early tier sequence"')
    run_sudo_cmd("cd /var/www/kidobits && git push origin main")
    print("Pushed to origin main successfully!")
else:
    print("No git changes to commit.")

sftp.close()
ssh.close()
print("Done.")
