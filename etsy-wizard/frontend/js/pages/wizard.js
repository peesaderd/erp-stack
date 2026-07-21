/* ─── POD Wizard 10-Step Flow ─── */
const WizardPage = {
  _steps: [
    { id: 'provider', label: 'Provider', icon: '🛒' },
    { id: 'category', label: 'Category', icon: '📁' },
    { id: 'product', label: 'Product', icon: '👕' },
    { id: 'variant', label: 'Variant', icon: '🎨' },
    { id: 'print_info', label: 'Print Info', icon: '🖨️' },
    { id: 'artwork', label: 'Artwork', icon: '🎭' },
    { id: 'mockup', label: 'Mockup', icon: '📸' },
    { id: 'content', label: 'Content', icon: '✍️' },
    { id: 'pricing', label: 'Pricing', icon: '💰' },
    { id: 'summary', label: 'Summary', icon: '✅' }
  ],

  _session: null,

  render() {
    // Try to restore saved session
    try {
      const saved = localStorage.getItem('wizard_session');
      if (saved) this._session = JSON.parse(saved);
    } catch(e) {}
    if (!this._session) {
      this._session = { step: 0, data: {}, sessionId: null };
    }
    return this._renderWizard();
  },

  _renderWizard() {
    const step = this._session.step;
    const total = this._steps.length;
    return `
      <div class="content-header"><div><h2>POD Wizard</h2><p>Create a print-on-demand product — Step ${step+1} of ${total}</p></div></div>
      <div class="wizard-layout">
        <div class="wizard-sidebar">
          ${this._steps.map((s, i) => `
            <div class="wiz-step ${i < step ? 'done' : ''} ${i === step ? 'active' : ''}" onclick="WizardPage._goStep(${i})">
              <div class="wiz-step-num">${i < step ? '✓' : i+1}</div>
              <div class="wiz-step-info">
                <div class="wiz-step-label">${s.icon} ${s.label}</div>
                <div class="wiz-step-desc">${this._stepDesc(s.id)}</div>
              </div>
            </div>
          `).join('')}
        </div>
        <div class="wizard-content">
          ${this._renderStep(step)}
        </div>
      </div>`;
  },

  _stepDesc(id) {
    const descs = {
      provider: 'Select POD provider',
      category: 'Product category',
      product: 'Choose product',
      variant: 'Size & color',
      print_info: 'Print areas',
      artwork: 'Upload design',
      mockup: 'Generate preview',
      content: 'Title & tags',
      pricing: 'Set price',
      summary: 'Review & save'
    };
    return descs[id] || '';
  },

  _renderStep(idx) {
    const step = this._steps[idx];
    if (!step) return '<div class="loading">Invalid step</div>';
    try {
      return this[`_step_${step.id}`]();
    } catch(e) {
      console.error('Step render error:', e);
      return `<div class="loading"><div class="spinner"></div></div>`;
    }
  },

  /* ── Step 0: Provider ── */
  _step_provider() {
    return `
      <div class="wiz-content">
        <h3 class="wiz-title">🛒 Choose Provider</h3>
        <p class="wiz-sub">Select your print-on-demand provider</p>
        <div class="wiz-grid">
          <div class="wiz-card ${this._session.data.provider === 'printful' ? 'selected' : ''}" onclick="WizardPage._select('provider','printful')">
            <div class="wiz-card-icon">🖨️</div>
            <div class="wiz-card-name">Printful</div>
            <div class="wiz-card-desc">High quality POD • Global fulfillment</div>
          </div>
          <div class="wiz-card disabled">
            <div class="wiz-card-icon">🖨️</div>
            <div class="wiz-card-name">Printify</div>
            <div class="wiz-card-desc">Coming soon…</div>
          </div>
        </div>
      </div>
      <div class="wiz-actions">
        <span class="wiz-step-indicator">Step ${this._session.step+1} of ${this._steps.length}</span>
        <button class="btn btn-primary" onclick="WizardPage._next()" ${!this._session.data.provider ? 'disabled' : ''}>Save & Continue →</button>
      </div>`;
  },

  /* ── Step 1: Category ── */
  _step_category() {
    const cats = [
      { id: 't-shirts', icon: '👕', name: 'T-Shirts' },
      { id: 'hoodies', icon: '🧥', name: 'Hoodies' },
      { id: 'accessories', icon: '🧢', name: 'Accessories' },
      { id: 'mugs', icon: '☕', name: 'Mugs' },
      { id: 'posters', icon: '🖼️', name: 'Posters' },
      { id: 'phone-cases', icon: '📱', name: 'Phone Cases' },
      { id: 'bags', icon: '👜', name: 'Bags' },
      { id: 'hats', icon: '🧢', name: 'Hats' },
    ];
    return `
      <div class="wiz-content">
        <h3 class="wiz-title">📁 Select Category</h3>
        <p class="wiz-sub">What type of product do you want to create?</p>
        <div class="wiz-grid wiz-grid-small">
          ${cats.map(c => `
            <div class="wiz-card ${this._session.data.category === c.id ? 'selected' : ''}" onclick="WizardPage._select('category','${c.id}')">
              <div class="wiz-card-icon">${c.icon}</div>
              <div class="wiz-card-name">${c.name}</div>
            </div>`).join('')}
        </div>
      </div>
      <div class="wiz-actions">
        <button class="btn" onclick="WizardPage._prev()">← Back</button>
        <span class="wiz-step-indicator">Step ${this._session.step+1} of ${this._steps.length}</span>
        <button class="btn btn-primary" onclick="WizardPage._next()" ${!this._session.data.category ? 'disabled' : ''}>Save & Continue →</button>
      </div>`;
  },

  /* ── Step 2: Product ── */
  _step_product() {
    const products = [
      { id: 'standard-tshirt', name: 'Standard T-Shirt', price: 14.95 },
      { id: 'premium-tshirt', name: 'Premium T-Shirt', price: 19.95 },
      { id: 'longsleeve', name: 'Long Sleeve T-Shirt', price: 22.95 },
      { id: 'tank-top', name: 'Tank Top', price: 12.95 },
    ];
    return `
      <div class="wiz-content">
        <h3 class="wiz-title">👕 Select Product</h3>
        <p class="wiz-sub">Choose a product to customize</p>
        <div class="wiz-grid">
          ${products.map(p => `
            <div class="wiz-card ${this._session.data.product === p.id ? 'selected' : ''}" onclick="WizardPage._select('product','${p.id}')">
              <div class="wiz-card-icon">👕</div>
              <div class="wiz-card-name">${p.name}</div>
              <div class="wiz-card-desc">from $${p.price}</div>
            </div>`).join('')}
        </div>
      </div>
      <div class="wiz-actions">
        <button class="btn" onclick="WizardPage._prev()">← Back</button>
        <span class="wiz-step-indicator">Step ${this._session.step+1} of ${this._steps.length}</span>
        <button class="btn btn-primary" onclick="WizardPage._next()" ${!this._session.data.product ? 'disabled' : ''}>Save & Continue →</button>
      </div>`;
  },

  /* ── Step 3: Variant ── */
  _step_variant() {
    const colors = ['Black','White','Navy','Gray','Red'];
    const sizes = ['XS','S','M','L','XL','2XL'];
    const sel = this._session.data;
    return `
      <div class="wiz-content">
        <h3 class="wiz-title">🎨 Choose Variant</h3>
        <p class="wiz-sub">Select color and size options</p>
        <div class="form-group"><label>Color</label>
          <div class="wiz-chip-group">
            ${colors.map(c => `<span class="wiz-chip ${sel.color === c ? 'selected' : ''}" onclick="WizardPage._select('color','${c}')">${c}</span>`).join('')}
          </div>
        </div>
        <div class="form-group"><label>Size</label>
          <div class="wiz-chip-group">
            ${sizes.map(s => `<span class="wiz-chip ${sel.size === s ? 'selected' : ''}" onclick="WizardPage._select('size','${s}')">${s}</span>`).join('')}
          </div>
        </div>
      </div>
      <div class="wiz-actions">
        <button class="btn" onclick="WizardPage._prev()">← Back</button>
        <span class="wiz-step-indicator">Step ${this._session.step+1} of ${this._steps.length}</span>
        <button class="btn btn-primary" onclick="WizardPage._next()" ${!sel.color || !sel.size ? 'disabled' : ''}>Save & Continue →</button>
      </div>`;
  },

  /* ── Step 4: Print Info ── */
  _step_print_info() {
    return `
      <div class="wiz-content">
        <h3 class="wiz-title">🖨️ Print Information</h3>
        <p class="wiz-sub">Configure print placement and size</p>
        <div class="form-group"><label>Print Area</label>
          <select onchange="WizardPage._select('printArea',this.value)">
            <option value="">Select placement…</option>
            <option value="front" ${this._session.data.printArea === 'front' ? 'selected' : ''}>Front Center</option>
            <option value="back" ${this._session.data.printArea === 'back' ? 'selected' : ''}>Back Center</option>
            <option value="left-chest" ${this._session.data.printArea === 'left-chest' ? 'selected' : ''}>Left Chest</option>
            <option value="full-front" ${this._session.data.printArea === 'full-front' ? 'selected' : ''}>Full Front</option>
          </select>
        </div>
        <div class="form-group"><label>Print Size (inches)</label>
          <select onchange="WizardPage._select('printSize',this.value)">
            <option value="">Select size…</option>
            <option value="8x10" ${this._session.data.printSize === '8x10' ? 'selected' : ''}>8" × 10"</option>
            <option value="10x12" ${this._session.data.printSize === '10x12' ? 'selected' : ''}>10" × 12"</option>
            <option value="12x16" ${this._session.data.printSize === '12x16' ? 'selected' : ''}>12" × 16"</option>
            <option value="full" ${this._session.data.printSize === 'full' ? 'selected' : ''}>Full Print Area</option>
          </select>
        </div>
      </div>
      <div class="wiz-actions">
        <button class="btn" onclick="WizardPage._prev()">← Back</button>
        <span class="wiz-step-indicator">Step ${this._session.step+1} of ${this._steps.length}</span>
        <button class="btn btn-primary" onclick="WizardPage._next()" ${!this._session.data.printArea ? 'disabled' : ''}>Save & Continue →</button>
      </div>`;
  },

  /* ── Step 5: Artwork ── */
  _step_artwork() {
    return `
      <div class="wiz-content">
        <h3 class="wiz-title">🎭 Artwork</h3>
        <p class="wiz-sub">Upload your design or generate with AI</p>
        <div class="wiz-upload-area" id="artwork-drop" onclick="document.getElementById('artwork-file').click()">
          <div style="font-size:48px;margin-bottom:8px">🎨</div>
          <div style="font-size:14px;font-weight:500">${this._session.data.artwork ? '✓ ' + this._session.data.artwork.name : 'Click to upload artwork'}</div>
          <div style="font-size:12px;color:var(--text2);margin-top:4px">PNG, JPG, SVG • Max 20MB</div>
          <input type="file" id="artwork-file" accept="image/*" style="display:none" onchange="WizardPage._uploadArt(this)">
        </div>
        <div style="text-align:center;margin-top:16px">
          <button class="btn" onclick="WizardPage._genArt()">🤖 Generate with AI</button>
        </div>
      </div>
      <div class="wiz-actions">
        <button class="btn" onclick="WizardPage._prev()">← Back</button>
        <span class="wiz-step-indicator">Step ${this._session.step+1} of ${this._steps.length}</span>
        <button class="btn btn-primary" onclick="WizardPage._next()" ${!this._session.data.artwork ? 'disabled' : ''}>Save & Continue →</button>
      </div>`;
  },

  /* ── Step 6: Mockup ── */
  _step_mockup() {
    return `
      <div class="wiz-content">
        <h3 class="wiz-title">📸 Generate Mockup</h3>
        <p class="wiz-sub">Preview your product with AI-generated mockups</p>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
          <div class="card"><div style="height:280px;background:var(--bg3);display:flex;align-items:center;justify-content:center;font-size:48px">👕</div><div style="padding:12px;text-align:center;font-size:13px">Front View</div></div>
          <div class="card"><div style="height:280px;background:var(--bg3);display:flex;align-items:center;justify-content:center;font-size:48px">👕</div><div style="padding:12px;text-align:center;font-size:13px">Back View</div></div>
        </div>
        <div style="text-align:center;margin-top:16px">
          <button class="btn btn-primary" onclick="alert('🎨 Mockup generation will render your artwork on the product')">✨ Generate Mockups</button>
        </div>
      </div>
      <div class="wiz-actions">
        <button class="btn" onclick="WizardPage._prev()">← Back</button>
        <span class="wiz-step-indicator">Step ${this._session.step+1} of ${this._steps.length}</span>
        <button class="btn btn-primary" onclick="WizardPage._next()">Save & Continue →</button>
      </div>`;
  },

  /* ── Step 7: Content ── */
  _step_content() {
    const d = this._session.data;
    return `
      <div class="wiz-content">
        <h3 class="wiz-title">✍️ Content & SEO</h3>
        <p class="wiz-sub">Write your listing content or generate with AI</p>
        <div class="form-group"><label>Title</label>
          <textarea rows="2" placeholder="Enter a compelling product title" id="wiz-title">${d.title || ''}</textarea>
        </div>
        <div class="form-group"><label>Description</label>
          <textarea rows="4" placeholder="Describe your product in detail" id="wiz-desc">${d.description || ''}</textarea>
        </div>
        <div class="form-group"><label>Tags (comma separated)</label>
          <input type="text" placeholder="handmade, gift, art, design" id="wiz-tags" value="${d.tags || ''}">
        </div>
        <div style="text-align:center;margin-top:12px">
          <button class="btn" onclick="WizardPage._genContent()">🤖 Generate with AI</button>
          <button class="btn" onclick="WizardPage._optTags()">🏷️ Optimize Tags</button>
        </div>
      </div>
      <div class="wiz-actions">
        <button class="btn" onclick="WizardPage._prev()">← Back</button>
        <span class="wiz-step-indicator">Step ${this._session.step+1} of ${this._steps.length}</span>
        <button class="btn btn-primary" onclick="WizardPage._saveContent(); WizardPage._next()">Save & Continue →</button>
      </div>`;
  },

  /* ── Step 8: Pricing ── */
  _step_pricing() {
    const d = this._session.data;
    return `
      <div class="wiz-content">
        <h3 class="wiz-title">💰 Pricing</h3>
        <p class="wiz-sub">Set your selling price</p>
        <div class="form-group"><label>Selling Price (USD)</label>
          <input type="number" step="0.01" min="0" placeholder="29.99" id="wiz-price" value="${d.price || ''}">
        </div>
        <div class="form-group"><label>Sale Price (optional)</label>
          <input type="number" step="0.01" min="0" placeholder="19.99" id="wiz-sale" value="${d.salePrice || ''}">
        </div>
        <div class="form-group"><label>Quantity in Stock</label>
          <input type="number" min="0" placeholder="100" id="wiz-qty" value="${d.quantity || '100'}">
        </div>
      </div>
      <div class="wiz-actions">
        <button class="btn" onclick="WizardPage._prev()">← Back</button>
        <span class="wiz-step-indicator">Step ${this._session.step+1} of ${this._steps.length}</span>
        <button class="btn btn-primary" onclick="WizardPage._savePricing(); WizardPage._next()" ${!d.price ? 'disabled' : ''}>Save & Continue →</button>
      </div>`;
  },

  /* ── Step 9: Summary ── */
  _step_summary() {
    const d = this._session.data;
    return `
      <div class="wiz-content">
        <h3 class="wiz-title">✅ Summary</h3>
        <p class="wiz-sub">Review your product before saving</p>
        <div class="card" style="margin-bottom:16px">
          <div class="card-body">
            <div class="summary-row"><span class="summary-label">Provider</span><span>${d.provider || '—'}</span></div>
            <div class="summary-row"><span class="summary-label">Category</span><span>${d.category || '—'}</span></div>
            <div class="summary-row"><span class="summary-label">Product</span><span>${d.product || '—'}</span></div>
            <div class="summary-row"><span class="summary-label">Color/Size</span><span>${d.color || '—'} / ${d.size || '—'}</span></div>
            <div class="summary-row"><span class="summary-label">Print Area</span><span>${d.printArea || '—'} (${d.printSize || '—'})</span></div>
            <div class="summary-row"><span class="summary-label">Artwork</span><span>${d.artwork ? '✓ Uploaded' : '—'}</span></div>
            <div class="summary-row"><span class="summary-label">Title</span><span>${d.title || '—'}</span></div>
            <div class="summary-row"><span class="summary-label">Price</span><span>${d.price ? '$' + d.price : '—'}</span></div>
            <div class="summary-row"><span class="summary-label">Quantity</span><span>${d.quantity || '—'}</span></div>
          </div>
        </div>
        <div style="text-align:center">
          <button class="btn btn-primary" onclick="WizardPage._saveDraft()" style="font-size:15px;padding:12px 32px">💾 Save as Draft</button>
        </div>
      </div>
      <div class="wiz-actions">
        <button class="btn" onclick="WizardPage._prev()">← Back</button>
        <span class="wiz-step-indicator">Step ${this._session.step+1} of ${this._steps.length}</span>
        <button class="btn btn-primary" onclick="WizardPage._saveDraft()">💾 Save & Publish to Etsy</button>
      </div>`;
  },

  /* ── Helpers ── */
  _select(key, value) {
    this._session.data[key] = value;
    this._save();
    App.route();
  },

  _save() {
    this._session.updatedAt = Date.now();
    try { localStorage.setItem('wizard_session', JSON.stringify(this._session)); } catch(e) {}
  },

  _next() {
    if (this._session.step < this._steps.length - 1) {
      this._session.step++;
      this._save();
      App.route();
    }
  },

  _prev() {
    if (this._session.step > 0) {
      this._session.step--;
      this._save();
      App.route();
    }
  },

  _goStep(i) {
    // Only allow going to completed or current steps
    if (i <= this._session.step) {
      this._session.step = i;
      this._save();
      App.route();
    }
  },

  _uploadArt(input) {
    if (input.files && input.files[0]) {
      this._session.data.artwork = { name: input.files[0].name, size: input.files[0].size };
      this._save();
      App.route();
    }
  },

  _genArt() {
    alert('🤖 AI artwork generation will be available when connected to an image generation API');
  },

  _saveContent() {
    const title = document.getElementById('wiz-title');
    const desc = document.getElementById('wiz-desc');
    const tags = document.getElementById('wiz-tags');
    if (title) this._session.data.title = title.value;
    if (desc) this._session.data.description = desc.value;
    if (tags) this._session.data.tags = tags.value;
    this._save();
  },

  _savePricing() {
    const price = document.getElementById('wiz-price');
    const sale = document.getElementById('wiz-sale');
    const qty = document.getElementById('wiz-qty');
    if (price) this._session.data.price = parseFloat(price.value) || 0;
    if (sale) this._session.data.salePrice = parseFloat(sale.value) || 0;
    if (qty) this._session.data.quantity = parseInt(qty.value) || 0;
    this._save();
  },

  async _saveDraft() {
    try {
      const res = await API.saveDraft({
        session: this._session,
        provider: this._session.data.provider,
        product: this._session.data.product,
        title: this._session.data.title || 'Untitled Design',
        price: this._session.data.price || 0
      });
      // Clear session on save
      this._session = { step: 0, data: {}, sessionId: null };
      localStorage.removeItem('wizard_session');
      App.showModal('✅ Draft Saved!', `
        <p>Your product draft has been saved successfully.</p>
        <div class="form-actions">
          <button class="btn" onclick="App.closeModal(); App.nav('dashboard')">Back to Dashboard</button>
          <button class="btn btn-primary" onclick="App.closeModal(); App.nav('listings')">View Drafts</button>
        </div>
      `);
    } catch(e) {
      // Fallback: save locally
      const drafts = JSON.parse(localStorage.getItem('wizard_drafts') || '[]');
      drafts.push({ ...this._session, savedAt: Date.now() });
      localStorage.setItem('wizard_drafts', JSON.stringify(drafts));
      this._session = { step: 0, data: {}, sessionId: null };
      localStorage.removeItem('wizard_session');
      App.showModal('✅ Draft Saved Locally!', `
        <p>Saved as a local draft. Connect Etsy API to save to cloud.</p>
        <div class="form-actions">
          <button class="btn" onclick="App.closeModal(); App.nav('dashboard')">Back to Dashboard</button>
          <button class="btn btn-primary" onclick="App.closeModal(); App.nav('listings')">View Drafts</button>
        </div>
      `);
    }
  },

  _genContent() {
    // Simple AI content generation demo
    const titles = [
      'Vintage Botanical Art Print — Set of 3',
      'Hand-Carved Wooden Spoon Set',
      'Minimalist Ceramic Vase — Stoneware',
      'Macrame Wall Hanging — Large',
      'Scented Soy Candle Trio — Lavender'
    ];
    const desc = 'Handcrafted with love and attention to detail. Made from high-quality, eco-friendly materials. Perfect for gifting or treating yourself. Each piece is unique and made to order.';
    const tags = 'handmade, gift, artisan, decor, unique';
    
    this._session.data.title = titles[Math.floor(Math.random() * titles.length)];
    this._session.data.description = desc;
    this._session.data.tags = tags;
    this._save();
    App.route();
  },

  _optTags() {
    this._session.data.tags = 'personalized, custom, handmade, artisan, gift, decor, unique, quality';
    this._save();
    App.route();
  },

  afterRender() {}
};
