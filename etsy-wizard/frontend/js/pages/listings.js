const ListingsPage = {
  async render() {
    const data = API._mockStats();
    return `
      <div class="content-header">
        <div><h2>Listings</h2><p>Manage your Etsy product listings</p></div>
        <div style="display:flex;gap:8px">
          <button class="btn">📥 Import</button>
          <button class="btn btn-primary" onclick="App.nav('wizard')">✨ New Listing</button>
        </div>
      </div>
      <div class="stats-grid" style="grid-template-columns:repeat(3,1fr)">
        <div class="stat-card"><div class="stat-label">Active</div><div class="stat-value">6</div></div>
        <div class="stat-card"><div class="stat-label">Drafts</div><div class="stat-value">1</div></div>
        <div class="stat-card"><div class="stat-label">Expired</div><div class="stat-value">1</div></div>
      </div>
      <div class="card">
        <div class="card-header"><div><h3>All Listings</h3><p>${data.activeListings.length + 2} total</p></div>
          <div style="display:flex;gap:8px">
            <select style="padding:6px 10px;border-radius:6px;border:1px solid var(--border);background:var(--bg3);color:var(--text);font-size:12px">
              <option>All Status</option><option>Active</option><option>Draft</option><option>Expired</option>
            </select>
          </div>
        </div>
        <div class="card-body table-wrap">
          <table>
            <thead><tr><th>Item</th><th>Price</th><th>Views</th><th>Favorites</th><th>Stock</th><th>Status</th><th></th></tr></thead>
            <tbody>
              ${data.activeListings.map(l => `<tr>
                <td><strong>${l.name}</strong></td>
                <td>${Charts.money(l.price)}</td>
                <td class="td-label">${Charts.formatNum(l.views)}</td>
                <td class="td-label">${l.favs}</td>
                <td class="td-label">${l.stock}</td>
                <td>${Charts.statusBadge(l.status)}</td>
                <td><button class="btn btn-sm" onclick="alert('Edit listing')">✏️</button></td>
              </tr>`).join('')}
              <tr><td><strong>Vintage Postcard Collection</strong></td><td>$15.00</td><td class="td-label">—</td><td class="td-label">—</td><td class="td-label">—</td><td>${Charts.statusBadge('Draft')}</td><td><button class="btn btn-sm btn-primary" onclick="App.nav('wizard')">Continue</button></td></tr>
              <tr><td><strong>Silk Scarf — Floral Pattern</strong></td><td>$35.00</td><td class="td-label">—</td><td class="td-label">—</td><td class="td-label">—</td><td>${Charts.statusBadge('Expired')}</td><td><button class="btn btn-sm" onclick="alert('Relist item')">Relist</button></td></tr>
            </tbody>
          </table>
        </div>
      </div>`;
  },
  afterRender() {}
};
