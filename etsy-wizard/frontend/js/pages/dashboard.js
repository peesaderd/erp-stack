/* ─── Dashboard Page ─── */
const DashboardPage = {
  async render() {
    const data = await API.getStats();
    return `
      <div class="content-header">
        <div><h2>Dashboard</h2><p>Welcome back, ${data.shopName || 'ArtisanCrafts'}</p></div>
        <div style="display:flex;align-items:center;gap:12px">
          <span class="status-badge">Live</span>
          <button class="btn btn-sm" onclick="DashboardPage.sync()">⟳ Sync</button>
          <button class="btn btn-sm btn-primary" onclick="DashboardPage.showConnect()">🔗 Connect Etsy API</button>
        </div>
      </div>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">Total Revenue</div>
          <div class="stat-value">${Charts.money(data.revenue.value)}</div>
          <div class="stat-change ${data.revenue.trend}">${data.revenue.trend === 'up' ? '↑' : '↓'} ${data.revenue.change}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Active Listings</div>
          <div class="stat-value">${data.listings.value}</div>
          <div class="stat-change up">↑ ${data.listings.change}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Orders This Week</div>
          <div class="stat-value">${data.orders.value}</div>
          <div class="stat-change up">↑ ${data.orders.change}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Avg. Order Value</div>
          <div class="stat-value">${Charts.money(data.avgOrder.value)}</div>
          <div class="stat-change ${data.avgOrder.trend}">${data.avgOrder.trend === 'up' ? '↑' : '↓'} ${data.avgOrder.change}</div>
        </div>
      </div>
      <div class="dash-grid">
        <div class="card">
          <div class="card-header"><div><h3>Weekly Sales</h3><p>Revenue over the last 7 days</p></div><span style="font-size:12px;color:var(--green)">↑ +8.3% vs last week</span></div>
          <div class="card-body" id="weekly-chart"></div>
        </div>
        <div class="card">
          <div class="card-header"><div><h3>Listing Status</h3><p>${data.listingStatus.reduce((s,d)=>s+d.value,0)} total listings</p></div></div>
          <div class="card-body" id="listing-chart"></div>
        </div>
      </div>
      <div class="dash-row">
        <div class="card">
          <div class="card-header"><div><h3>Recent Orders</h3><p>${data.recentOrders.filter(o=>o.status==='Processing'||o.status==='Paid').length} awaiting action</p></div><a href="#" onclick="return App.nav('listings')" style="font-size:13px">View all →</a></div>
          <div class="card-body table-wrap">${this._ordersTable(data.recentOrders)}</div>
        </div>
        <div class="card">
          <div class="card-header"><div><h3>Active Listings</h3><p>${data.activeListings.length} items listed</p></div><a href="#" onclick="return App.nav('listings')" style="font-size:13px">View all →</a></div>
          <div class="card-body table-wrap">${this._listingsTable(data.activeListings)}</div>
        </div>
      </div>`;
  },

  afterRender() {
    // Only call after the DOM is ready
    requestAnimationFrame(() => {
      const stats = API._mockStats();
      const chartEl = document.getElementById('weekly-chart');
      const listEl = document.getElementById('listing-chart');
      if (chartEl) Charts.barChart(chartEl, stats.weeklySales, {});
      if (listEl) Charts.donutChart(listEl, stats.listingStatus);
    });
  },

  _ordersTable(orders) {
    return `<table>
      <thead><tr><th>Order</th><th>Buyer</th><th>Date</th><th>Total</th><th>Status</th></tr></thead>
      <tbody>${orders.map(o => `<tr><td><strong>${o.id}</strong></td><td>${o.buyer}</td><td class="td-label">${o.date}</td><td>${Charts.money(o.total)}</td><td>${Charts.statusBadge(o.status)}</td></tr>`).join('')}</tbody>
    </table>`;
  },

  _listingsTable(listings) {
    return `<table>
      <thead><tr><th>Item</th><th>Price</th><th>Views</th><th>Favorites</th><th>Stock</th><th>Status</th></tr></thead>
      <tbody>${listings.map(l => `<tr><td>${l.name}</td><td>${Charts.money(l.price)}</td><td class="td-label">${Charts.formatNum(l.views)}</td><td class="td-label">${l.favs}</td><td class="td-label">${l.stock}</td><td>${Charts.statusBadge(l.status)}</td></tr>`).join('')}</tbody>
    </table>`;
  },

  sync() {
    alert('Syncing Etsy data… (API integration coming soon)');
  },

  showConnect() {
    App.showModal('🔗 Connect Etsy API', `
      <p>To connect your Etsy shop, you need to configure Etsy API credentials.</p>
      <div class="form-group"><label>API Key</label><input type="text" placeholder="Enter your Etsy API key"></div>
      <div class="form-group"><label>Shared Secret</label><input type="text" placeholder="Enter your Etsy shared secret"></div>
      <div class="form-actions"><button class="btn" onclick="App.closeModal()">Cancel</button><button class="btn btn-primary" onclick="alert('Etsy API integration coming soon!')">Connect</button></div>
    `);
  }
};
