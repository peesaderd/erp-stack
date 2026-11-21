import paramiko

HOSTNAME = '89.167.82.205'
USERNAME = 'openhands'
PASSWORD = 'OpenHands@ERP2026'

LOCAL_INDEX = r'C:\Users\ADMIN\Documents\antigravity\calm-noether\scratch\smartback_pwa\index.html'
REMOTE_TARGET = '/var/www/m2igen-redesign/smartback/index.html'

print("Connecting to remote server...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD)

sftp = ssh.open_sftp()
sftp.put(LOCAL_INDEX, "/tmp/sb_pwa/index.html")
sftp.close()

cmd = f"""
echo '{PASSWORD}' | sudo -S cp /tmp/sb_pwa/index.html {REMOTE_TARGET}
echo '{PASSWORD}' | sudo -S chown www-data:www-data {REMOTE_TARGET}
echo '{PASSWORD}' | sudo -S chmod 755 {REMOTE_TARGET}
ls -la {REMOTE_TARGET}
"""
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

ssh.close()
print("Deployed updated Ecommerce UI to live site successfully!")
