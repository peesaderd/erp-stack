import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

stdin, stdout, stderr = ssh.exec_command("curl -s -I https://kidobits.m2igen.com/kidobits/theme/theme_phonicsLesson.html?lesson=L1.01")
print("Curl HTTP header:", stdout.read().decode())

cmd = """python3 -c "
with open('/var/www/kidobits/theme/theme_phonicsLesson.html', encoding='utf-8') as f:
    text = f.read()

assert 'jumpToStep' in text, 'jumpToStep missing'
assert 'force: !!force' in text, 'force missing'
assert 'const SPEECH_RMS = 0.030;' in text, 'SPEECH_RMS missing'
print('All HTML checks verified!')
" """
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())

ssh.close()
