import paramiko
import re

print("Connecting to remote server...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026')
sftp = ssh.open_sftp()

print("Reading remote theme_games.html...")
with sftp.open('/var/www/kidobits/theme/theme_games.html', 'r') as f:
    html = f.read().decode('utf-8')

# 1. Add Responsive CSS in head
responsive_style = """  <!-- Kidobits Games Hub Universal Responsive Grid CSS -->
  <style id="kidobits-games-responsive">
    @media (min-width: 640px), (orientation: landscape) and (min-width: 540px) {
      .games-container {
        max-width: 860px !important;
      }
      .games-interactive-grid {
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 16px !important;
      }
      .games-interactive-grid > section {
        margin: 0 !important;
        height: 100% !important;
      }
      .games-adventures-grid {
        grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
      }
      nav[aria-label="Bottom Navigation"] {
        max-width: 480px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        right: auto !important;
        width: calc(100% - 24px) !important;
      }
    }

    @media (min-width: 1024px) {
      .games-container {
        max-width: 1080px !important;
      }
    }
  </style>
</head>"""

if 'kidobits-games-responsive' not in html and '</head>' in html:
    html = html.replace('</head>', responsive_style, 1)

# 2. Update container
old_container = '<div class="w-full max-w-[430px] min-h-screen bg-white relative flex flex-col justify-between shadow-2xl pb-24">'
new_container = '<div class="games-container w-full max-w-[430px] md:max-w-[860px] lg:max-w-[1080px] min-h-screen bg-white relative flex flex-col justify-between shadow-2xl pb-24 transition-all duration-200">'
html = html.replace(old_container, new_container, 1)

# 3. Wrap Section 2 (Memory) and Section 3 (Quiz) in .games-interactive-grid
old_sec2_start = '<!-- ================= 2. GAME 1: MEMORY MATCH (จับคู่ความจำ) ================= -->'
new_sec2_start = """<!-- ================= INTERACTIVE MINI-GAMES GRID ================= -->
      <div class="games-interactive-grid grid grid-cols-1 md:grid-cols-2 gap-4 mt-5">

      <!-- ================= 2. GAME 1: MEMORY MATCH (จับคู่ความจำ) ================= -->"""
html = html.replace(old_sec2_start, new_sec2_start, 1)

html = html.replace(
    '<section class="mt-5 bg-[#FFFDF5] border border-[#FFEAA7] rounded-[24px] p-4 card-shadow">',
    '<section class="bg-[#FFFDF5] border border-[#FFEAA7] rounded-[24px] p-4 card-shadow flex flex-col justify-between">',
    1
)

html = html.replace(
    '<section class="mt-4 bg-[#F2FAF6] border border-[#C6F6D5] rounded-[24px] p-4 card-shadow">',
    '<section class="bg-[#F2FAF6] border border-[#C6F6D5] rounded-[24px] p-4 card-shadow flex flex-col justify-between">',
    1
)

old_sec3_end = """        <p id="quizFeedback" class="text-center text-xs font-extrabold mt-2 h-4 transition-all"></p>
      </section>"""

new_sec3_end = """        <p id="quizFeedback" class="text-center text-xs font-extrabold mt-2 h-4 transition-all"></p>
      </section>

      </div>"""
html = html.replace(old_sec3_end, new_sec3_end, 1)

# 4. Update Section 4 (Adventures) to 4 cols on desktop
html = html.replace(
    '<div class="grid grid-cols-2 gap-2.5">',
    '<div class="games-adventures-grid grid grid-cols-2 md:grid-cols-4 gap-3">',
    1
)

# 5. Update Bottom Navigation to modern centered capsule and Phonics link to theme_phonics_map.html
old_nav = '<nav class="fixed bottom-0 left-0 right-0 max-w-[430px] mx-auto bg-white/95 backdrop-blur-md border-t border-[#EAE4F2] px-3 py-2 flex items-center justify-between z-50 shadow-lg" aria-label="Bottom Navigation">'
new_nav = '<nav class="fixed bottom-3 left-1/2 -translate-x-1/2 w-[calc(100%-24px)] max-w-[460px] bg-white/95 backdrop-blur-md shadow-[0_10px_30px_rgba(60,30,90,.18)] rounded-full px-2 py-2 flex justify-between border border-[#F3EDF8] z-50" aria-label="Bottom Navigation">'
html = html.replace(old_nav, new_nav, 1)

html = html.replace(
    "<button onclick=\"window.location.href='theme_phonicsLevel.html'\"",
    "<button onclick=\"window.location.href='theme_phonics_map.html'\""
)

# 6. Save and apply on remote
with sftp.open('/tmp/theme_games.html', 'w') as f:
    f.write(html)
sftp.close()

cmd = """
sudo cp /tmp/theme_games.html /var/www/kidobits/theme/theme_games.html
sudo chown www-data:www-data /var/www/kidobits/theme/theme_games.html
cd /var/www/kidobits
git add theme/theme_games.html
git commit -m "feat(responsive): convert theme_games to modern responsive CSS Grid layout"
git push origin main
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
ssh.close()
print("Done!")
