const SettingsPage = {
  render() {
    return `
      <div class="content-header"><div><h2>Settings</h2><p>Configure your dashboard and API connections</p></div></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:800px">
        <div class="card">
          <div class="card-header"><h3>🔗 Etsy API</h3></div>
          <div class="card-body">
            <div class="form-group"><label>Shop Name</label><input type="text" value="ArtisanCrafts" disabled></div>
            <div class="form-group"><label>API Key</label><input type="text" placeholder="Enter Etsy API key"></div>
            <div class="form-group"><label>Shared Secret</label><input type="password" placeholder="Enter shared secret"></div>
            <div class="form-actions"><button class="btn btn-primary" onclick="alert('Saved! (Integration coming soon)')">Save</button></div>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3>🎨 Display</h3></div>
          <div class="card-body">
            <div class="form-group"><label>Theme</label>
              <div style="display:flex;gap:8px">
                <button class="btn" onclick="App.toggleTheme();App.route()" id="theme-dark" style="flex:1">🌙 Dark</button>
                <button class="btn" onclick="App.toggleTheme();App.route()" id="theme-light" style="flex:1">☀️ Light</button>
              </div>
            </div>
            </div>
            <div class="form-group"><label>Currency</label>
              <select><option>USD ($)</option><option>THB (฿)</option><option>EUR (€)</option></select>
            </div>
            <div class="form-group"><label>Timezone</label>
              <select><option>UTC+7 (ICT)</option><option>UTC (GMT)</option><option>UTC-5 (EST)</option></select>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3>📦 POD Providers</h3></div>
          <div class="card-body">
            <div class="form-group" style="display:flex;align-items:center;gap:8px">
              <input type="checkbox" checked id="pf"><label for="pf">Printful</label>
            </div>
            <div class="form-group" style="display:flex;align-items:center;gap:8px">
              <input type="checkbox" id="pr"><label for="pr">Printify (coming soon)</label>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-header"><h3>🔄 Sync</h3></div>
          <div class="card-body">
            <p style="font-size:13px;color:var(--text2);margin-bottom:12px">Last synced: Never</p>
            <button class="btn" onclick="alert('Syncing…')">⟳ Sync Now</button>
            <button class="btn" style="margin-left:8px" onclick="DashboardPage.showConnect()">🔗 Configure API</button>
          </div>
        </div>
      </div>`;
  },
  afterRender() {}
};
