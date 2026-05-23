/* ═══════════════════════════════════════════════════════════════════════════
   ERP Modular — Shell Configuration
   ═══════════════════════════════════════════════════════════════════════════
   แก้ไขไฟล์นี้เพื่อกำหนดค่า Mini Apps และ Gateway URL
   ═══════════════════════════════════════════════════════════════════════════ */

window.ERP_CONFIG = {
  /* URL ของ API Gateway (ไม่ต้องเปลี่ยนถ้า Shell อยู่บน origin เดียวกับ Gateway) */
  gatewayUrl: '/gateway',

  /* Mini Apps ที่ Shell โหลดได้
     ถ้าตั้งค่าไว้ จะใช้ค่านี้ก่อน — ถ้าไม่ตั้ง จะโหลดจาก Gateway API */
  apps: {
    /* ─── Project Management ─── */
    plane: {
      name: 'Plane',
      icon: '📋',
      url: 'http://130.61.230.127:54512',
      description: 'Project Management — Issues, Sprints, Cycles',
      requiredRole: 'editor',
    },

    /* ─── Kanban Board ─── */
    planka: {
      name: 'Planka',
      icon: '📌',
      url: 'http://130.61.230.127:54513',
      description: 'Kanban Board — Cards, Lists, Boards',
      requiredRole: 'editor',
    },

    /* ─── Documentation ─── */
    bookstack: {
      name: 'BookStack',
      icon: '📚',
      url: 'http://89.167.82.205:54515',
      description: 'Documentation Wiki — Shelves, Books, Pages',
      requiredRole: 'viewer',
    },

    /* ─── Knowledge Base ─── */
    siyuan: {
      name: 'Siyuan',
      icon: '🧠',
      url: 'http://130.61.230.127:54511',
      description: 'Knowledge Base — Notes, Docs, Blocks',
      requiredRole: 'viewer',
    },

    /* ─── Logging & Metrics ─── */
    openobserve: {
      name: 'OpenObserve',
      icon: '📊',
      url: 'http://130.61.230.127:54514',
      description: 'Logging, Metrics, Traces',
      requiredRole: 'admin',
    },
  },
};
