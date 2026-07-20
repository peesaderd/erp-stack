/* ═══════════════════════════════════════════════════════════════════════════
   ERP Modular — Micro-frontend Shell (Main Controller)
   ═══════════════════════════════════════════════════════════════════════════
   จัดการ Routing, iframe, sidebar, topbar
   ═══════════════════════════════════════════════════════════════════════════ */

const ERPShell = (() => {
  let _currentApp = null;
  let _loading = false;

  /* ─── DOM refs ─── */
  const $ = (sel) => document.querySelector(sel);
  const el = {
    sidebar: $('#sidebar'),
    nav: $('#app-nav'),
    container: $('#app-container'),
    iframe: $('#app-iframe'),
    welcome: $('#welcome-screen'),
    welcomeApps: $('#welcome-apps'),
    title: $('#app-title'),
    userInfo: $('#user-info'),
    userName: $('#user-name'),
    userAvatar: $('#user-avatar'),
    connection: $('#connection-status'),
    toast: $('#toast-container'),
    menuBtn: $('#btn-menu'),
    logoutBtn: $('#btn-logout'),
  };

  /* ─── Toast ─── */
  function toast(message, type = 'info', duration = 3000) {
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.textContent = message;
    el.toast.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, duration);
  }

  /* ─── Navigation ─── */
  function navigate(slug) {
    if (_loading || slug === _currentApp) return;

    const app = ERPAppRegistry.get(slug);
    if (!app) {
      toast(`ไม่พบ Mini App "${slug}"`, 'error');
      return;
    }

    // ตรวจสอบ role
    const roleHierarchy = ['viewer', 'editor', 'developer', 'mini-app', 'admin'];
    const userLevel = roleHierarchy.indexOf(ERPAuth.getRole());
    const reqLevel = roleHierarchy.indexOf(app.requiredRole);
    if (reqLevel !== -1 && userLevel < reqLevel) {
      toast(`ไม่มีสิทธิ์เข้าใช้ "${app.name}"`, 'error');
      return;
    }

    _currentApp = slug;
    _loading = true;

    // อัปเดต UI
    el.title.textContent = app.name;
    el.welcome.classList.add('hidden');
    el.iframe.classList.remove('hidden');

    // แสดง loading
    const loader = document.createElement('div');
    loader.className = 'loading-overlay';
    loader.innerHTML = '<div class="spinner"></div>';
    el.container.appendChild(loader);

    // โหลด iframe
    el.iframe.src = app.url;
    el.iframe.onload = () => {
      loader.remove();
      _loading = false;
      ERPAuth.shareTokenWithApp(el.iframe, slug);
      toast(`เปิด "${app.name}" แล้ว`, 'success');
    };
    el.iframe.onerror = () => {
      loader.remove();
      _loading = false;
      toast(`ไม่สามารถโหลด "${app.name}" ได้`, 'error');
    };

    // อัปเดต nav active
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.toggle('active', item.dataset.slug === slug);
    });

    // ปิด sidebar บนมือถือ
    el.sidebar.classList.remove('open');
  }

  /* ─── Render Sidebar Nav ─── */
  function renderNav() {
    const apps = ERPAppRegistry.getAvailable(ERPAuth.getRole());
    el.nav.innerHTML = '';

    if (apps.length === 0) {
      el.nav.innerHTML = '<div style="padding:16px;color:var(--color-text-dim);font-size:13px;">ไม่มี Mini App ที่เข้าใช้ได้</div>';
      return;
    }

    apps.forEach(app => {
      const item = document.createElement('div');
      item.className = 'nav-item';
      item.dataset.slug = app.slug;
      item.innerHTML = `
        <span class="nav-icon">${app.icon}</span>
        <span>${app.name}</span>
        ${app.badge ? `<span class="nav-badge">${app.badge}</span>` : ''}
      `;
      item.addEventListener('click', () => navigate(app.slug));
      el.nav.appendChild(item);
    });
  }

  /* ─── Render Welcome Screen ─── */
  function renderWelcome() {
    const apps = ERPAppRegistry.getAvailable(ERPAuth.getRole());
    el.welcomeApps.innerHTML = '';

    apps.slice(0, 6).forEach(app => {
      const btn = document.createElement('button');
      btn.className = 'welcome-app-btn';
      btn.innerHTML = `<span class="app-btn-icon">${app.icon}</span> ${app.name}`;
      btn.addEventListener('click', () => navigate(app.slug));
      el.welcomeApps.appendChild(btn);
    });
  }

  /* ─── อัปเดต User Info ─── */
  function updateUser() {
    const data = ERPAuth.getTokenData();
    if (data) {
      el.userName.textContent = data.sub || 'ไม่ระบุชื่อ';
      el.userAvatar.textContent = data.role === 'admin' ? '🔒' : '👤';
    } else {
      el.userName.textContent = 'ยังไม่เข้าสู่ระบบ';
      el.userAvatar.textContent = '👤';
    }
  }

  /* ─── กลับไปหน้าแรก ─── */
  function goHome() {
    _currentApp = null;
    el.title.textContent = 'ERP Modular';
    el.iframe.classList.add('hidden');
    el.iframe.src = '';
    el.welcome.classList.remove('hidden');
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
  }

  /* ─── Event Bus handlers ─── */
  function setupEventBus() {
    ERPEventBus.on('navigation.navigate', (envelope) => {
      if (envelope.data.slug) navigate(envelope.data.slug);
    });

    ERPEventBus.on('navigation.home', () => goHome());

    ERPEventBus.on('toast.show', (envelope) => {
      toast(envelope.data.message, envelope.data.type);
    });

    ERPEventBus.on('app.badge', (envelope) => {
      if (envelope.data.slug && envelope.data.count !== undefined) {
        ERPAppRegistry.setBadge(envelope.data.slug, envelope.data.count);
        renderNav();
      }
    });
  }

  /* ═══ Init ═══ */
  async function init(config) {
    // 1. เริ่มต้น Event Bus
    ERPEventBus.init();

    // 2. เริ่มต้น Auth
    ERPAuth.init();

    // 3. ฟังการเปลี่ยนแปลง auth
    ERPAuth.onChange(() => {
      updateUser();
      renderNav();
      renderWelcome();
    });

    // 4. ลงทะเบียน Mini Apps
    if (config && config.apps) {
      ERPAppRegistry.registerAll(config.apps);
    }

    // 5. ลองโหลดจาก Gateway
    if (!config || !config.apps) {
      await ERPAppRegistry.loadFromGateway(config?.gatewayUrl);
    }

    // 6. Render UI
    updateUser();
    renderNav();
    renderWelcome();

    // 7. Event Bus handlers
    setupEventBus();

    // 8. Menu toggle (มือถือ)
    el.menuBtn.addEventListener('click', () => {
      el.sidebar.classList.toggle('open');
    });

    // 9. Logout
    el.logoutBtn.addEventListener('click', () => {
      ERPAuth.logout();
      goHome();
      toast('ออกจากระบบแล้ว', 'info');
    });

    // 10. Connection status
    el.connection.classList.remove('disconnected');

    console.log('[Shell] ERP Modular พร้อมทำงาน');
    toast('ERP Modular พร้อมใช้งาน', 'success');
  }

  return { init, navigate, goHome, toast };
})();
