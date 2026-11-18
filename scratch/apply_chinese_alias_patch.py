import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='ignore'), stderr.read().decode('utf-8', errors='ignore')

script = r'''
for path in ['/var/www/kidobits/chinese.html', '/var/www/kidobits/chinese_preview.html']:
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()

    old_target = """    function openLesson(lessonId, forcedStep = null) {
      let found = null;
      for (const k in CHINESE_DATA) {
        const item = CHINESE_DATA[k].find(x => x.id === lessonId);
        if (item) { found = item; break; }
      }
      if (!found) return;"""

    new_target = """    function openLesson(lessonId, forcedStep = null) {
      if (!lessonId || lessonId === 'CH01' || lessonId === 'CH1' || lessonId === 'ch01') lessonId = 'K1.01';
      let found = null;
      for (const k in CHINESE_DATA) {
        const item = CHINESE_DATA[k].find(x => x.id === lessonId);
        if (item) { found = item; break; }
      }
      if (!found && CHINESE_DATA['early'] && CHINESE_DATA['early'].length > 0) {
        found = CHINESE_DATA['early'][0];
      }
      if (!found) return;"""

    if old_target in c:
        c = c.replace(old_target, new_target)
        print(f'Updated openLesson in {path}')
    else:
        print(f'old_target not found in {path}')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)

print('Alias patch finished!')
'''

sftp = ssh.open_sftp()
with sftp.open('/tmp/alias_patch.py', 'w') as f:
    f.write(script)
sftp.close()

out, err = run("sudo python3 /tmp/alias_patch.py")
print("=== ALIAS PATCH OUTPUT ===")
print(out, err)

ssh.close()
