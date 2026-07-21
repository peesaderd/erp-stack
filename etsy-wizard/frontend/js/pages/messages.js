const MessagesPage = {
  render() {
    const msgs = [
      { from:'Etsy Support', subject:'Your shop has been verified', date:'2026-06-03', unread:false },
      { from:'Printful', subject:'Order #5001 — Shipped', date:'2026-06-05', unread:true },
      { from:'Etsy Marketplace', subject:'New feature: AI-powered tags', date:'2026-06-01', unread:false },
      { from:'System', subject:'Weekly report ready', date:'2026-05-28', unread:false },
    ];
    return `
      <div class="content-header"><div><h2>Messages</h2><p>${msgs.filter(m=>m.unread).length} unread</p></div><button class="btn">✉️ Compose</button></div>
      <div class="card">
        ${msgs.map(m => `
          <div style="display:flex;align-items:center;gap:12px;padding:14px 20px;border-bottom:1px solid var(--border);cursor:pointer" onclick="alert('Message detail')">
            <div style="width:36px;height:36px;border-radius:50%;background:${m.unread ? 'var(--accent)' : 'var(--bg4)'};display:flex;align-items:center;justify-content:center;font-size:14px">📩</div>
            <div style="flex:1;min-width:0">
              <div style="font-size:13px;font-weight:${m.unread ? '600' : '400'}">${m.from}</div>
              <div style="font-size:12px;color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${m.subject}</div>
            </div>
            <div style="font-size:11px;color:var(--text2)">${m.date}</div>
            ${m.unread ? '<div style="width:8px;height:8px;border-radius:50%;background:var(--accent)"></div>' : ''}
          </div>`).join('')}
      </div>`;
  },
  afterRender() {}
};
