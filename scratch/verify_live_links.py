import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

def run_cmd(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='replace')

print('=== theme_home.html phonics links ===')
print(run_cmd("grep -n -C 1 'theme_phonics' /var/www/kidobits/theme/theme_home.html"))

print('=== theme_phonics_map.html Level 1 button ===')
print(run_cmd("sed -n '150,156p' /var/www/kidobits/theme/theme_phonics_map.html"))

ssh.close()
