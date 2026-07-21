const GalleryPage = {
  async render() {
    try {
      const products = await API.getProducts();
      return `
        <div class="content-header"><div><h2>Gallery</h2><p>Browse product mockups and designs</p></div></div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px">
          ${(products.products || []).map(p => `
            <div class="card" style="cursor:pointer" onclick="GalleryPage.view('${p.id}')">
              <div style="height:200px;background:var(--bg3);display:flex;align-items:center;justify-content:center;font-size:48px">${p.icon || '👕'}</div>
              <div style="padding:12px"><strong style="font-size:13px">${p.name}</strong><br><span style="font-size:12px;color:var(--text2)">${p.category || 'POD Product'}</span></div>
            </div>`).join('') || '<div class="loading"><div class="spinner"></div>Loading products…</div>'}
        </div>`;
    } catch(e) {
      // Fallback product grid
      const fallback = [
        { name:'Vintage Botanical Art Print', icon:'🖼️', cat:'Posters' },
        { name:'Hand-Carved Wooden Spoon Set', icon:'🥄', cat:'Kitchen' },
        { name:'Minimalist Ceramic Vase', icon:'🏺', cat:'Home Decor' },
        { name:'Macrame Wall Hanging', icon:'🧵', cat:'Wall Art' },
        { name:'Scented Soy Candle Trio', icon:'🕯️', cat:'Candles' },
        { name:'Wool Beanie — Earth Tones', icon:'🧢', cat:'Accessories' },
      ];
      return `
        <div class="content-header"><div><h2>Gallery</h2><p>Browse product mockups and designs</p></div></div>
        <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px">
          ${fallback.map(p => `
            <div class="card" style="cursor:pointer">
              <div style="height:200px;background:var(--bg3);display:flex;align-items:center;justify-content:center;font-size:48px">${p.icon}</div>
              <div style="padding:12px"><strong style="font-size:13px">${p.name}</strong><br><span style="font-size:12px;color:var(--text2)">${p.cat}</span></div>
            </div>`).join('')}
        </div>`;
    }
  },
  afterRender() {},
  view(id) { App.nav('wizard'); }
};
