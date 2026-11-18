import paramiko

ssot_js = r"""/**
 * Kidobits Student Profile SSOT (Single Source of Truth)
 * Centralizes student identity, name, age, and grade across all themes and modules.
 * Default / Fallback Student Name: 'Putter'
 */
(function() {
  'use strict';

  var KEY = 'kidobits_student_profile';
  var FALLBACK = 'Putter';

  var KidobitsStudent = {
    KEY: KEY,
    FALLBACK_NAME: FALLBACK,

    // 1. Get raw or structured profile from single source of truth
    getProfile: function() {
      var student = null;
      try {
        var raw = localStorage.getItem(KEY);
        if (raw) student = JSON.parse(raw);
      } catch (e) {}

      // If missing or holds legacy hardcoded dummy names, upgrade to Putter
      if (!student || !student.name || student.name === 'น้องเอ็มม่า' || student.name === 'Marion') {
        student = student || {};
        // Check if auth cache has a custom student name
        var foundAuthName = null;
        try {
          var rawAuth = localStorage.getItem('kidobits_auth_user');
          if (rawAuth) {
            var authUser = JSON.parse(rawAuth);
            if (authUser && authUser.student_name && authUser.student_name !== 'น้องเอ็มม่า' && authUser.student_name !== 'Marion') {
              foundAuthName = authUser.student_name;
            }
          }
        } catch (e) {}

        student.name = foundAuthName || FALLBACK;
        if (!student.age) student.age = '6';
        if (!student.grade) student.grade = 'K3 / อนุบาล 3';
        if (!student.level) student.level = 1;

        // Save migrated profile
        try {
          localStorage.setItem(KEY, JSON.stringify(student));
        } catch(e) {}
      }

      return student;
    },

    // 2. Get Student Name (Guaranteed SSOT, never parent's LINE name)
    getName: function() {
      var p = this.getProfile();
      if (p && p.name && p.name.trim() && p.name !== 'น้องเอ็มม่า' && p.name !== 'Marion') {
        return p.name.trim();
      }
      return FALLBACK;
    },

    // 3. Save Student Profile (Single Source of Truth write)
    saveProfile: function(updates) {
      var current = this.getProfile();
      var updated = Object.assign({}, current, updates);
      if (!updated.name || !updated.name.trim()) {
        updated.name = FALLBACK;
      }
      localStorage.setItem(KEY, JSON.stringify(updated));

      // Sync auth user cache if present
      try {
        var rawAuth = localStorage.getItem('kidobits_auth_user');
        if (rawAuth) {
          var authUser = JSON.parse(rawAuth);
          authUser.student_name = updated.name;
          localStorage.setItem('kidobits_auth_user', JSON.stringify(authUser));
        }
      } catch (e) {}

      // Dispatch custom event to sync all open tabs/views
      window.dispatchEvent(new CustomEvent('kidobits_student_changed', { detail: updated }));

      // Run syncDOM immediately
      this.syncDOM();

      // Sync to central ERP backend if logged in
      try {
        var token = localStorage.getItem('kidobits_jwt_token');
        if (token && window.fetch) {
          fetch('/api/v1/auth/profile', {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({
              student_name: updated.name,
              student_age: updated.age || '6'
            })
          }).catch(function() {});
        }
      } catch (e) {}

      return updated;
    },

    // 4. Synchronize all UI elements across the page
    syncDOM: function() {
      var name = this.getName();

      // 4.1 Home Greeting
      var homeGreeting = document.getElementById('homeGreetingName');
      if (homeGreeting) {
        homeGreeting.textContent = 'Hello, ' + name + ' 👋';
      }

      // 4.2 Elements with data-kb-student-name
      var namedEls = document.querySelectorAll('[data-kb-student-name]');
      for (var i = 0; i < namedEls.length; i++) {
        namedEls[i].textContent = name;
      }

      // 4.3 Profile headings or greetings
      var headings = document.querySelectorAll('h2, h3');
      for (var j = 0; j < headings.length; j++) {
        var txt = headings[j].innerText || headings[j].textContent || '';
        if (txt.indexOf('Hello,') === 0 && txt.indexOf('👋') !== -1) {
          headings[j].textContent = 'Hello, ' + name + ' 👋';
        }
        if (txt === 'Marion' || txt === 'น้องเอ็มม่า') {
          headings[j].textContent = name;
        }
      }

      // 4.4 Name inputs (e.g. in modals or profile editor)
      var nameInput = document.getElementById('input-student-name');
      if (nameInput && (!nameInput.value || nameInput.value === 'น้องเอ็มม่า' || nameInput.value === 'Marion')) {
        nameInput.value = name;
      }

      // Template settings student name input
      var templateNameInputs = document.querySelectorAll('input[placeholder="Marion"], input[placeholder="เช่น น้องเอ็มม่า, น้องมาร์ค"]');
      for (var k = 0; k < templateNameInputs.length; k++) {
        if (!templateNameInputs[k].value || templateNameInputs[k].value === 'Marion' || templateNameInputs[k].value === 'น้องเอ็มม่า') {
          templateNameInputs[k].value = name;
        }
      }
    }
  };

  window.KidobitsStudent = KidobitsStudent;

  // Intercept any student name inputs across the app and save to SSOT automatically
  document.addEventListener('input', function(e) {
    if (e.target && e.target.tagName === 'INPUT') {
      var placeholder = e.target.placeholder || '';
      var id = e.target.id || '';
      if (placeholder === 'Marion' || placeholder === 'เช่น น้องเอ็มม่า, น้องมาร์ค' || id === 'input-student-name') {
        var val = e.target.value.trim();
        if (val && val !== 'Marion' && val !== 'น้องเอ็มม่า') {
          KidobitsStudent.saveProfile({ name: val });
        }
      }
    }
  }, true);

  // Auto-run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      KidobitsStudent.syncDOM();
    });
  } else {
    KidobitsStudent.syncDOM();
  }

  // Periodic DOM sync to catch any late client renders (e.g. React mount)
  var syncCount = 0;
  var syncInterval = setInterval(function() {
    KidobitsStudent.syncDOM();
    syncCount++;
    if (syncCount > 10) clearInterval(syncInterval);
  }, 300);

  // Listen to cross-tab storage changes
  window.addEventListener('storage', function(e) {
    if (e.key === KEY) {
      KidobitsStudent.syncDOM();
    }
  });

  // Listen to in-tab changes
  window.addEventListener('kidobits_student_changed', function() {
    KidobitsStudent.syncDOM();
  });
})();
"""

def deploy_ssot():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect('89.167.82.205', username='openhands', password='OpenHands@ERP2026', timeout=15)
    sftp = ssh.open_sftp()
    with sftp.file('/tmp/kidobits_student_ssot.js', 'w') as f:
        f.write(ssot_js.encode('utf-8'))
    sftp.close()
    
    cmd = (
        'echo "OpenHands@ERP2026" | sudo -S cp /tmp/kidobits_student_ssot.js /var/www/kidobits/theme/js/kidobits_student_ssot.js && '
        'echo "OpenHands@ERP2026" | sudo -S cp /tmp/kidobits_student_ssot.js /var/www/kidobits/js/kidobits_student_ssot.js && '
        'echo "OpenHands@ERP2026" | sudo -S chmod 664 /var/www/kidobits/theme/js/kidobits_student_ssot.js /var/www/kidobits/js/kidobits_student_ssot.js'
    )
    stdin, stdout, stderr = ssh.exec_command(cmd)
    stdout.read(); stderr.read()
    print("kidobits_student_ssot.js deployed with auto-migration to Putter!")
    ssh.close()

if __name__ == '__main__':
    deploy_ssot()
