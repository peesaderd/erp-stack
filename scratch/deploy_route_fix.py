import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = r'''
with open("/var/www/kidobits/theme/theme_azPlayer.html", "r", encoding="utf-8") as f:
    text = f.read()

target = 'function h(v){n(v),E(""),window.scrollTo({top:0})}'
replacement = 'function h(v){if(v==="home"){window.location.href="theme_home.html";return;}if(v==="phonicsHome"){window.location.href="theme_phonicsHome.html";return;}if(v==="mathHome"){window.location.href="theme_mathHome.html";return;}if(v==="chineseHome"){window.location.href="theme_chineseHome.html";return;}n(v);E("");window.scrollTo({top:0});}'

if target in text:
    text = text.replace(target, replacement, 1)
    print("SUCCESS: routed h() to real HTML pages")
    with open("/tmp/theme_azPlayer_routed.html", "w", encoding="utf-8") as f:
        f.write(text)
else:
    print("ERROR: target not found")
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/route_h_func.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/route_h_func.py')
print(stdout.read().decode())
print("ERR:", stderr.read().decode())

cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_azPlayer_routed.html /var/www/kidobits/theme/theme_azPlayer.html && echo "DEPLOY_ROUTED_OK"'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

ssh.close()
