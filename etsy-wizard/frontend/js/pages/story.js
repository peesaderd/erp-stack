/* ─── Story Coloring Book Page ─── */
const StoryPage = {
  templates: [],
  selectedTemplate: null,
  generating: false,

  async render() {
    return `
      <div class="page-header">
        <h1>📚 Story Coloring Book</h1>
        <p>AI Brain + AI Artist — สร้างหนังสือระบายสีแบบมีเรื่องราว</p>
      </div>

      <div class="story-section">
        <div class="section-card">
          <h3>📖 เลือกเรื่อง</h3>
          <div id="story-templates" class="template-grid">
            <div class="loading"><div class="spinner"></div><p>กำลังโหลด...</p></div>
          </div>
        </div>

        <div class="section-card" id="preview-section" style="display:none">
          <h3>🎨 ตัวอย่าง</h3>
          <div id="story-preview" class="preview-grid"></div>
        </div>

        <div class="section-card" id="generate-section" style="display:none">
          <h3>🚀 สร้างหนังสือ</h3>
          <div class="generate-controls">
            <button class="btn btn-primary" onclick="StoryPage.generate()" id="btn-generate">
              🎨 สร้างหนังสือระบายสี (6 หน้า)
            </button>
            <p class="note">💡 ใช้ AI Brain (Cloudflare Llama 3.3 70B) + AI Artist (FLUX Schnell) — ฟรี!</p>
          </div>
          <div id="generate-status" class="generate-status" style="display:none"></div>
        </div>
      </div>

      <div class="section-card" id="results-section" style="display:none">
        <h3>✅ ผลลัพธ์</h3>
        <div id="results-grid" class="results-grid"></div>
      </div>
    `;
  },

  async afterRender() {
    await this.loadTemplates();
  },

  async loadTemplates() {
    try {
      const res = await fetch('/api/pod/story/templates');
      this.templates = await res.json();
      this.renderTemplates();
    } catch (e) {
      document.getElementById('story-templates').innerHTML = 
        '<p class="error">❌ ไม่สามารถโหลด templates ได้</p>';
    }
  },

  renderTemplates() {
    const grid = document.getElementById('story-templates');
    grid.innerHTML = this.templates.map(t => `
      <div class="template-card ${this.selectedTemplate === t.key ? 'selected' : ''}" 
           onclick="StoryPage.selectTemplate('${t.key}')">
        <div class="template-icon">📚</div>
        <h4>${t.title}</h4>
        <p>${t.theme}</p>
        <span class="badge">${t.pages} หน้า</span>
      </div>
    `).join('');
  },

  async selectTemplate(key) {
    this.selectedTemplate = key;
    this.renderTemplates();

    // Show preview
    try {
      const res = await fetch(`/api/pod/story/${key}`);
      const story = await res.json();
      
      document.getElementById('preview-section').style.display = 'block';
      document.getElementById('generate-section').style.display = 'block';
      
      document.getElementById('story-preview').innerHTML = story.pages.map(p => `
        <div class="preview-card">
          <div class="page-num">${p.page_num}</div>
          <p>${p.scene}</p>
        </div>
      `).join('');
    } catch (e) {
      console.error(e);
    }
  },

  async generate() {
    if (!this.selectedTemplate || this.generating) return;
    
    this.generating = true;
    const btn = document.getElementById('btn-generate');
    const status = document.getElementById('generate-status');
    
    btn.disabled = true;
    btn.textContent = '⏳ กำลังสร้าง...';
    status.style.display = 'block';
    status.innerHTML = '<div class="loading"><div class="spinner"></div><p>กำลังสร้างหนังสือระบายสี...</p></div>';

    try {
      const res = await fetch('/api/pod/story/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ story_key: this.selectedTemplate })
      });
      
      const result = await res.json();
      
      if (result.error) {
        status.innerHTML = `<p class="error">❌ ${result.error}</p>`;
      } else {
        this.showResults(result);
        status.innerHTML = '<p class="success">✅ สร้างเสร็จแล้ว!</p>';
      }
    } catch (e) {
      status.innerHTML = `<p class="error">❌ เกิดข้อผิดพลาด: ${e.message}</p>`;
    } finally {
      this.generating = false;
      btn.disabled = false;
      btn.textContent = '🎨 สร้างหนังสือระบายสี (6 หน้า)';
    }
  },

  showResults(result) {
    const section = document.getElementById('results-section');
    const grid = document.getElementById('results-grid');
    
    section.style.display = 'block';
    
    grid.innerHTML = `
      <h4>${result.title}</h4>
      <div class="result-images">
        ${result.pages.filter(p => p.url).map(p => `
          <div class="result-card">
            <img src="${p.url}" alt="Page ${p.page_num}" loading="lazy">
            <p>${p.page_num}. ${p.scene}</p>
            <a href="${p.url}" target="_blank" class="btn btn-sm">เปิดดู</a>
          </div>
        `).join('')}
      </div>
    `;
    
    section.scrollIntoView({ behavior: 'smooth' });
  }
};
