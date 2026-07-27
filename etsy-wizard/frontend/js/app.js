/* ─── Main App ─── */
const App = {
  pages: {
    dashboard: { label: 'Dashboard', icon: '📊', render: () => DashboardPage.render(), after: () => DashboardPage.afterRender() },
    gallery:   { label: 'Gallery', icon: '🖼️', render: () => GalleryPage.render(), after: () => GalleryPage.afterRender() },
    wizard:    { label: 'POD Wizard', icon: '✨', render: () => WizardPage.render(), after: () => WizardPage.afterRender() },
    listings:  { label: 'Listings', icon: '📋', render: () => ListingsPage.render(), after: () => ListingsPage.afterRender() },
    messages:  { label: 'More', icon: '💬', render: () => MessagesPage.render(), after: () => MessagesPage.afterRender() },
    settings:  { label: 'Settings', icon: '⚙️', render: () => SettingsPage.render(), after: () => SettingsPage.afterRender() }
  },

  async init() {
    this.initTheme();
    window.addEventListener('hashchange', () => this.route());
    window.addEventListener('load', () => this.route());
    this.route();
  },

  initTheme() {
    const saved = localStorage.getItem('dashboard_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
  },

  toggleTheme() {
    const cur = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('dashboard_theme', next);
    const btn = document.querySelector('.theme-toggle');
    if (btn) btn.textContent = next === 'dark' ? '☀️' : '🌙';
  },

  themeIcon() {
    const cur = document.documentElement.getAttribute('data-theme') || 'dark';
    return cur === 'dark' ? '☀️' : '🌙';
  },

  async route() {
    const hash = window.location.hash.replace('#', '') || 'dashboard';
    const page = this.pages[hash];
    if (!page) { this.nav('dashboard'); return; }

    const app = document.getElementById('app');
    try {
      app.innerHTML = this.layout(page.label, await page.render());
    } catch(e) {
      console.error(e);
      app.innerHTML = this.layout(page.label, '<div class="loading"><div class="spinner"></div><p>Error loading page</p></div>');
    }

    document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.page === hash));
    requestAnimationFrame(() => page.after());
  },

  layout(title, content) {
    return `
      <div class="app-layout">
        <aside class="sidebar" id="sidebar">
          <div class="sidebar-brand">
            <h1>PeteAI</h1>
            <span>Etsy Dashboard</span>
          </div>
          <nav class="sidebar-nav">${this._navItems()}</nav>
          <div class="sidebar-footer">
            <button class="nav-item" data-page="settings" onclick="App.nav('settings')">
              <span class="icon">⚙️</span><span class="label">Settings</span>
            </button>
          </div>
        </aside>
        <div class="main">
          <header class="topbar">
            <div class="topbar-left">
              <button class="mobile-toggle" onclick="App.toggleSidebar()">☰</button>
              <h2>${title}</h2>
              <span class="shop-name">· <strong>ArtisanCrafts</strong></span>
            </div>
            <div class="topbar-right">
              <span class="status-badge">Live</span>
              <button class="theme-toggle" onclick="App.toggleTheme()" title="Toggle theme">${this.themeIcon()}</button>
              <button class="btn btn-sm" onclick="DashboardPage.showConnect()">🔗 Connect Etsy API</button>
              <div class="avatar" title="ArtisanCrafts">AC</div>
            </div>
          </header>
          <div class="content">${content}</div>
        </div>
      </div>`;
  },

  _navItems() {
    const items = [
      { id: 'dashboard', label: 'Dashboard', icon: '📊' },
      { id: 'gallery', label: 'Gallery', icon: '🖼️' },
      { id: 'wizard', label: 'POD Wizard', icon: '✨' },
      { id: 'listings', label: 'Listings', icon: '📋' },
      { id: 'messages', label: 'More', icon: '💬' },
    ];
    const hash = window.location.hash.replace('#', '') || 'dashboard';
    return items.map(i => `
      <button class="nav-item ${hash === i.id ? 'active' : ''}" data-page="${i.id}" onclick="App.nav('${i.id}')">
        <span class="icon">${i.icon}</span><span class="label">${i.label}</span>
      </button>`).join('');
  },

  nav(page) {
    window.location.hash = '#' + page;
    this.closeSidebar();
    return false;
  },

  toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); },
  closeSidebar() { const s = document.getElementById('sidebar'); if (s) s.classList.remove('open'); },

  showModal(title, body) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'modal';
    overlay.innerHTML = '<div class="modal">' +
      '<button class="modal-close" onclick="App.closeModal()">✕</button>' +
      '<h3>' + title + '</h3>' + body + '</div>';
    overlay.addEventListener('click', (e) => { if (e.target === overlay) App.closeModal(); });
    document.body.appendChild(overlay);
  },

  closeModal() {
    const m = document.getElementById('modal');
    if (m) m.remove();
  }
};

document.addEventListener('DOMContentLoaded', () => App.init());
