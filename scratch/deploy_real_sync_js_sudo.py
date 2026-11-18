import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='ignore'), stderr.read().decode('utf-8', errors='ignore')

# Upload to /tmp
sftp = ssh.open_sftp()
sftp.put('kidobits_real_sync.js', '/tmp/kidobits_real_sync.js')
sftp.close()

# sudo cp to targets
out, err = run("sudo cp /tmp/kidobits_real_sync.js /var/www/kidobits/theme/js/kidobits_real_sync.js && sudo cp /tmp/kidobits_real_sync.js /var/www/kidobits/js/kidobits_real_sync.js && sudo chmod 644 /var/www/kidobits/theme/js/kidobits_real_sync.js /var/www/kidobits/js/kidobits_real_sync.js")
print("=== CP RESULT ===")
print(out, err)

# Verify file exists
out2, _ = run("ls -la /var/www/kidobits/theme/js/kidobits_real_sync.js")
print("=== VERIFY FILE ===")
print(out2)

ssh.close()
