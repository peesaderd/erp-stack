/* ═══════════════════════════════════════════════════════════════════════════
   ERP Modular — Mini App Registry
   ═══════════════════════════════════════════════════════════════════════════
   ลงทะเบียนและจัดการ Mini Apps ที่ Shell โหลดได้
   ═══════════════════════════════════════════════════════════════════════════ */

const ERPAppRegistry = (() => {
  const _apps = new Map();

  /* ─── ลงทะเบียน Mini App ─── */
  function register(slug, config) {
    if (!slug || !config) {
      console.error('[AppRegistry] ต้องระบุ slug และ config');
      return;
    }

    const defaults = {
      name: slug,
      description: '',
      icon: '📦',
      url: '',
      requiredRole: 'viewer',
      badge: 0,
      features: [],
    };

    _apps.set(slug, { ...defaults, ...config, slug });
    ERPEventBus.registerApp(slug, config.url);
    console.log(`[AppRegistry] ลงทะเบียน "${slug}" เรียบร้อย`);
  }

  /* ─── ลงทะเบียนหลายตัวพร้อมกัน ─── */
  function registerAll(apps) {
    if (!apps || typeof apps !== 'object') return;
    Object.entries(apps).forEach(([slug, config]) => register(slug, config));
  }

  /* ─── ดึงข้อมูล Mini App ─── */
  function get(slug) { return _apps.get(slug) || null; }

  function getAll() { return Array.from(_apps.values()); }

  function getAvailable(role) {
    const roleHierarchy = ['viewer', 'editor', 'developer', 'mini-app', 'admin'];
    const userLevel = roleHierarchy.indexOf(role);
    if (userLevel === -1) return [];

    return Array.from(_apps.values()).filter(app => {
      const reqLevel = roleHierarchy.indexOf(app.requiredRole);
      return reqLevel !== -1 && userLevel >= reqLevel;
    });
  }

  /* ─── อัปเดต badge ─── */
  function setBadge(slug, count) {
    const app = _apps.get(slug);
    if (app) { app.badge = count; }
  }

  /* ─── โหลดรายการ Mini Apps จาก Gateway ─── */
  async function loadFromGateway(gatewayUrl) {
    try {
      const url = gatewayUrl || '/gateway/apps';
      const resp = await fetch(url, {
        headers: { ...ERPAuth.authHeader() },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const data = await resp.json();
      if (data.apps && Array.isArray(data.apps)) {
        data.apps.forEach(app => {
          register(app.slug, {
            name: app.name,
            description: app.description,
            url: app.url,
            icon: app.icon || '📦',
          });
        });
        console.log(`[AppRegistry] โหลด ${data.apps.length} apps จาก Gateway`);
      }
      return data.apps || [];
    } catch (err) {
      console.warn('[AppRegistry] ไม่สามารถโหลดจาก Gateway ได้:', err.message);
      return [];
    }
  }

  return {
    register, registerAll, loadFromGateway,
    get, getAll, getAvailable, setBadge,
  };
})();
