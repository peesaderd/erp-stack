import paramiko
import re

print("Connecting to remote server...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=10)
sftp = ssh.open_sftp()

print("Reading /var/www/kidobits/theme/theme_profile.html ...")
with sftp.open('/var/www/kidobits/theme/theme_profile.html', 'r') as f:
    html = f.read().decode('utf-8')

# -----------------------------------------------------------------------------
# 1. Update Responsive CSS: Remove broken grid on .px-5.pt-5, add .kb-profile-grid
# -----------------------------------------------------------------------------
old_css_part = """      /* 2-Column Responsive Grid inside Profile Content */
      #root .px-5.pt-5 {
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 16px !important;
        align-items: start !important;
      }

      /* Title spans full width */
      #root .px-5.pt-5 > h2:first-child {
        grid-column: 1 / -1 !important;
        margin-bottom: 0 !important;
      }"""

new_css_part = """      /* Balanced 2-Column Grid on Tablet & Desktop */
      .kb-profile-grid {
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 24px !important;
        align-items: start !important;
      }

      .kb-profile-col {
        display: flex !important;
        flex-direction: column !important;
        gap: 16px !important;
      }

      #root > div > div {
        max-width: 900px !important;
        padding-bottom: 110px !important;
      }"""

if old_css_part in html:
    html = html.replace(old_css_part, new_css_part, 1)
    print("Replaced broken .px-5.pt-5 grid CSS with .kb-profile-grid CSS")
else:
    print("Notice: old_css_part not found directly, checking regex")
    html = re.sub(
        r'/\*\s*2-Column Responsive Grid inside Profile Content\s*\*/[\s\S]*?#root\s+\.px-5\.pt-5\s*>[^}]*\}',
        new_css_part,
        html,
        count=1
    )

# -----------------------------------------------------------------------------
# 2. Update React JSX in theme_profile.html to wrap into 2 balanced columns
# -----------------------------------------------------------------------------
pos_h2 = html.find('My Profile')
start_jsx = html.rfind('className:"px-5 pt-5"', 0, pos_h2)
end_jsx = html.find('Made for happy learners', pos_h2)
end_jsx = html.find(')]})', end_jsx) + 4

orig_jsx = html[start_jsx:end_jsx]
print("Found orig_jsx bounds:", start_jsx, end_jsx, len(orig_jsx))

student_start = orig_jsx.find('o("div",{className:"bg-gradient-to-br from-[#FFF0F5]')
badges_h4_start = orig_jsx.rfind('l("h4"', 0, orig_jsx.find('children:"Badges"'))
badges_row_start = orig_jsx.find('o("div",{className:"flex gap-2 mt-2"', badges_h4_start)
settings_h4_start = orig_jsx.rfind('l("h4"', 0, orig_jsx.find('children:"Settings • ตั้งค่า"'))
settings_row_start = orig_jsx.find('o("div",{className:"space-y-2 mt-2"', settings_h4_start)
progress_start = orig_jsx.find('o("div",{className:"bg-[#FFF0F5] rounded-2xl p-3 mt-3')
logout_start = orig_jsx.find('l("button",{onClick:()=>{n("onboarding")')
footer_start = orig_jsx.find('l("p",{className:"text-center text-xs text-[#9A8FA8]')

header_alert = orig_jsx[0:student_start]
student_card = orig_jsx[student_start:badges_h4_start].rstrip(', ')
badges_h4 = orig_jsx[badges_h4_start:badges_row_start].rstrip(', ')
badges_row = orig_jsx[badges_row_start:settings_h4_start].rstrip(', ')
settings_h4 = orig_jsx[settings_h4_start:settings_row_start].rstrip(', ')
settings_container = orig_jsx[settings_row_start:progress_start].rstrip(', ')
progress_card = orig_jsx[progress_start:logout_start].rstrip(', ')
logout_btn = orig_jsx[logout_start:footer_start].rstrip(', ')
footer_p = orig_jsx[footer_start:-3] # drops ')]}'

# Ensure avatar circle has an id and fallback emoji
old_circle = 'l("div",{className:"w-24 h-24 rounded-full bg-white mx-auto border-4 border-white shadow grid place-items-center text-5xl mt-2",children:Rt})'
new_circle = 'l("div",{id:"profile-avatar-circle",className:"w-24 h-24 rounded-full bg-white mx-auto border-4 border-white shadow overflow-hidden grid place-items-center text-5xl mt-2",children:Rt||"👦"})'
student_card = student_card.replace(old_circle, new_circle)

new_jsx = header_alert + f'''o("div",{{className:"kb-profile-grid flex flex-col md:grid md:grid-cols-2 gap-5 items-start mt-3",children:[
  o("div",{{className:"kb-profile-col w-full flex flex-col gap-4",children:[
    {student_card},
    {progress_card},
    o("div",{{className:"w-full",children:[
      {badges_h4},
      {badges_row}
    ]}})
  ]}}),
  o("div",{{id:"kb-profile-right-col",className:"kb-profile-col w-full flex flex-col gap-4",children:[
    {settings_h4},
    {settings_container},
    {logout_btn},
    {footer_p}
  ]}})
]}})]}})'''

html = html[:start_jsx] + new_jsx + html[end_jsx:]
print("Successfully injected 2-column balanced JSX layout into theme_profile.html")

# -----------------------------------------------------------------------------
# 3. Update syncThemeAuth to handle Parent and Student Avatar Photos
# -----------------------------------------------------------------------------
old_sync_start = "function syncThemeAuth() {"
new_sync_code = """function syncThemeAuth() {
    if (!window.KidobitsAuth) return;
    const profile = (KidobitsAuth.getUser ? KidobitsAuth.getUser() : (KidobitsAuth.getProfile ? KidobitsAuth.getProfile() : null));

    // 1. Update Student Profile Avatar & Name
    let student = null;
    try {
      const rawS = localStorage.getItem('kidobits_student_profile');
      if (rawS) student = JSON.parse(rawS);
    } catch(e) {}

    let displayName = '';
    if (student && student.displayPreference === 'parent' && profile && profile.name) {
      displayName = profile.name;
    } else if (student && student.name && student.name.trim()) {
      displayName = student.name.trim();
    } else if (profile && profile.name) {
      displayName = profile.name;
    } else {
      displayName = 'น้องเอ็มม่า';
    }

    const headings = document.querySelectorAll('h2');
    headings.forEach(h => {
      const text = h.innerText || h.textContent || '';
      if (text.includes('Hello,') || text.includes('Marion')) {
        h.textContent = `Hello, ${displayName} 👋`;
      }
    });

    // 2. Real Student Avatar in Profile Header Card (#profile-avatar-circle)
    const circle = document.getElementById('profile-avatar-circle') || document.querySelector('.w-24.h-24.rounded-full');
    if (circle) {
      let studentAvatar = "https://sprofile.line-scdn.net/0h-f75F-i3ckkaTGHqoZMMNmoccSM5PStbNn47fHhJeXAldD0XMnhqKS4YKy4uemYdZSM7KicfeHwWXwUvBBqOfR18L3gmdDIXPyI9qg";
      try {
        const rawConf = localStorage.getItem('kidobits_avatar_config');
        if (rawConf) {
          const conf = JSON.parse(rawConf);
          if (conf.url && conf.mode !== 'cartoon') studentAvatar = conf.url;
          else if (conf.avatar_url) studentAvatar = conf.avatar_url;
        }
      } catch(e) {}
      if (profile) {
        if (profile.student_avatar_url) studentAvatar = profile.student_avatar_url;
        else if (profile.avatar_url && !profile.avatar_url.includes('default-avatar')) studentAvatar = profile.avatar_url;
      }
      if (studentAvatar) {
        const curImg = circle.querySelector('img');
        if (!curImg || curImg.getAttribute('src') !== studentAvatar) {
          circle.innerHTML = `<img src="${studentAvatar}" alt="Student Avatar" class="w-full h-full object-cover rounded-full" onerror="this.onerror=null;this.parentElement.innerHTML='👦';">`;
        }
      }
    }

    // 3. Update Top Bar Avatar Button
    const avatarBtn = document.querySelector('button[aria-label="Edit avatar"]');
    if (avatarBtn) {
      const btnPic = (profile && (profile.picture || profile.social_avatar_url || profile.avatar_url)) || "https://sprofile.line-scdn.net/0h-f75F-i3ckkaTGHqoZMMNmoccSM5PStbNn47fHhJeXAldD0XMnhqKS4YKy4uemYdZSM7KicfeHwWXwUvBBqOfR18L3gmdDIXPyI9qg";
      if (btnPic && !avatarBtn.querySelector('img')) {
        avatarBtn.innerHTML = `<img src="${btnPic}" alt="Avatar" class="w-full h-full rounded-full object-cover">`;
      }
      if (!avatarBtn.dataset.authAttached) {
        avatarBtn.dataset.authAttached = '1';
        avatarBtn.addEventListener('click', function(e) {
          if (!(KidobitsAuth.getUser ? KidobitsAuth.getUser() : (KidobitsAuth.getProfile ? KidobitsAuth.getProfile() : null))) {
            e.preventDefault();
            e.stopPropagation();
            window.location.href = '/theme/theme_login.html';
          }
        }, true);
      }
    }

    // 4. Inject Member Card into Right Column of Profile
    let authCard = document.getElementById('theme-member-auth-card');
    if (!authCard) {
      authCard = document.createElement('div');
      authCard.id = 'theme-member-auth-card';
      authCard.className = 'w-full mb-1';
    }

    const rightCol = document.getElementById('kb-profile-right-col');
    if (rightCol) {
      if (authCard.parentNode !== rightCol || authCard !== rightCol.firstChild) {
        rightCol.insertBefore(authCard, rightCol.firstChild);
      }
    } else {
      const profileContainer = document.querySelector('#root .px-5.pt-5');
      if (profileContainer && !document.getElementById('theme-member-auth-card')) {
        profileContainer.appendChild(authCard);
      }
    }

    const parentPic = (profile && (profile.picture || profile.social_avatar_url || profile.avatar_url)) || (profile && profile.line_user_id ? "https://sprofile.line-scdn.net/0h-f75F-i3ckkaTGHqoZMMNmoccSM5PStbNn47fHhJeXAldD0XMnhqKS4YKy4uemYdZSM7KicfeHwWXwUvBBqOfR18L3gmdDIXPyI9qg" : "");

    if (profile) {
      authCard.innerHTML = `
        <div style="background: linear-gradient(135deg, #F0FDF4 0%, #E8FFF0 100%); border: 2px solid #86EFAC; border-radius: 20px; padding: 14px; box-shadow: 0 4px 15px rgba(22,163,74,.08);">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
            <div style="display: flex; align-items: center; gap: 10px;">
              <div style="width: 44px; height: 44px; border-radius: 50%; overflow: hidden; border: 2px solid #22C55E; background: white; display: grid; place-items: center; font-size: 22px; shrink: 0;">
                ${parentPic ? `<img src="${parentPic}" alt="Parent" style="width: 100%; height: 100%; object-fit: cover;">` : '🦁'}
              </div>
              <div>
                <div style="display: flex; align-items: center; gap: 6px;">
                  <b style="font-size: 13px; color: #14532D;">${profile.name || profile.sub || 'ผู้ปกครอง'}</b>
                  <span style="font-size: 9px; font-weight: 800; background: #16A34A; color: white; padding: 1px 6px; border-radius: 999px;">${(profile.provider || 'CENTRAL').toUpperCase()}</span>
                </div>
                <span style="font-size: 11px; color: #166534; display: block; overflow: hidden; text-overflow: ellipsis; max-width: 220px; white-space: nowrap;">${profile.email || 'เชื่อมต่อ Central Auth สำเร็จ'}</span>
              </div>
            </div>
            <button onclick="KidobitsAuth.logout()" style="padding: 6px 12px; border-radius: 10px; background: white; border: 1px solid #FCA5A5; color: #DC2626; font-size: 11px; font-weight: 800; cursor: pointer; white-space: nowrap; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
              ออกจากระบบ
            </button>
          </div>
        </div>
      `;
    } else {
      authCard.innerHTML = `
        <div style="background: linear-gradient(135deg, #FFF0F5 0%, #F5F0FF 100%); border: 2px solid #E9DCFA; border-radius: 20px; padding: 14px; text-align: center; box-shadow: 0 4px 15px rgba(139,124,255,.08);">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
            <div style="text-align: left;">
              <b style="font-size: 13px; color: #372A54;">บัญชีผู้ปกครอง (Parent Zone)</b>
              <span style="font-size: 11px; color: #7B7488; display: block;">เข้าสู่ระบบเพื่อเชื่อมต่อ LINE และบันทึกผลการเรียน</span>
            </div>
            <a href="theme_login.html" style="padding: 7px 14px; border-radius: 10px; background: #06C755; color: white; font-size: 12px; font-weight: 800; text-decoration: none; display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; box-shadow: 0 2px 6px rgba(6,199,85,.3);">
              <span>เข้าสู่ระบบ LINE</span>
            </a>
          </div>
        </div>
      `;
    }
}"""

# Replace entire syncThemeAuth function
sync_start = html.find("function syncThemeAuth() {")
sync_end = html.find("window.addEventListener('kidobits_auth_changed'", sync_start)
sync_end = html.rfind('}', 0, sync_end) + 1

print("syncThemeAuth bounds:", sync_start, sync_end)
html = html[:sync_start] + new_sync_code + html[sync_end:]
print("Updated syncThemeAuth!")

# Write to remote /tmp
with sftp.open('/tmp/fixed_theme_profile.html', 'w') as f:
    f.write(html)

sftp.close()
ssh.close()
print("Drafted and uploaded to /tmp/fixed_theme_profile.html successfully!")
