import paramiko

js_content = '''// Kidobits Device Orientation & Screen Lock Engine
// Enforces:
// 1. Mobile Phone: Fixed Portrait (390-430px). When tilted horizontally (max-height <= 520px), shows portrait prompt and locks orientation.
// 2. Tablet & Desktop: Landscape mode (>= 768px / >= 1024px, height >= 521px).
(function() {
  'use strict';

  function initOrientationLock() {
    // 1. Programmatic Screen Orientation Lock (Supported on Chrome Android, PWA standalone, Fullscreen)
    try {
      var isPhone = Math.min(window.screen.width, window.screen.height) < 600;
      if (isPhone && window.screen && window.screen.orientation && window.screen.orientation.lock) {
        window.screen.orientation.lock('portrait').catch(function() {
          // Fallback handled by CSS overlay
        });
      }
    } catch (e) {}

    // 2. Inject Prompt CSS if not already injected
    if (!document.getElementById('kidobits-orientation-css')) {
      var style = document.createElement('style');
      style.id = 'kidobits-orientation-css';
      style.textContent = [
        '/* Overlay only appears on phone devices turned to landscape (height <= 520px) */',
        '@media screen and (orientation: landscape) and (max-height: 520px) {',
        '  #kb-rotate-notice { display: flex !important; }',
        '  body { overflow: hidden !important; }',
        '}',
        '@keyframes kbRotatePhone {',
        '  0%, 15% { transform: rotate(0deg); }',
        '  40%, 65% { transform: rotate(-90deg); }',
        '  85%, 100% { transform: rotate(0deg); }',
        '}',
        '.animate-kb-rotate {',
        '  animation: kbRotatePhone 2.4s cubic-bezier(0.4, 0, 0.2, 1) infinite;',
        '}'
      ].join('\\n');
      document.head.appendChild(style);
    }

    // 3. Inject Prompt DOM if not already present
    if (!document.getElementById('kb-rotate-notice')) {
      var overlay = document.createElement('div');
      overlay.id = 'kb-rotate-notice';
      overlay.style.cssText = 'display:none; position:fixed; inset:0; z-index:999999; background:rgba(29, 23, 49, 0.96); backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:20px; color:#FFFFFF; font-family:"Prompt",-apple-system,sans-serif;';
      overlay.innerHTML = [
        '<div style="width:72px; height:72px; border-radius:22px; background:rgba(255,255,255,0.12); border:1.5px solid rgba(255,255,255,0.25); display:flex; align-items:center; justify-content:center; font-size:36px; margin-bottom:14px;" class="animate-kb-rotate">',
        '  📱',
        '</div>',
        '<h3 style="font-size:18px; font-weight:800; margin:0 0 6px 0; letter-spacing:-0.02em;">กรุณาใช้งานในแนวตั้ง</h3>',
        '<p style="font-size:13px; color:rgba(255,255,255,0.8); max-width:300px; margin:0 0 16px 0; font-weight:500; line-height:1.45;">',
        '  แอปถูกออกแบบสำหรับหน้าจอมือถือแนวตั้ง<br>กรุณาหมุนโทรศัพท์ของคุณกลับเป็นแนวตั้งครับ',
        '</p>',
        '<button id="kb-dismiss-rotate" style="background:rgba(255,255,255,0.18); border:1px solid rgba(255,255,255,0.3); color:#fff; font-size:11px; font-weight:700; padding:6px 14px; border-radius:999px; cursor:pointer;">',
        '  ดูต่อในแนวนอน (ข้าม)',
        '</button>'
      ].join('');
      document.body.appendChild(overlay);

      var dismissBtn = document.getElementById('kb-dismiss-rotate');
      if (dismissBtn) {
        dismissBtn.addEventListener('click', function() {
          overlay.style.setProperty('display', 'none', 'important');
        });
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initOrientationLock);
  } else {
    initOrientationLock();
  }
})();
'''

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=10)
sftp = ssh.open_sftp()
with sftp.file('/var/www/kidobits/theme/js/kidobits_device_orientation.js', 'w') as f:
    f.write(js_content.encode('utf-8'))
sftp.close()

# Also copy to /var/www/kidobits/js/
stdin, stdout, stderr = ssh.exec_command('echo "OpenHands@ERP2026" | sudo -S cp /var/www/kidobits/theme/js/kidobits_device_orientation.js /var/www/kidobits/js/kidobits_device_orientation.js && echo "OpenHands@ERP2026" | sudo -S chmod 644 /var/www/kidobits/theme/js/kidobits_device_orientation.js /var/www/kidobits/js/kidobits_device_orientation.js')
print("Chmod stdout:", stdout.read().decode('utf-8'))
print("Chmod stderr:", stderr.read().decode('utf-8'))

ssh.close()
print("Uploaded kidobits_device_orientation.js successfully!")
