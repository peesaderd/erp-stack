import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

remote_script = r'''
with open("/var/www/kidobits/theme/theme_azPlayer.html", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# Replace the onClick of mic button to call window.triggerAZMic() directly
target = 'onClick:()=>{if(window.triggerAZMic){window.triggerAZMic();}else{Qt(0);iP(Qt,()=>{ne("เก่งมาก! ฟังและพูดตามได้แล้ว \\uD83C\\uDF89");Bn(5,5)});}}'
replacement = 'onClick:()=>{console.log("[Mic] Clicked");if(window.triggerAZMic){window.triggerAZMic();}else{console.error("[Mic] triggerAZMic missing");}}'

if target in text:
    text = text.replace(target, replacement, 1)
    print("SUCCESS: Mic button updated with direct call")
else:
    print("ERROR: Target not found")

with open("/tmp/theme_azPlayer_clean_click.html", "w", encoding="utf-8") as f:
    f.write(text)
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/fix_clean_click.py', 'w') as f:
    f.write(remote_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/fix_clean_click.py')
print(stdout.read().decode())
print("ERR:", stderr.read().decode())

cmd = 'echo "OpenHands@ERP2026" | sudo -S cp /tmp/theme_azPlayer_clean_click.html /var/www/kidobits/theme/theme_azPlayer.html && echo "DEPLOY_HTML_OK"'
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

ssh.close()
