import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8'), stderr.read().decode('utf-8')

with open('scratch/theme_login.html', 'r', encoding='utf-8') as f:
    login_html = f.read()

sftp = ssh.open_sftp()
with sftp.file('/tmp/theme_login.html', 'w') as f:
    f.write(login_html)
sftp.close()

out, err = run('sudo cp /tmp/theme_login.html /var/www/kidobits/theme/theme_login.html && sudo cp /tmp/theme_login.html /var/www/kidobits/login.html && sudo chown www-data:www-data /var/www/kidobits/theme/theme_login.html /var/www/kidobits/login.html')
print('Copy result:', out, err)

ssh.close()
