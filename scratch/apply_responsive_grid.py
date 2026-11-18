import paramiko
import os

print("Connecting to remote server...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')
sftp = ssh.open_sftp()

# -----------------------------------------------------------------------------
# 1. Update theme_phonicsHome.html
# -----------------------------------------------------------------------------
print("Reading remote theme_phonicsHome.html...")
with sftp.open('/var/www/kidobits/theme/theme_phonicsHome.html', 'r') as f:
    home_html = f.read().decode('utf-8')

responsive_home_style = """  <!-- Kidobits Phonics Home Universal Responsive Grid CSS -->
  <style id="kidobits-phonics-home-responsive">
    @media (min-width: 640px), (orientation: landscape) and (min-width: 540px) {
      .phonics-home-container {
        max-width: 860px !important;
      }
      .phonics-level-grid {
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 14px !important;
      }
      .phonics-level-grid > * {
        margin: 0 !important;
        height: 100% !important;
      }
      nav.phonics-bottom-nav {
        max-width: 500px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        right: auto !important;
        width: calc(100% - 24px) !important;
      }
    }

    @media (min-width: 1024px) {
      .phonics-home-container {
        max-width: 1080px !important;
      }
      .phonics-level-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
        gap: 16px !important;
      }
    }
  </style>
</head>"""

if 'kidobits-phonics-home-responsive' not in home_html and '</head>' in home_html:
    home_html = home_html.replace('</head>', responsive_home_style, 1)

home_html = home_html.replace(
    'class="w-full max-w-[430px] sm:rounded-[36px]',
    'class="phonics-home-container w-full max-w-[430px] sm:rounded-[36px]'
)

home_html = home_html.replace(
    '<div class="space-y-3 mt-2">',
    '<div class="phonics-level-grid space-y-3 sm:space-y-0 mt-2">'
)

home_html = home_html.replace(
    '<nav class="absolute bottom-3 left-3 right-3',
    '<nav class="phonics-bottom-nav absolute bottom-3 left-3 right-3'
)

with sftp.open('/tmp/theme_phonicsHome.html', 'w') as f:
    f.write(home_html)

# -----------------------------------------------------------------------------
# 2. Update theme_phonicsLevel.html
# -----------------------------------------------------------------------------
print("Reading remote theme_phonicsLevel.html...")
with sftp.open('/var/www/kidobits/theme/theme_phonicsLevel.html', 'r') as f:
    level_html = f.read().decode('utf-8')

# Ensure the media queries trigger on min-width (not only landscape)
old_mq1 = "@media (orientation: landscape) and (min-width: 600px)"
new_mq1 = "@media (min-width: 640px), (orientation: landscape) and (min-width: 540px)"

old_mq2 = "@media (orientation: landscape) and (min-width: 900px)"
new_mq2 = "@media (min-width: 1024px)"

if old_mq1 in level_html:
    level_html = level_html.replace(old_mq1, new_mq1)
if old_mq2 in level_html:
    level_html = level_html.replace(old_mq2, new_mq2)

with sftp.open('/tmp/theme_phonicsLevel.html', 'w') as f:
    f.write(level_html)

sftp.close()

# -----------------------------------------------------------------------------
# 3. Apply changes and commit on remote
# -----------------------------------------------------------------------------
print("Copying files to /var/www/kidobits/theme/ ...")
apply_cmd = (
    "sudo cp /tmp/theme_phonicsHome.html /var/www/kidobits/theme/theme_phonicsHome.html && "
    "sudo cp /tmp/theme_phonicsLevel.html /var/www/kidobits/theme/theme_phonicsLevel.html && "
    "sudo chown -R www-data:www-data /var/www/kidobits/theme/ && "
    "cd /var/www/kidobits && "
    "git add theme/theme_phonicsHome.html theme/theme_phonicsLevel.html && "
    "git commit -m 'feat(responsive): convert phonicsHome and phonicsLevel to responsive CSS Grid' && "
    "git push origin main"
)

stdin, stdout, stderr = ssh.exec_command(apply_cmd)
out = stdout.read().decode()
err = stderr.read().decode()

print("STDOUT:\n", out)
print("STDERR:\n", err)

ssh.close()
print("Done!")
