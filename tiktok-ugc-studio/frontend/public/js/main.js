const API = window.location.origin + '/api/tiktok';
const SCRAPER = window.location.origin + '/api/tiktok';

let currentStep = 1;

/* ═══ Tab switching ═══ */
function switchTab(name) {
  // Persist tab in URL hash for PWA pull-to-refresh restore
  if (location.hash !== '#' + name) {
    location.hash = name;
  }
  
  // Always close mobile side drawer
  const nav = document.getElementById('sideNav');
  const overlay = document.getElementById('sideOverlay');
  if (nav) nav.classList.remove('open');
  if (overlay) overlay.classList.remove('open');

  // Highlight mobile bottom tab item
  document.querySelectorAll('.mobile-tab-item').forEach(item => {
    item.classList.remove('active');
    const onclickAttr = item.getAttribute('onclick');
    if (onclickAttr && onclickAttr.includes("'" + name + "'")) {
      item.classList.add('active');
    }
  });

  // Highlight side-nav and topbar-nav buttons
  document.querySelectorAll('[data-tab]').forEach(btn => {
    btn.classList.remove('active');
    if (btn.getAttribute('data-tab') === name) {
      btn.classList.add('active');
    }
  });

  // Switch display of page panels
  document.querySelectorAll('.page').forEach(page => {
    page.classList.remove('active');
    page.style.display = 'none';
  });

  const activePage = document.getElementById('page-' + name);
  if (activePage) {
    activePage.classList.add('active');
    activePage.style.display = 'block';
  }

  // Load specific tab data
  // Stop pipeline polling when leaving pipeline tab
  if (name !== 'pipeline') stopPipelinePoll();

  if (name === 'dashboard') loadDashboard();
  if (name === 'pipeline') {
    loadPipelineJobs();
    loadBatches();
  }
  if (name === 'products') loadAnalyzedProducts();
  if (name === 'assets') loadAssets();
  if (name === 'publisher') { loadPublisherVideos(); loadPublisherQueue(); }
  if (name === 'scout') {
    switchScoutSub('niche');
  }
  if (name === 'accounts') {
    switchAccountsSub('tiktok');
  }
  if (name === 'profile') {
    updateAuthUI();
  }
}

// --- Consolidated Sub-tab Switchers ---
function switchAccountsSub(sub) {
  document.querySelectorAll('#accountsSubTabs button').forEach(btn => {
    btn.classList.remove('active');
    if (btn.getAttribute('data-subtab') === sub) btn.classList.add('active');
  });
  document.querySelectorAll('.accounts-pane').forEach(p => p.style.display = 'none');
  document.getElementById('accounts-' + sub).style.display = 'block';
  if (sub === 'tiktok') loadAccounts();
  if (sub === 'social') pfmFetchAccounts();
}

function switchPublisherSub(sub) {
  // Publisher now uses single unified view — load everything
  loadPublisherVideos();
  loadPublisherQueue();
}

function switchScoutSub(sub) {
  document.querySelectorAll('#scoutSubTabs button').forEach(btn => {
    btn.classList.remove('active');
    if (btn.getAttribute('data-subtab') === sub) btn.classList.add('active');
  });
  document.querySelectorAll('.scout-pane').forEach(p => p.style.display = 'none');
  if (sub === 'niche') {
    document.getElementById('scout-niche-pane').style.display = 'block';
    scoutRefreshNiches();
  } else if (sub === 'targets') {
    document.getElementById('scout-targets').style.display = 'block';
    renderSocialTargets();
  } else if (sub === 'schedule') {
    document.getElementById('scout-schedule').style.display = 'block';
    renderSchedule();
  }
}

// --- Profile Local Auth Tab Switcher ---
function toggleLocalAuthTab(tab) {
  document.querySelectorAll('#profileAuthTabs button').forEach(btn => btn.classList.remove('active'));
  document.getElementById('local-login-form').style.display = tab === 'login' ? 'block' : 'none';
  document.getElementById('local-register-form').style.display = tab === 'register' ? 'block' : 'none';
  
  if (tab === 'login') {
    document.getElementById('btn-login-tab').classList.add('active');
  } else {
    document.getElementById('btn-register-tab').classList.add('active');
  }
}

// --- Profile Auth Actions ---
async function profileLocalLogin() {
  const email = document.getElementById('profile-login-email').value.trim();
  const password = document.getElementById('profile-login-password').value;
  const result = document.getElementById('profile-login-res');
  
  if (!email || !password) {
    result.textContent = 'Please fill in all fields';
    result.style.color = 'var(--color-red-400)';
    return;
  }
  
  result.textContent = '⚡ Signing in...';
  result.style.color = 'var(--text-secondary)';
  
  try {
    const r = await fetch(window.location.origin + '/api/auth/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email, password})
    });
    const d = await r.json();
    if (d.ok && d.token) {
      localStorage.setItem('tus_token', d.token);
      localStorage.setItem('tus_user', JSON.stringify(d.user || {email: email, name: (d.user?.name || email.split('@')[0])}));
      updateAuthUI();
      showToast('Logged in successfully', 'success');
    } else {
      result.textContent = d.message || d.error || 'Login failed';
      result.style.color = 'var(--color-red-400)';
    }
  } catch(e) {
    result.textContent = 'Error: ' + e.message;
    result.style.color = 'var(--color-red-400)';
  }
}

async function profileLocalRegister() {
  const name = document.getElementById('profile-reg-name').value.trim();
  const email = document.getElementById('profile-reg-email').value.trim();
  const password = document.getElementById('profile-reg-password').value;
  const result = document.getElementById('profile-reg-res');
  
  if (!name || !email || !password) {
    result.textContent = 'Please fill in all fields';
    result.style.color = 'var(--color-red-400)';
    return;
  }
  
  result.textContent = '⚡ Creating account...';
  result.style.color = 'var(--text-secondary)';
  
  try {
    const r = await fetch(window.location.origin + '/api/auth/register', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, email, password})
    });
    const d = await r.json();
    if (d.ok && d.token) {
      localStorage.setItem('tus_token', d.token);
      localStorage.setItem('tus_user', JSON.stringify(d.user || {name: name, email: email}));
      updateAuthUI();
      showToast('Account created successfully', 'success');
    } else {
      result.textContent = d.message || d.error || 'Registration failed';
      result.style.color = 'var(--color-red-400)';
    }
  } catch(e) {
    result.textContent = 'Error: ' + e.message;
    result.style.color = 'var(--color-red-400)';
  }
}

/* ═══ Toast ═══ */
function showToast(msg, type='info') {
  const el = document.createElement('div'); el.className = 'toast '+type; el.textContent = msg;
  document.body.appendChild(el);
  const duration = type === 'error' ? 5000 : type === 'info' ? 4000 : 3500;
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(() => el.remove(),300); }, duration);
}

/* ═══ Button loading state helper ═══ */
function setButtonLoading(btnId, loading, originalText) {
const btn = document.getElementById(btnId);
if (!btn) return;
if (loading) {
    btn._origText = originalText || btn.textContent;
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-spinner"></span> กำลังทำงาน...';
    btn.style.opacity = '0.7';
  } else {
    btn.disabled = false;
    btn.innerHTML = btn._origText || originalText || 'สร้าง';
    btn.style.opacity = '1';
  }
}

  /* ═══ Loading indicator ═══ */
function setLoading(elId, loading) {
  const el = document.getElementById(elId);
  if (!el) return;
  if (loading) el.innerHTML = '<div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line" style="width:60%"></div>';
}

/* Button loading state */
function btnLoading(btnId, loading, label) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  if (loading) {
    btn.disabled = true;
    btn.classList.add('loading');
    btn.dataset.label = btn.innerHTML;
    btn.innerHTML = '<span class="btn-spinner"></span>' + (label || 'กำลังดำเนินการ...');
  } else {
    btn.disabled = false;
    btn.classList.remove('loading');
    if (btn.dataset.label) btn.innerHTML = btn.dataset.label;
  }
}

/* ═══ Dashboard ═══ */
async function loadDashboard() {
  setLoading('dashRecentJobs', true);
  const creditsEl = document.getElementById('dashCredits');
  const statsVideo = document.getElementById('dashStatVideos');
  const statsProd = document.getElementById('dashStatProducts');
  const statsJobs = document.getElementById('dashStatJobs');
  const statsCredits = document.getElementById('dashStatCredits');
  const jobsEl = document.getElementById('dashRecentJobs');
  try {
    const res = await fetch(API + '/dashboard/summary');
    if (!res.ok) throw new Error('API error');
    const data = await res.json();
    if (!data.success) throw new Error('Not successful');
    // Update credit balance
    const bal = data.credit_balance || 0;
    if (creditsEl) creditsEl.textContent = '฿' + bal.toLocaleString('th-TH', {minimumFractionDigits:2,maximumFractionDigits:2});
    // Update stats
    if (statsVideo) { statsVideo.textContent = data.total_videos || 0; animateValue(statsVideo); }
    if (statsProd) { statsProd.textContent = data.total_products || 0; animateValue(statsProd); }
    if (statsJobs) { statsJobs.textContent = (data.recent_jobs || []).length; animateValue(statsJobs); }
    if (statsCredits) statsCredits.textContent = '฿' + bal.toLocaleString('th-TH', {minimumFractionDigits:0});
    // Recent jobs
    const jobs = data.recent_jobs || [];
    if (!jobs.length) {
      jobsEl.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:16px">\u{1F4AD} No recent jobs. Start by generating a video!</div>';
    } else {
      jobsEl.innerHTML = jobs.slice(0,10).map(j => {
        const badgeClass = j.status === 'completed' ? 'badge-green' : j.status === 'processing' || j.status === 'in_progress' ? 'badge-indigo' : j.status === 'failed' ? 'badge-red' : 'badge-gray';
        const timeAgo = j.created_at ? timeSince(j.created_at) : '';
        return `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border-secondary)">
          <div style="flex:1;min-width:0">
            <div class="text-sm" style="font-weight:500">${j.id || 'Job'}</div>
            <div class="text-xs text-secondary" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${j.product_url ? j.product_url.slice(0,50) : timeAgo}</div>
          </div>
          <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
            <span class="text-xs text-secondary">${timeAgo}</span>
            <span class="badge ${badgeClass}">${j.status || 'pending'}</span>
          </div>
        </div>`;
      }).join('');
    }
    // Track event (fire-and-forget, first load only)
    if (!window._dashTracked) {
      window._dashTracked = true;
      fetch(API + '/dashboard/track-event', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({event: 'dashboard_view', metadata: {}})
      }).catch(() => {});
    }
  } catch(e) {
    if (jobsEl) jobsEl.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:16px">❌ Failed to load: ' + e.message + '</div>';
  }
}

function timeSince(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  // DB stores UTC, append Z so browser treats it as UTC
  const utcStr = dateStr.includes('Z') ? dateStr : dateStr.replace(' ', 'T') + 'Z';
  const d = new Date(utcStr);
  const sec = Math.floor((now - d) / 1000);
  if (sec < 60) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return min + 'm ago';
  const hr = Math.floor(min / 60);
  if (hr < 24) return hr + 'h ago';
  const day = Math.floor(hr / 24);
  return day + 'd ago';
}

function animateValue(el) {
  el.style.transition = 'transform .2s ease';
  el.style.transform = 'scale(1.15)';
  setTimeout(() => { el.style.transform = 'scale(1)'; }, 200);
}

/* ═══ Recent jobs (legacy) ═══ */
async function loadRecentJobs() {
  await loadDashboard();
}

/* ═══ Content wizard ═══ */
function goContentStep(step) {
  currentStep = step;
  document.querySelectorAll('.step').forEach(s => s.classList.remove('active','done'));
  document.querySelectorAll('.step-content').forEach(s => s.classList.remove('active'));
  for (let i = 1; i < step; i++) document.querySelector(`.step[data-step="${i}"]`)?.classList.add('done');
  document.querySelector(`.step[data-step="${step}"]`)?.classList.add('active');
  document.getElementById('contentStep'+step)?.classList.add('active');
}

async function autoGenerateAll() {
  // One-click: background pipeline — runs server-side via /video/generate (can close tab!)
  const url = document.getElementById('productUrl').value;
  const title = document.getElementById('productTitle').value.trim();
  const details = document.getElementById('productDetails').value.trim();
  const style = sessionStorage.getItem('selectedStyle');
  if (!url && !title && !details) { showToast('ใส่ชื่อสินค้าหรือ URL ก่อน','error'); return; }

  const dur = parseInt(sessionStorage.getItem('selectedDuration')) || 8;
  
  showLoadingOverlay('🚀 กำลังเริ่ม Pipeline ฝั่ง Server...');
  setButtonLoading('autoGenBtn', true);
  try {
    const imageUrl = uploadedImages.product || '';
    
    // /video/generate runs the FULL pipeline server-side (script+prompt+image+video)
    // Already runs as async task via asyncio.create_task — no browser needed after this call!
    const res = await fetch(window.location.origin + '/api/tiktok/video/generate', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        product_title: title || url?.split('/').pop() || '',
        product_url: url,
        product_description: details,
        product_image: imageUrl,
        hook: document.getElementById('scriptHook')?.value || '',
        value: document.getElementById('scriptValue')?.value || '',
        cta: document.getElementById('scriptCta')?.value || '',
        duration: dur,
        ugc_style: style,
        content_type: sessionStorage.getItem('selectedContentType') || 'affiliate',
        aspect_ratio: sessionStorage.getItem('aspectRatio') || '9:16',
        negative_prompt: document.getElementById('negativePrompt')?.value?.trim() || 'text, subtitle, caption, emoji, icon, logo, watermark, UI, overlay, graphic',
        recipe: document.querySelector('#recipePicker .style-card.selected')?.getAttribute('data-recipe') || undefined,
        country: document.getElementById('countrySelect')?.value || 'thai',
        gender: document.getElementById('genderSelect')?.value || 'female',
      })
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error('Pipeline start failed: ' + (errText || res.statusText));
    }
    const data = await res.json();
    const jobId = data.job_id || '';
    
    setButtonLoading('autoGenBtn', false);
    hideLoadingOverlay();
    
    showToast('✅ Pipeline เริ่มทำงานแล้ว! Job ID: ' + jobId + ' (ออกจาก page หรือปิด browser ได้เลย)', 'success');
    sessionStorage.setItem('lastPipelineJobId', jobId);
    
    // Redirect to Pipeline tab to monitor — auto-refresh every 8s
    setTimeout(function() {
      switchTab('pipeline');
      loadPipelineJobs();
      startPipelinePoll(jobId);
    }, 1500);
    
  } catch(e) {
    setButtonLoading('autoGenBtn', false);
    hideLoadingOverlay();
    showToast('❌ ' + e.message, 'error');
    console.error('autoGenerateAll error:', e);
  }
}

function showLoadingOverlay(msg) {
  const o = document.getElementById('loadingOverlay');
  if(!o) return;
  document.getElementById('loadingText').textContent = msg;
  o.classList.add('open');
}
function hideLoadingOverlay() {
  const o = document.getElementById('loadingOverlay');
  if(o) o.classList.remove('open');
}

// ─── Auto Pipeline ─────────────────────────────────────────

// Polling state for pipeline job completion auto-refresh
var _pipelinePollInterval = null;
var _pipelinePollJobId = null;

function startPipelinePoll(jobId) {
  _pipelinePollJobId = jobId;
  stopPipelinePoll();
  _pipelinePollInterval = setInterval(function() {
    if (!_pipelinePollJobId) { stopPipelinePoll(); return; }
    var el = document.getElementById('pipelineJobList');
    if (!el || el.offsetParent === null) { stopPipelinePoll(); return; } // tab not visible
    loadPipelineJobs().then(function() {
      // Check if job completed
      fetch(API + '/pipeline/list?limit=50').then(function(r) { return r.json(); }).then(function(d) {
        var jobs = d.jobs || [];
        var found = jobs.find(function(j) { return j.job_id === _pipelinePollJobId; });
        if (found) {
          if (found.status === 'completed' || found.status === 'success') {
            stopPipelinePoll();
            showToast('✅ Pipeline เสร็จแล้ว! Job: ' + _pipelinePollJobId.slice(0,12) + '...', 'success');
          } else if (found.status === 'error' || found.status === 'failed') {
            stopPipelinePoll();
            showToast('❌ Pipeline failed: ' + _pipelinePollJobId.slice(0,12) + '...', 'error');
          }
        }
      }).catch(function(){});
    }).catch(function(){});
  }, 15000); // every 15 seconds (reduced from 8s to reduce flicker)
}

function stopPipelinePoll() {
  if (_pipelinePollInterval) {
    clearInterval(_pipelinePollInterval);
    _pipelinePollInterval = null;
  }
}

function selectAutoMode(el) {
  document.querySelectorAll('.auto-pipeline-modes .mode-card').forEach(function(c){ 
    c.classList.remove('selected');
    c.style.borderColor = 'var(--border-primary)';
    c.style.background = 'var(--bg-secondary)';
  });
  el.classList.add('selected');
  el.style.borderColor = 'var(--accent-purple)';
  el.style.background = 'rgba(139,92,246,0.08)';
  localStorage.setItem('autoPipelineMode', el.dataset.mode);
}

function saveAutoPipelineSettings() {
  var settings = {
    mode: localStorage.getItem('autoPipelineMode') || 'manual',
    platforms: [],
    dailyCount: document.getElementById('autoDailyCount')?.value || 3,
    postTime: document.getElementById('autoPostTime')?.value || 'random',
    productSource: document.getElementById('autoProductSource')?.value || 'all',
  };
  document.querySelectorAll('#autoPfmPlatforms input[type="checkbox"]:checked').forEach(function(c){
    settings.platforms.push(c.value);
  });
  localStorage.setItem('autoPipelineSettings', JSON.stringify(settings));
  showToast('💾 Auto Pipeline settings saved!', 'success');
}

async function startAutoPipelineNow() {
  saveAutoPipelineSettings();
  var settings = JSON.parse(localStorage.getItem('autoPipelineSettings') || '{}');
  if (!settings.platforms || !settings.platforms.length) { showToast('กรุณาเลือก platform', 'error'); return; }
  
  var btn = document.getElementById('startAutoPipeline');
  var status = document.getElementById('autoPipelineStatus');
  btn.disabled = true;
  btn.textContent = '⏳ Running...';
  status.textContent = 'กำลังดึงข้อมูลสินค้า...';
  
  try {
    // Fetch products from DB
    var r = await fetch(API + '/products/list?limit=50&preset=all');
    var d = await r.json();
    var products = d.products || [];
    
    if (!products.length) { showToast('ไม่มีสินค้าในระบบ', 'error'); btn.disabled=false; btn.textContent='▶️ Start Auto Pipeline'; return; }
    
    status.textContent = 'พบสินค้า ' + products.length + ' รายการ กำลังเลือก...';
    
    // Filter by source
    var filtered = products;
    if (settings.productSource === 'untouched') {
      filtered = products.filter(function(p){ return p.tus_status === 'pending' || !p.tus_status; });
    } else if (settings.productSource === 'retry') {
      filtered = products.filter(function(p){ return p.tus_status === 'failed' || p.tus_status === 'running'; });
    }
    
    if (!filtered.length) { showToast('ไม่พบสินค้าที่ตรงเงื่อนไข', 'error'); btn.disabled=false; btn.textContent='▶️ Start Auto Pipeline'; return; }
    
    status.textContent = 'เลือก ' + filtered[0].title.slice(0,50) + '... กำลังส่งเข้า Pipeline';
    
    // Run pipeline for first product
    var title = filtered[0].title || '';
    var desc = filtered[0].description || filtered[0].title_th || '';
    var images = filtered[0].images || [];
    
    // Fill wizard fields with this product data
    document.getElementById('productTitle').value = title;
    document.getElementById('productDetails').value = desc;
    var prodId = filtered[0].product_id;
    var prodImgUrl = images.length ? images[0] : (prodId ? "/ugc/static/product_images/" + prodId + ".jpg" : null);
    if (prodImgUrl) {
      uploadedImages.product = prodImgUrl.startsWith("http") ? prodImgUrl : window.location.origin + prodImgUrl;
      document.getElementById('productImgPlaceholder').innerHTML = '<img src='+uploadedImages.product+' style="max-width:100%;max-height:120px;border-radius:8px">';
    }

    showToast('✅ Selected: ' + title.slice(0,40), 'success');
    
    if (settings.mode === 'manual') {
      status.textContent = '✅ เลือกสินค้าแล้ว — กรุณากด Auto Generate All หรือ Generate Video';
      showToast('🎯 Manual mode: กรอกข้อมูลแล้ว พร้อมให้สร้างวิดีโอ!', 'success');
      return;
    }
    
    // Auto Queue or Full Auto: auto-generate
    status.textContent = '⏳ Auto generating...';
    await autoGenerateAll();
    
    status.textContent = '✅ วิดีโอสร้างเสร็จ!';
    
    if (settings.mode === 'full-auto') {
      // Post directly
      status.textContent = '⏳ Auto posting...';
      showToast('🚀 Full Auto: กำลังโพสต์...', 'info');
      // Generate AI content first
      var genR = await fetch(API + '/publisher/generate-content', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({product_name: title, description: desc, tags: [], platform: settings.platforms[0]})
      });
      var genData = await genR.json();
      
      // Find most recent pipeline job
      var pipeR = await fetch(API + '/pipeline/list');
      var pipeD = await pipeR.json();
      var jobs = pipeD.jobs || [];
      var latestJob = jobs.filter(function(j){ return j.status === 'completed' || j.status === 'running'; })[0];
      
      if (latestJob) {
        for (var i = 0; i < settings.platforms.length; i++) {
          await pfmFetch('/publisher/enqueue', {
            method: 'POST', body: JSON.stringify({
              video_path: latestJob.video_url || '',
              title: genData.title || title,
              description: genData.description || desc,
              caption: title,
              hashtags: genData.hashtags || [],
              platform: settings.platforms[i],
              job_id: latestJob.job_id,
              schedule_at: new Date(Date.now() + 30000).toISOString()
            })
          });
        }
        status.textContent = '✅ Auto posted to ' + settings.platforms.length + ' platforms!';
        showToast('🚀 Auto posted!', 'success');
      }
    } else {
      showToast('⏳ Auto Queue: วิดีโออยู่ในคิว โปรดตรวจสอบที่ Publisher', 'success');
    }
    
    loadPublisherQueue();
  } catch(e) {
    showToast('Auto Pipeline Error: ' + e.message, 'error');
    status.textContent = '❌ Error: ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = '▶️ Start Auto Pipeline';
  }
}

async function generateScript() {
  const url = document.getElementById('productUrl').value;
  const title = document.getElementById('productTitle').value.trim();
  const details = document.getElementById('productDetails').value.trim();
  const style = sessionStorage.getItem('selectedStyle');
  if (!url && !title && !details) { showToast('ใส่ชื่อสินค้าหรือ URL ก่อน','error'); return; }

  setButtonLoading('genScriptBtn', true);
  try {
    const body = { ugc_style: style, duration: sessionStorage.getItem('selectedDuration') || '8' };
    if (url) body.product_url = url;
    if (title) body.product_title = title;
    if (details) body.product_details = details;
    if (!body.product_name && title) body.product_name = title;
    if (!body.product_name && url) body.product_name = url.split('/').pop() || url;

    const res = await fetch(window.location.origin + '/api/tiktok/ugc/scripts/generate', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error('Generate failed');
    const data = await res.json();

    // Keep existing values if API returns empty (don't clear pre-filled data)
    if (data.hook) document.getElementById('scriptHook').value = data.hook;
    if (data.value_proposition) document.getElementById('scriptValue').value = data.value_proposition;
    if (data.cta) document.getElementById('scriptCta').value = data.cta;
    if (data.hashtags) {
      const tagField = document.getElementById('scriptHashtags');
      if (tagField) tagField.value = Array.isArray(data.hashtags) ? data.hashtags.join(', ') : data.hashtags;
    }
    localStorage.setItem('lastScript', JSON.stringify(data));
    setButtonLoading('genScriptBtn', false);
    goContentStep(2);
  } catch(e) {
    setButtonLoading('genScriptBtn', false);
    showToast('Failed: '+e.message,'error');
  }
}

function goToStep3() {
  // Populate summary from Step 2 data
  document.getElementById('step3Hook').textContent = document.getElementById('scriptHook').value || '-';
  document.getElementById('step3Value').textContent = document.getElementById('scriptValue').value || '-';
  document.getElementById('step3Cta').textContent = document.getElementById('scriptCta').value || '-';
  
  const duration = sessionStorage.getItem('selectedDuration') || '8';
  document.getElementById('step3Duration').textContent = duration + ' วิ' + (duration >= 15 ? ' (1 scene)' : ' (1 scene)');
  
  const lastScript = JSON.parse(localStorage.getItem('lastScript') || '{}');
  document.getElementById('step3Scene').textContent = lastScript.scene || lastScript.scenes?.join(', ') || lastScript.script?.scene || 'UGC ถือสินค้าหน้าฉากหลังเรียบ';
  document.getElementById('step3Voice').textContent = lastScript.voice || lastScript.voice_style || lastScript.script?.voice || 'เสียงไทยหญิง อายุ 20-30 น้ำเสียงเป็นกันเอง';
  document.getElementById('step3Prompt').textContent = (lastScript.prompt || lastScript.video_prompt || lastScript.script?.prompt || '').length > 5 ? (lastScript.prompt || lastScript.video_prompt || lastScript.script?.prompt) : '- กำลัง generate (ลองใหม่)...';
  document.getElementById('step3Mood').textContent = lastScript.mood || lastScript.mood_tone || lastScript.script?.mood || 'เป็นกันเอง, เชื่อถือได้, อุ่นใจ';
  // Hashtags from prompt-builder analysis (returned by script gen endpoint)
  const rawTags = lastScript.hashtags || lastScript.script?.hashtags || [];
  const tagStr = Array.isArray(rawTags) ? rawTags.join(', ') : (typeof rawTags === 'string' ? rawTags : '');
  document.getElementById('step3Hashtags').textContent = tagStr || '-';

  // Show uploaded product image
  const productImg = document.getElementById('productImgPreview') || document.querySelector('#productImgZone img');
  const step3Img = document.getElementById('step3ProductImg');
  const noImg = document.getElementById('step3NoImg');
  if (productImg && productImg.src) {
    step3Img.src = productImg.src;
    step3Img.style.display = 'inline';
    noImg.style.display = 'none';
  } else {
    step3Img.style.display = 'none';
    noImg.style.display = 'block';
  }
  
  goContentStep(3);
}

async function generateImageFromStep3() {
  setButtonLoading('genImageBtn', true);
  const productName = document.getElementById('productTitle').value || document.getElementById('productName').value || 'สินค้า';
  const productDetails = document.getElementById('productDetails').value || '';
  const style = sessionStorage.getItem('selectedStyle');
  const productImageUrl = uploadedImages.product || '';
  
  try {
    // Use enhanced prompt builder — dynamic gender, setting, lighting based on product
    const builder = await fetch(window.location.origin + '/api/tiktok/ugc/images/build-prompt', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        product_name: productName,
        description: productDetails,
        ugc_style: style,
        use_mistral: false
      })
    });
    if (!builder.ok) throw new Error('Build prompt failed');
    const builderData = await builder.json();
    const prompt = builderData.prompt || builderData.data?.prompt || '';
    if (!prompt) throw new Error('No prompt built');
    
    const res = await fetch(window.location.origin + '/api/tiktok/ugc/images/generate', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({prompt, count: 1, image_url: productImageUrl})
    });
    if (!res.ok) throw new Error('API error');
    const data = await res.json();
    const images = data.data?.data?.images || data.data?.images || data.images || [];
    let imgUrl = images[0]?.url || '';
    if (imgUrl.startsWith('http://localhost:8110/storage/images/')) {
      imgUrl = window.location.origin + '/storage/images/' + imgUrl.split('/').pop();
    }
    if (!imgUrl) throw new Error('No image');
    const modelImg = document.getElementById('modelImgPreview');
    if (modelImg) { modelImg.src = imgUrl; modelImg.style.display = 'block'; }
    const step3Img = document.getElementById('step3ProductImg');
    if (step3Img) { step3Img.src = imgUrl; step3Img.style.display = 'inline'; document.getElementById('step3NoImg').style.display = 'none'; }
    setButtonLoading('genImageBtn', false);
    showToast('✅ รูปพร้อมใช้','success');
    goContentStep(4);
  } catch(e) {
    setButtonLoading('genImageBtn', false);
    showToast('❌ สร้างรูปไม่สำเร็จ: ' + e.message,'error');
  }
}

// ── Recipe Templates ─────────────────────────────────────────────
let _recipes = [];

async function loadRecipes() {
  const container = document.getElementById('recipePicker');
  if (!container) return;
  try {
    const r = await fetch(API + '/pipeline/recipes');
    const d = await r.json();
    _recipes = d.recipes || [];
    container.innerHTML = _recipes.map(r => {
      const isSelected = r.name === 'gadget';
      return '<div class="style-card' + (isSelected ? ' selected' : '') + '" data-recipe="' + r.name + '" onclick="selectRecipe(\'' + r.name + '\')" title="' + r.description + '">'
        + '<div style="font-size:22px;line-height:1.2">' + r.label.split(' ')[0] + '</div>'
        + '<div class="font-medium" style="font-size:11px;line-height:1.2;margin-top:4px">' + r.label.replace(/^[^\s]+\s/, '') + '</div>'
        + '<div class="text-xs text-secondary" style="font-size:9px;line-height:1.2;margin-top:2px">' + r.description + '</div>'
        + '</div>';
    }).join('');
  } catch(e) { /* silent */ }
}

function selectRecipe(name) {
  document.querySelectorAll('#recipePicker .style-card').forEach(c => c.classList.remove('selected'));
  const card = document.querySelector('#recipePicker [data-recipe="' + name + '"]');
  if (card) card.classList.add('selected');

  const recipe = _recipes.find(r => r.name === name);
  if (!recipe) return;

  // Apply recipe settings to the form
  // UGC Style
  const styleMap = {
    'product_usage': ['📱', 'Product Usage — สาธิตการใช้'],
    'holding_product': ['🤳', 'Holding Product — ถือสินค้าพูด'],
    'ugc_review': ['⭐', 'UGC Review — รีวิวสินค้า'],
    'talking_head': ['🎤', 'Talking Head — พูดหน้ากล้อง'],
    'product_demo': ['📦', 'Product Demo — โชว์สินค้า ไม่มีคน'],
    'fashion_lookbook': ['👗', 'Fashion Lookbook — แฟชั่นสายชิค หรูหรา'],
  };
  const s = styleMap[recipe.ugc_style] || ['📦', 'Product Demo'];
  document.getElementById('selectedStyleIcon').textContent = s[0];
  document.getElementById('selectedStyleLabel').textContent = s[1];
  sessionStorage.setItem('selectedStyle', recipe.ugc_style);
  // Sync UGC dropdown highlight to match recipe
  document.querySelectorAll('#styleModalGrid .style-card').forEach(c => c.classList.remove('selected'));
  const modalCard = document.querySelector('#styleModalGrid [data-style="' + recipe.ugc_style + '"]');
  if (modalCard) modalCard.classList.add('selected');

  // Duration
  const durChips = document.querySelectorAll('.duration-chip');
  durChips.forEach(c => {
    const val = parseInt(c.getAttribute('onclick')?.match(/'?(\d+)'?\)/)?.[1] || '8');
    if (val === recipe.duration) c.classList.add('selected');
    else c.classList.remove('selected');
  });
  sessionStorage.setItem('selectedDuration', String(recipe.duration));

}

function selectStyle(el, style) {
  document.querySelectorAll('.style-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  sessionStorage.setItem('selectedStyle', style);
}

function selectStyleFromModal(el, style) {
  document.querySelectorAll('#styleModalGrid .style-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  sessionStorage.setItem('selectedStyle', style);
  const icon = el.querySelector('.style-card-emoji')?.textContent || '🤳';
  const label = el.querySelector('.font-medium')?.textContent || style;
  const sub = el.querySelector('.text-xs')?.textContent || '';
  document.getElementById('selectedStyleIcon').textContent = icon;
  document.getElementById('selectedStyleLabel').textContent = label + ' — ' + sub;
  document.getElementById('styleModal').classList.remove('open');
  // Deselect recipe card — user is doing custom style, not following a preset
  document.querySelectorAll('#recipePicker .style-card').forEach(c => c.classList.remove('selected'));
}

function selectDuration(el, dur) {
  document.querySelectorAll('.duration-chip').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  sessionStorage.setItem('selectedDuration', dur);
  [document.getElementById('durationHint'), document.getElementById('durationHint4')].forEach(h => {
    if (h) h.textContent = dur == 15 ? '🎬 15 วิ = 1 scene ต้นทุน ~$0.15' : '8 วิ = 1 scene ต้นทุน ~$0.09';
  });
  const costHint = document.getElementById('costHint');
  if (costHint) costHint.textContent = dur == 15 ? 'ต้นทุน ~$0.15 (1 scene)' : 'ต้นทุน ~$0.09/clip';
}

/* ═══ Image Upload Handlers ═══ */
let uploadedImages = {}; // { product: dataUrl, model: dataUrl }

function handleImageUpload(input, type) {
  const file = input.files[0];
  if (!file) return;
  if (!file.type.startsWith('image/')) { showToast('เลือกไฟล์รูปภาพเท่านั้น','error'); return; }
  // Max 10MB
  if (file.size > 10 * 1024 * 1024) { showToast('รูปต้องไม่เกิน 10MB','error'); return; }

  const reader = new FileReader();
  reader.onload = function(e) {
    const dataUrl = e.target.result;
    uploadedImages[type] = dataUrl;

    const zone = document.getElementById(type + 'ImgZone');
    const placeholder = document.getElementById(type + 'ImgPlaceholder');
    zone.classList.add('has-image');

    // Replace placeholder with preview + remove button
    placeholder.innerHTML = '' +
      '<img class="preview" src="' + dataUrl + '" alt="' + type + '">' +
      '<button class="remove-img" onclick="event.stopPropagation();removeImage(\'' + type + '\')">✕</button>';

    showToast('อัปโหลด ' + (type === 'product' ? 'รูปสินค้า' : 'รูป Model') + ' แล้ว','success');
  };
  reader.readAsDataURL(file);
}

function removeImage(type) {
  delete uploadedImages[type];
  const zone = document.getElementById(type + 'ImgZone');
  const placeholder = document.getElementById(type + 'ImgPlaceholder');
  zone.classList.remove('has-image');
  placeholder.innerHTML = '' +
    '<div class="upload-icon">' + (type === 'product' ? '📷' : '🧑') + '</div>' +
    '<div class="upload-label">' + (type === 'product' ? 'รูปสินค้า' : 'รูป Model / คน') + '</div>' +
    '<div class="upload-hint">' + (type === 'product' ? 'คลิกเพื่ออัปโหลด' : '(optional)') + '</div>';
  // Reset file input
  const input = document.getElementById(type + 'ImgInput');
  if (input) input.value = '';
}

function selectRatio(el, ratio) {
  document.querySelectorAll('.ratio-chip').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  sessionStorage.setItem('aspectRatio', ratio);
}

function toggleAdvanced() {
  const t = document.getElementById('advancedToggle');
  const s = document.getElementById('advancedSection');
  t.classList.toggle('on');
  s.style.display = t.classList.contains('on') ? 'block' : 'none';
}

async function startGeneration() {
  const hook = document.getElementById('scriptHook').value;
  const value = document.getElementById('scriptValue').value;
  const cta = document.getElementById('scriptCta').value;
  if (!hook) { showToast('กรุณาใส่ Hook ก่อน','error'); return; }

  const btn = document.getElementById('genBtn');
  const progress = document.getElementById('generationProgress');
  btn.disabled = true; btn.style.opacity = '.6';
  progress.style.display = 'block';
  document.getElementById('progressText').textContent = '⚡ กำลังสร้างวิดีโอ...';
  document.getElementById('progressBar').style.width = '20%';

  const duration = parseInt(sessionStorage.getItem('selectedDuration') || '8');
  const totalScenes = duration >= 15 ? 2 : 1;

  try {
    const basePrompt = hook + '. ' + value + (cta ? '. ' + cta : '');
    const title = document.getElementById('productTitle').value.trim();
    const imageUrl = uploadedImages.product || null;
    
      // Single request — backend handles 8s or 15s (1 scene)
    const label = duration + ' วิ';
    document.getElementById('progressText').textContent = '🎬 กำลังสร้างวิดีโอ ' + label + '...';
    document.getElementById('progressBar').style.width = '40%';
    
    const body = {
      product_title: title || undefined,
      product_url: document.getElementById('productUrl').value || undefined,
      product_image: imageUrl,
      hook: hook,
      value: value,
      cta: cta,
      content_type: sessionStorage.getItem('selectedContentType') || 'affiliate',
      ugc_style: sessionStorage.getItem('selectedStyle'),
      aspect_ratio: sessionStorage.getItem('aspectRatio') || '9:16',
      duration: duration,
      negative_prompt: document.getElementById('negativePrompt').value.trim() || undefined,
      recipe: document.querySelector('#recipePicker .style-card.selected')?.getAttribute('data-recipe') || undefined,
      country: document.getElementById('countrySelect')?.value || 'thai',
      gender: document.getElementById('genderSelect')?.value || 'female',
    };
    
    const res = await fetch(API + '/video/generate', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error('Generation failed');
    const data = await res.json();
    const jobId = data.job_id;
    document.getElementById('progressText').textContent = '⏳ กำลังสร้างวิดีโอ ' + label + ' (Pipeline)...';
    document.getElementById('progressBar').style.width = '60%';

    // Poll pipeline status
    let attempts = 0;
    const pollJob = async () => {
      while (attempts < 60) {
        attempts++;
        await new Promise(r => setTimeout(r, 5000));
        try {
          const sres = await fetch(API + '/video/status/' + jobId);
          const sdata = await sres.json();
          if (sdata.status === 'completed') {
            document.getElementById('progressBar').style.width = '100%';
            document.getElementById('progressText').textContent = '✅ วิดีโอ ' + label + 'พร้อมแล้ว! ต้นทุน ~$' + (sdata.cost || '0.13');
            showToast('วิดีโอ ' + label + 'สร้างเสร็จ ✅','success');
            setTimeout(() => loadPipeline(), 1000);
            return;
          } else if (sdata.status === 'failed') {
            throw new Error(sdata.error || 'Pipeline failed');
          }
        } catch(e) {
          if (attempts > 5) throw e;
        }
      }
      throw new Error('Timeout waiting for video');
    };
    await pollJob();
  } catch(e) {
    document.getElementById('progressText').textContent = '❌ ล้มเหลว: ' + e.message;
    document.getElementById('progressBar').style.width = '0%';
    throw e;
  } finally {
    btn.disabled = false; btn.style.opacity = '1';
  }
}

/* ═══ Pipeline ═══ */
/* ═══ Pipeline Monitor ═══ */
let currentDetailJobId = '';

function statusBadgeClass(status) {
  const map = { 'completed': 'badge-green', 'running': 'badge-blue', 'pending': 'badge', 'error': 'badge-red', 'cancelled': 'badge', 'restarted': 'badge-yellow', 'failed': 'badge-red' };
  return map[status] || 'badge';
}

function statusIcon(status) {
  const map = { 'completed': '✅', 'running': '⏳', 'pending': '⏸', 'error': '❌', 'cancelled': '🚫', 'restarted': '🔄', 'failed': '❌' };
  return map[status] || '❓';
}

function stepStatusIcon(status) {
  const map = { 'success': '✅', 'processing': '⏳', 'pending': '⏸', 'error': '❌' };
  return map[status] || '❓';
}
function getStepProgressHtml(job) {
  const stepsMap = [
    { num: 1, name: 'Analyze Product' },
    { num: 2, name: 'Load Recipe' },
    { num: 3, name: 'Generate Script' },
    { num: 4, name: 'Build Image Prompt' },
    { num: 5, name: 'Generate Image' },
    { num: 6, name: 'Build Video Prompts' },
    { num: 7, name: 'TTS Voice Gen' },
    { num: 8, name: 'Wan 2.7 Video Gen' },
    { num: 9, name: 'Final Compose' }
  ];
  const circledNums = ['❶','❷','❸','❹','❺','❻','❼','❽','❾'];
  let currentStep = 1;
  let currentName = 'Analyze Product';

  if (job.status === 'completed') {
    currentStep = 9;
  } else if (job.steps_data) {
    try {
      const s = typeof job.steps_data === 'string' ? JSON.parse(job.steps_data) : job.steps_data;
      if (s.pipeline?.status === 'success' || s.compose?.status === 'success') { currentStep = 9; currentName = 'Final Compose'; }
      else if (s.video_gen?.status === 'processing' || s.video_generation?.status === 'error') { currentStep = 8; currentName = 'Wan 2.7 Video Gen'; }
      else if (s.tts?.status === 'success') { currentStep = 8; currentName = 'Wan 2.7 Video Gen'; }
      else if (s.tts?.status === 'processing') { currentStep = 7; currentName = 'TTS Voice Gen'; }
      else if (s.video_prompts) { currentStep = 7; currentName = 'TTS Voice Gen'; }
      else if (s.image?.status === 'success' || s.generate_image) { currentStep = 6; currentName = 'Build Video Prompts'; }
      else if (s.prompt_builder?.status === 'success' || s.image_prompt) { currentStep = 5; currentName = 'Generate Image'; }
      else if (s.script) { currentStep = 4; currentName = 'Build Image Prompt'; }
      else if (s.recipe) { currentStep = 3; currentName = 'Generate Script'; }
      else if (s.analyze) { currentStep = 2; currentName = 'Load Recipe'; }
    } catch(e) {}
  }

  let passedCircles = '';
  for (let i = 0; i < currentStep - 1; i++) {
    passedCircles += `<span style="color:var(--accent-purple);font-size:12px;margin-right:2px">${circledNums[i]}</span>`;
  }

  if (job.status === 'completed') {
    return ''; // Hide step progress bar for completed jobs
  }

  let activeBadge = '';
  if (job.status === 'error') {
    activeBadge = `<span class="badge" style="background:rgba(239,68,68,0.15);color:#ef4444;font-size:10.5px;padding:2px 8px">❌ ${currentStep}/9 ${currentName} Failed</span>`;
  } else {
    activeBadge = `<span class="badge" style="background:rgba(139,92,246,0.15);color:var(--accent-purple);font-size:10.5px;padding:2px 8px">⏳ ${currentStep}/9 ${currentName}</span>`;
  }

  return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;width:100%">${passedCircles} ${activeBadge}</div>`;
}

async function loadPipelineJobs(force = false) {
  if (force) { window._pipelinePollCache = null; }
  const el = document.getElementById('pipelineJobList');
  const filter = document.getElementById('pipelineFilter')?.value || 'all';
  try {
    const res = await fetch(API + '/pipeline/list?limit=100');
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();
    let jobs = data.jobs || [];
    if (filter !== 'all') {
      jobs = jobs.filter(j => j.status === filter);
    }
    if (!jobs.length) {
      el.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:32px">📭 ไม่มีงานที่ตรงกับเงื่อนไข</div>';
      return;
    }

    // Trigger Notification for newly completed jobs
    jobs.forEach(function(job) {
      if (job.status === 'completed') {
        var jTitle = job.product_title || job.job_id || 'วิดีโอ';
        sendJobNotification('🎬 วิดีโอสร้างเสร็จสมบูรณ์แล้ว!', jTitle + ' พร้อมใช้งานและโพสต์ลงโซเชียลมีเดียแล้วครับ', job.job_id);
      }
    });
    // Use product_url from DB as product name (no per-job detail fetch to avoid flicker)
    // Cache-busting: only re-render when data actually changes (reduce flicker)
  var _cacheKey = JSON.stringify(jobs.map(function(j){return j.job_id+j.status+j.created_at;}));
  if (_cacheKey === window._pipelinePollCache) { return; }
  window._pipelinePollCache = _cacheKey;
  el.innerHTML = jobs.map(j => {
      const badgeCls = statusBadgeClass(j.status);
      const icon = statusIcon(j.status);
      const timeAgo = timeSince(j.created_at);
      const title = j.product_title || '';
      const prodImg = j.product_image || '';
      const genImg = j.generated_image || '';
      const hasProd = prodImg ? true : false;
      const hasGen = genImg ? true : false;
      const hasBoth = hasProd && hasGen;
      const imgW = hasBoth ? 96 : 48;
      const progressHtml = getStepProgressHtml(j);
      return `<div class="pipeline-job-card" style="flex-wrap:wrap">
        ${progressHtml}
        <div style="width:100%;display:flex;align-items:center;gap:8px;margin-bottom:6px">
          <div class="job-id" style="flex:1;font-weight:700;font-size:13.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${title || j.job_id}</div>
          <span class="badge ${badgeCls}" style="flex-shrink:0;font-size:11px">${icon} ${j.status}</span>
        </div>
        <div style="width:${imgW}px;height:48px;min-width:${imgW}px;border-radius:10px;overflow:hidden;border:1px solid var(--border-primary);display:flex;align-items:center;justify-content:center;background:var(--bg-tertiary);flex-shrink:0">
          ${hasBoth
            ? `<div style="width:48px;height:48px;min-width:48px;display:flex;align-items:center;justify-content:center;overflow:hidden"><img src="${prodImg}" alt="" style="width:100%;height:100%;object-fit:cover" onerror="this.style.display='none'"></div><div style="width:1px;height:40px;background:var(--border-primary);flex-shrink:0"></div><div style="width:48px;height:48px;min-width:48px;display:flex;align-items:center;justify-content:center;overflow:hidden"><img src="${genImg}" alt="" style="width:100%;height:100%;object-fit:cover" onerror="this.style.display='none'"></div>`
            : hasProd
              ? `<img src="${prodImg}" alt="" style="width:100%;height:100%;object-fit:cover" onerror="this.style.display='none';this.parentElement.innerHTML='${icon}'">`
              : hasGen
                ? `<img src="${genImg}" alt="" style="width:100%;height:100%;object-fit:cover" onerror="this.style.display='none';this.parentElement.innerHTML='${icon}'">`
                : `<span style="font-size:20px">${icon}</span>`
          }
        </div>
        <div style="flex:1;display:flex;flex-direction:column;gap:4px;min-width:0;padding-left:10px">
          <div style="display:flex;align-items:center;font-size:11px;color:var(--text-secondary);gap:8px">
            <span style="white-space:nowrap">🕐 ${timeAgo}</span>
            <span style="margin-left:auto"></span>
            <button class="btn btn-primary btn-sm" onclick="loadPipelineDetail('${j.job_id}')" style="padding:2px 7px;font-size:10.5px;margin:0 2px">📋 ดู</button>
            ${j.status === 'running' || j.status === 'pending' ? `<button class="btn btn-sm" onclick="cancelJobFromList('${j.job_id}')" style="padding:2px 6px;font-size:10.5px;margin:0 2px;color:var(--color-red-500)">✖</button>` : ''}
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;font-size:11px;color:var(--text-secondary)">
            <span>📋 ${j.job_id}</span>
            ${j.status !== 'completed' ? `<button class="btn btn-sm" onclick="retryJob('${j.job_id}')" style="padding:2px 8px;font-size:10.5px;margin-top:2px" title="Retry Job">🔄 ลองใหม่</button>` : ''}
          </div>
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    el.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:16px">Failed: ' + e.message + '</div>';
  }
}

async function loadPipelineDetail(jobId) {
  currentDetailJobId = jobId;
  const modal = document.getElementById('pipelineDetailModal');
  const idEl = document.getElementById('pdJobId');
  const statusEl = document.getElementById('pdStatusBadge');
  const createdEl = document.getElementById('pdCreatedAt');
  const accountEl = document.getElementById('pdAccountInfo');
  const timelineEl = document.getElementById('pdTimeline');
  const assetsEl = document.getElementById('pdAssets');
  const retryBtn = document.getElementById('pdRetryBtn');
  const cancelBtn = document.getElementById('pdCancelBtn');
  const infoSection = document.getElementById('pdInfoSection');
  const videoSection = document.getElementById('pdVideoSection');
  const imageSection = document.getElementById('pdImageSection');
  const scriptSection = document.getElementById('pdScriptSection');
  const promptsSection = document.getElementById('pdPromptsSection');
  const hashtagsSection = document.getElementById('pdHashtagsSection');
  const costsSection = document.getElementById('pdCostsSection');

  modal.classList.add('open');
  idEl.textContent = 'Loading...';
  statusEl.textContent = '...';
  timelineEl.innerHTML = '<div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line"></div>';
  assetsEl.innerHTML = '';
  // Show all sections by default (hide only if truly empty later)
  infoSection.style.display = 'block';
  videoSection.style.display = 'block';
  imageSection.style.display = 'block';
  scriptSection.style.display = 'block';
  promptsSection.style.display = 'block';
  hashtagsSection.style.display = 'block';
  costsSection.style.display = 'block';
  if (retryBtn) retryBtn.style.display = 'none';
  if (cancelBtn) cancelBtn.style.display = 'none';

  try {
    const res = await fetch(API + '/pipeline/detail/' + jobId);
    if (!res.ok) throw new Error('Job not found');
    const data = await res.json();
    const job = data.job;
    const logs = job.logs || {};
    const steps = job.steps || {};

    // Merge step data into logs for easier access
    for (const [sname, sdata] of Object.entries(steps)) {
      if (sdata.product_name) logs.product_title = logs.product_title || sdata.product_name;
      if (sdata.product_image) logs.product_img_web_url = logs.product_img_web_url || toWebUrl(sdata.product_image);
      if (sdata.generated_image_path || sdata.image_path) logs.image_web_url = logs.image_web_url || toWebUrl(sdata.generated_image_path || sdata.image_path);
      if (sdata.image_url && !logs.image_web_url) logs.image_web_url = sdata.image_url;
      if (sdata.image_prompt) logs.image_prompt = logs.image_prompt || sdata.image_prompt;
      if (sdata.video_prompt) logs.video_prompts = logs.video_prompts || sdata.video_prompt;
      if (sdata.script) logs.script = logs.script || sdata.script;
      if (sdata.hashtags) logs.hashtags = logs.hashtags || (Array.isArray(sdata.hashtags) ? sdata.hashtags.join(', ') : sdata.hashtags);
      if (sdata.tags) logs.hashtags = logs.hashtags || sdata.tags;
      // ⛔ video_url from steps is ALWAYS a local path — use toWebUrl()!
      if (!logs.video_web_url && sdata.video_url && sdata.video_url.includes('/')) {
        logs.video_web_url = toWebUrl(sdata.video_url);
      }
      if (sdata.filepath) logs.video_path = logs.video_path || sdata.filepath;
      if (sdata.video_path) logs.video_path = logs.video_path || sdata.video_path;
      if (sdata.negative_prompt) logs.negative_prompt = logs.negative_prompt || sdata.negative_prompt;
      if (sdata.cost_estimate) logs.cost_total = logs.cost_total || sdata.cost_estimate;
    }
    // For old jobs: extract tts filepath
    if (!logs.tts_audio_path && steps.tts && steps.tts.filepath) {
      logs.tts_audio_path = steps.tts.filepath;
      logs.tts_web_url = toWebUrl(steps.tts.filepath);
    }
    // Extract from metadata (in-memory results)
    if (job.metadata) {
      const m = job.metadata;
      if (m.product_name) logs.product_title = logs.product_title || m.product_name;
      if (m.product_image) logs.product_img_web_url = logs.product_img_web_url || toWebUrl(m.product_image);
      if (m.hashtags) logs.hashtags = logs.hashtags || (Array.isArray(m.hashtags) ? m.hashtags.join(', ') : m.hashtags);
      if (m.tags && Array.isArray(m.tags)) logs.hashtags = logs.hashtags || m.tags.join(', ');
      if (m.hook) logs.script_hook = logs.script_hook || m.hook;
      if (m.value) logs.script_value = logs.script_value || m.value;
      if (m.cta) logs.script_cta = logs.script_cta || m.cta;
      if (m.image_prompt) logs.image_prompt = logs.image_prompt || m.image_prompt;
      if (m.negative_prompt) logs.negative_prompt = logs.negative_prompt || m.negative_prompt;
      if (m.aspect_ratio) logs.aspect_ratio = logs.aspect_ratio || m.aspect_ratio;
      if (m.ugc_style) logs.ugc_style = logs.ugc_style || m.ugc_style;
      if (m.image_url) logs.image_web_url = logs.image_web_url || m.image_url;
    }
    // Also try metadata.product_url as product image
    if (!logs.product_img_web_url && job.product_url && job.product_url.match(/\.(jpg|jpeg|png|gif|webp)/i)) {
      logs.product_img_web_url = toWebUrl(job.product_url);
    }
    // Extract video from job.video_url (in-memory merged)
    if (!logs.video_web_url && job.video_url) {
      logs.video_web_url = toWebUrl(job.video_url);
    }

    idEl.textContent = job.job_id;
    statusEl.textContent = statusIcon(job.status) + ' ' + job.status;
    statusEl.className = 'badge ' + statusBadgeClass(job.status);
    const ctStr = job.created_at ? (job.created_at.includes('Z') ? job.created_at : job.created_at.replace(' ', 'T') + 'Z') : null;
    const ctDate = ctStr ? new Date(ctStr) : null;
    const thTime = ctDate ? ctDate.toLocaleString('th-TH', {timeZone:'Asia/Bangkok', hour12:false, year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'}) : '';
    createdEl.innerHTML = '🕐 ' + (job.created_at ? timeSince(job.created_at) : 'just now') + (thTime ? ' <span class="text-xs text-secondary">(' + thTime + ' น.)</span>' : '');
    accountEl.innerHTML = '👤 ' + (job.account_id || '—') + (job.product_url ? ' · 📦 ' + job.product_url.slice(0, 60) : '');

    // Retry / Cancel buttons
    if ((job.status === 'error' || job.status === 'restarted') && retryBtn) {
      retryBtn.style.display = 'inline-flex';
    }
    if ((job.status === 'running' || job.status === 'pending') && cancelBtn) {
      cancelBtn.style.display = 'inline-flex';
    }

    // ── Product Info Section ──
    const productName = logs.product_title || logs.product_name || '';
    const productDesc = logs.product_description || '';
    const productPrice = logs.product_price;
    const productImgUrl = logs.product_img_web_url || logs.product_image_path || '';
    document.getElementById('pdProductName').textContent = productName || '—';
    document.getElementById('pdProductDesc').textContent = (productDesc || '').slice(0, 200) || '—';
    document.getElementById('pdProductPrice').textContent = productPrice ? '฿' + Number(productPrice).toLocaleString() : '—';
    const pimg = document.getElementById('pdProductImg');
    if (productImgUrl) {
      pimg.src = productImgUrl;
      pimg.style.display = 'block';
    } else {
      pimg.style.display = 'none';
    }
    // Show product category tags (NOT hashtags - hashtags have their own section below)
    const tagsEl = document.getElementById('pdProductTags');
    const category = logs.product_category || '';
    if (category) {
      tagsEl.innerHTML = `<span class="badge badge-gray" style="font-size:10px">📂 ${category}</span>`;
    } else {
      tagsEl.innerHTML = '';
    }

    // ── Video Section ──
    const videoUrl = logs.video_web_url || '';
    const vp = document.getElementById('pdVideoPlayer');
    if (videoUrl) {
      vp.pause();
      vp.src = videoUrl;
      vp.load();
      document.getElementById('pdVideoLink').href = videoUrl;
      videoSection.style.display = 'block';
    } else {
      vp.pause();
      vp.removeAttribute('src');
      vp.load();
    }

    // ── Generated Image ──
    const imageUrl = logs.image_web_url || logs.generated_image_path || '';
    const imgEl = document.getElementById('pdGeneratedImg');
    if (imageUrl && imgEl) {
      imgEl.onerror = function() { this.parentElement.innerHTML = '<span class="text-secondary" style="font-size:12px">❌ Image unavailable</span>'; };
      imgEl.src = imageUrl;
      imageSection.style.display = 'block';
    } else {
      imageSection.style.display = 'none';
    }

    // ── Script Section ──
    const script = logs.script || '';
    // Try to parse Hook/Value/CTA from the script text when not stored separately
    let hookFromLogs = logs.hook || logs.script_hook || '';
    let valueFromLogs = logs.value || logs.script_value || '';
    let ctaFromLogs = logs.cta || logs.script_cta || '';
    // Parse from script text if empty
    if (script && !hookFromLogs && !valueFromLogs && !ctaFromLogs) {
      const scriptText = script;
      // Match [Hook] ... [Value] ... [CTA] pattern
      const hookMatch = scriptText.match(/\[Hook\]\s*([^\[]+)/i);
      const valueMatch = scriptText.match(/\[Value\]\s*([^\[]+)/i);
      const ctaMatch = scriptText.match(/\[CTA\]\s*([^\[]+)/i);
      if (hookMatch) hookFromLogs = hookMatch[1].trim().replace(/\s*\n\s*/g, ' ');
      if (valueMatch) valueFromLogs = valueMatch[1].trim().replace(/\s*\n\s*/g, ' ');
      if (ctaMatch) ctaFromLogs = ctaMatch[1].trim().replace(/\s*\n\s*/g, ' ');
      // Fallback for 8s format: first sentence = hook
      if (!hookFromLogs && !valueFromLogs) {
        const sentences = scriptText.split(/[.!?]+/).filter(Boolean);
        if (sentences.length >= 3) {
          hookFromLogs = sentences[0].trim();
          valueFromLogs = sentences[1].trim();
          ctaFromLogs = sentences.slice(2).join('. ').trim();
        }
      }
    }
    const scEl = document.getElementById('pdScript');
    if (hookFromLogs || valueFromLogs || ctaFromLogs) {
      scriptSection.style.display = 'block';
      const parts = [];
      if (hookFromLogs) parts.push('<div class="mb-2"><span class="badge badge-amber" style="font-size:10px">📢 Hook</span><div style="margin-top:4px;font-size:13px;color:var(--text-primary)">' + escapeHtml(hookFromLogs) + '</div></div>');
      if (valueFromLogs) parts.push('<div class="mb-2"><span class="badge badge-green" style="font-size:10px">💡 Value</span><div style="margin-top:4px;font-size:13px;color:var(--text-primary)">' + escapeHtml(valueFromLogs) + '</div></div>');
      if (ctaFromLogs) parts.push('<div><span class="badge badge-indigo" style="font-size:10px">🎯 CTA</span><div style="margin-top:4px;font-size:13px;color:var(--text-primary)">' + escapeHtml(ctaFromLogs) + '</div></div>');
      scEl.innerHTML = parts.join('');
    } else if (script) {
      scriptSection.style.display = 'block';
      scEl.innerHTML = '<pre style="white-space:pre-wrap;font-family:inherit;font-size:13px;line-height:1.6;color:var(--text-primary);margin:0">' + escapeHtml(script) + '</pre>';
    } else {
      scEl.innerHTML = '<span class="text-secondary" style="font-size:12px">ไม่มีข้อมูล Script</span>';
    }

    // ── Prompts Section ──
    const imgPrompt = logs.image_prompt || '';
    const vidPrompt = logs.video_prompts || '';
    const negPrompt = logs.negative_prompt || '';
    const promptEl = document.getElementById('pdPrompts');
    const pParts = [];
    if (imgPrompt) pParts.push('<div class="mb-3"><span class="badge" style="background:rgba(99,102,241,0.1);color:var(--brand);font-size:10px">🖼 Image Prompt</span><div style="margin-top:4px;font-size:12.5px;color:var(--text-primary);line-height:1.5">' + escapeHtml(imgPrompt.slice(0, 500)) + '</div></div>');
    if (vidPrompt) {
      const vpText = typeof vidPrompt === 'string' ? vidPrompt : Array.isArray(vidPrompt) ? vidPrompt.join(' | ') : JSON.stringify(vidPrompt);
      pParts.push('<div class="mb-3"><span class="badge" style="background:rgba(16,185,129,0.1);color:var(--accent-green);font-size:10px">🎬 Video Prompt</span><div style="margin-top:4px;font-size:12.5px;color:var(--text-primary);line-height:1.5">' + escapeHtml(vpText.slice(0, 500)) + '</div></div>');
    }
    if (negPrompt) pParts.push('<div><span class="badge badge-red" style="font-size:10px">🚫 Negative Prompt</span><div style="margin-top:4px;font-size:12.5px;color:var(--text-secondary);line-height:1.5">' + escapeHtml(negPrompt.slice(0, 300)) + '</div></div>');
    if (pParts.length) {
      promptEl.innerHTML = pParts.join('');
      promptsSection.style.display = 'block';
    } else {
      promptEl.innerHTML = '<span class="text-secondary" style="font-size:12px">ไม่มีข้อมูล Prompt</span>';
    }

    // ── Hashtags Section ──
    const hashtags = logs.hashtags || '';
    const htEl = document.getElementById('pdHashtags');
    if (hashtags && hashtags !== '[]') {
      const tagList = typeof hashtags === 'string' ? hashtags.split(',').map(t => t.trim()).filter(Boolean) : hashtags;
      // Filter out empty/brace artifacts from JSON array strings
      const cleanTags = tagList.filter(t => t && t !== '[' && t !== ']');
      if (cleanTags.length) {
        htEl.innerHTML = cleanTags.map(t => `<span class="badge badge-indigo" style="font-size:11px;margin:2px">🏷 ${t}</span>`).join(' ');
        hashtagsSection.style.display = 'block';
      } else {
        htEl.innerHTML = '<span class="text-secondary" style="font-size:12px">ไม่มี Hashtags</span>';
      }
    }

    // ── Costs Section ──
    const costTotal = logs.cost_total || logs.cost_estimate || 0;
    if (costTotal) {
      costsSection.style.display = 'block';
      document.getElementById('pdCostTotal').textContent = '💰 $' + Number(costTotal).toFixed(3);
      document.getElementById('pdCostImage').textContent = '🖼 $' + Number(logs.cost_image || 0).toFixed(3);
      document.getElementById('pdCostVoice').textContent = '🔊 $' + Number(logs.cost_voice || 0).toFixed(3);
      document.getElementById('pdCostVideo').textContent = '🎬 $' + Number(logs.cost_video || 0).toFixed(3);
    }

    // ── Timeline (compact, no bubbles, no file paths) ──
    const stepNames = Object.keys(steps).filter(n => n !== 'result');
    if (stepNames.length === 0) {
      timelineEl.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:20px">ℹ️ ยังไม่มีข้อมูลขั้นตอน</div>';
    } else {
      timelineEl.innerHTML = '<div class="card-title mb-2" style="font-size:14px">📋 ขั้นตอนการทำงาน</div>'
        + '<div style="display:table;width:100%;border-collapse:collapse">'
        + stepNames.map((name, i) => {
          const step = steps[name];
          const st = step.status || 'pending';
          const icon = stepStatusIcon(st);
          const badgeCls = st === 'success' ? 'badge-green' : st === 'error' ? 'badge-red' : st === 'processing' ? 'badge-amber' : 'badge-gray';
          const bgRow = st === 'success' ? 'rgba(16,185,129,0.05)' : st === 'error' ? 'rgba(239,68,68,0.05)' : 'transparent';
          return `<div style="display:table-row">
            <div style="display:table-cell;padding:6px 8px;white-space:nowrap;font-size:13px;border-bottom:1px solid var(--border-primary);background:${bgRow}">${icon} <span style="text-transform:capitalize">${name.replace(/_/g, ' ')}</span></div>
            <div style="display:table-cell;padding:6px 8px;text-align:right;font-size:12px;border-bottom:1px solid var(--border-primary);background:${bgRow}"><span class="badge ${badgeCls}" style="font-size:10px">${st}</span></div>
          </div>`;
        }).join('') + '</div>';
    }

    // ── Bottom Assets (compact, filenames only) ──
    const assetFiles = [];
    for (const [name, step] of Object.entries(steps)) {
      if (step.filepath) assetFiles.push({ label: name, path: step.filepath });
    }
    if (logs.tts_audio_path) assetFiles.push({ label: 'TTS Audio', path: logs.tts_audio_path });
    if (logs.video_path) assetFiles.push({ label: 'Raw Video', path: logs.video_path });
    if (logs.final_video_path) assetFiles.push({ label: 'Final Video', path: logs.final_video_path });
    if (assetFiles.length) {
      const unique = [...new Map(assetFiles.map(a => [a.path, a])).values()];
      assetsEl.innerHTML = '<div class="card-title mb-2" style="font-size:13px">📎 ไฟล์ที่สร้าง</div>'
        + unique.map(a => {
          const isVideo = a.path.match(/\.(mp4|mov|webm)$/i);
          return `<span style="display:inline-flex;align-items:center;gap:4px;padding:4px 8px;margin:2px;border-radius:6px;background:var(--bg-tertiary);cursor:pointer;font-size:12px;border:1px solid var(--border-primary)" onclick="window.open('${toWebUrl(a.path)}','_blank')">${isVideo ? '🎬' : '📄'} ${a.path.split('/').pop()}</span>`;
        }).join('');
    }
  } catch(e) {
    idEl.textContent = 'Error';
    timelineEl.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:20px;color:var(--color-red-500)">❌ ' + e.message + '</div>';
  }
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = String(text);
  return div.innerHTML;
}

function toWebUrl(localPath) {
  if (!localPath) return '';
  if (localPath.startsWith('http://') || localPath.startsWith('https://') || localPath.startsWith('/')) {
    // Already a URL or web path, just ensure it goes through proxy
    if (localPath.startsWith('/static/') && !localPath.startsWith('/api/')) {
      return '/api/tiktok' + localPath;
    }
    if (localPath.startsWith('/api/')) return localPath;
    // Convert local file paths
    if (localPath.startsWith('/home/openhands/erp-stack/modules/video/storage')) {
      return '/static/video/' + localPath.slice('/home/openhands/erp-stack/modules/video/storage/'.length);
    }
    if (localPath.startsWith('/home/openhands/erp-stack/tiktok-ugc-studio/storage')) {
      return '/api/tiktok/static/' + localPath.slice('/home/openhands/erp-stack/tiktok-ugc-studio/storage/'.length);
    }
    if (localPath.startsWith('http://')) return localPath;
  }
  return localPath;
}

function fmtCost(c) {
  if (!c || c == 0) return '';
  return '$' + Number(c).toFixed(3);
}

function closePipelineDetail() {
  var vp = document.getElementById('pdVideoPlayer');
  if (vp) { try { vp.pause(); vp.removeAttribute('src'); } catch(e) {} }
  document.getElementById('pipelineDetailModal').classList.remove('open');
  currentDetailJobId = '';
}

async function retryJob(jobId) {
  try {
    const res = await fetch(API + '/pipeline/' + jobId + '/retry', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast('🔄 Retry initiated for ' + jobId, 'success');
      loadPipelineDetail(jobId);
      loadPipelineJobs();
    } else {
      showToast('❌ ' + (data.error || 'Retry failed'), 'error');
    }
  } catch(e) {
    showToast('Error: ' + e.message, 'error');
  }
}

async function cancelJobFromList(jobId) {
  if (!confirm('⚠️ คุณแน่ใจหรือไม่ว่าต้องการยกเลิกงานนี้? (Job: ' + jobId + ')')) return;
  if (!confirm('‼️ ยืนยันการยกเลิกงานอีกครั้ง? การกระทำนี้ไม่สามารถย้อนกลับได้')) return;
  await cancelJobApi(jobId);
  loadPipelineJobs();
}

async function cancelJobFromDetail(jobId) {
  if (!confirm('⚠️ คุณแน่ใจหรือไม่ว่าต้องการยกเลิกงานนี้? (Job: ' + jobId + ')')) return;
  if (!confirm('‼️ ยืนยันการยกเลิกงานอีกครั้ง? การกระทำนี้ไม่สามารถย้อนกลับได้')) return;
  await cancelJobApi(jobId);
  loadPipelineDetail(jobId);
  loadPipelineJobs();
}

async function cancelJobApi(jobId) {
  try {
    const res = await fetch(API + '/pipeline/' + jobId + '/cancel', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast('🚫 Job ' + jobId + ' cancelled', 'info');
    } else {
      showToast('❌ ' + (data.error || 'Cancel failed'), 'error');
    }
  } catch(e) {
    showToast('Error: ' + e.message, 'error');
  }
}

async function loadAssetLibrary() {
  const modal = document.getElementById('assetLibraryModal');
  const grid = document.getElementById('assetLibraryGrid');
  const filter = document.getElementById('assetFilter')?.value || 'all';
  modal.classList.add('open');
  grid.innerHTML = '<div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line"></div>';
  try {
    const res = await fetch(API + '/pipeline/assets');
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();
    const images = data.images || [];
    const videos = data.videos || [];
    let items = [];
    if (filter === 'all' || filter === 'images') {
      items = items.concat(images.map(a => ({ ...a, _type: 'image' })));
    }
    if (filter === 'all' || filter === 'videos') {
      items = items.concat(videos.map(a => ({ ...a, _type: 'video' })));
    }
    if (!items.length) {
      grid.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:40px">📭 No assets found</div>';
      return;
    }
    grid.innerHTML = '<div class="asset-grid">' + items.map(a => {
      const name = a.name || a.path.split('/').pop() || 'asset';
      const size = a.size ? (a.size / 1024).toFixed(1) + ' KB' : '';
      const time = a.created ? timeSince(a.created) : '';
      if (a._type === 'video') {
        return `<div class="asset-card" onclick="window.open('${a.url}','_blank')">
          <div class="asset-thumb">
            <video src="${a.url}" muted preload="metadata"></video>
            <div class="asset-play-overlay">▶</div>
            <span class="asset-type-badge">🎬</span>
          </div>
          <div class="asset-info">
            <div class="asset-name" title="${name}">${name}</div>
            <div class="asset-meta">${size} ${time ? '· ' + time : ''}</div>
          </div>
        </div>`;
      }
      return `<div class="asset-card" onclick="window.open('${a.url}','_blank')">
        <div class="asset-thumb">
          <img src="${a.url}" alt="${name}" loading="lazy">
          <span class="asset-type-badge">🖼</span>
        </div>
        <div class="asset-info">
          <div class="asset-name" title="${name}">${name}</div>
          <div class="asset-meta">${size} ${time ? '· ' + time : ''}</div>
        </div>
      </div>`;
    }).join('') + '</div>';
  } catch(e) {
    grid.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:40px;color:var(--color-red-500)">❌ ' + e.message + '</div>';
  }
}

function closeAssetLibrary() {
  document.getElementById('assetLibraryModal').classList.remove('open');
}

/* ═══ Post to TikTok ═══ */
let _postJobId = '';

async function openPostModal(jobId, videoUrl) {
  _postJobId = jobId;
  const modal = document.getElementById('postModal');
  const video = document.getElementById('postVideoPreview');
  
  // Set video preview
  video.src = videoUrl;
  
  // Load accounts
  const sel = document.getElementById('postAccountSelect');
  sel.innerHTML = '<option value="">— กำลังโหลด —</option>';
  try {
    const r = await fetch(API + '/tiktok/accounts');
    const d = await r.json();
    const accounts = d.accounts || d || {};
    sel.innerHTML = '<option value="">— เลือกบัญชี —</option>';
    if (Array.isArray(accounts)) {
      accounts.forEach(a => {
        const name = a.username || a.name || a.account_id || a;
        sel.innerHTML += `<option value="${name}">@${name}</option>`;
      });
    } else {
      Object.keys(accounts).forEach(k => {
        sel.innerHTML += `<option value="${k}">@${k}</option>`;
      });
    }
  } catch(e) {
    sel.innerHTML = '<option value="">❌ โหลดไม่สำเร็จ</option>';
  }
  
  // Clear form
  document.getElementById('postAffiliateLink').value = '';
  document.getElementById('postCaption').value = '';
  document.getElementById('postScheduleTime').value = '';
  document.getElementById('postProgress').style.display = 'none';
  document.getElementById('postBtn').disabled = false;
  document.getElementById('postBtn').textContent = '🚀 Post Now';
  
  modal.classList.add('open');
}

/* ═══ Scheduled Posts ═══ */
async function loadScheduledPosts() {
  const el = document.getElementById('scheduledPostsList');
  if (!el) return;
  try {
    const r = await fetch(API + '/posts/scheduled');
    const d = await r.json();
    const posts = d.posts || [];
    if (!posts.length) {
      el.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:24px">📭 ไม่มีโพสต์ที่ scheduled</div>';
      return;
    }
    el.innerHTML = posts.map(p => {
      const statusIcon = p.status === 'published' ? '✅' : p.status === 'failed' ? '❌' : '⏳';
      const schedTime = p.schedule_at ? new Date(p.schedule_at).toLocaleString('th-TH') : '-';
      return '<div class="card" style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;margin-bottom:8px">'
        + '<div><strong>' + statusIcon + ' ' + (p.account_id || '-') + '</strong> <span class="badge ' + (p.status === 'published' ? 'badge-green' : p.status === 'failed' ? 'badge-red' : 'badge') + '">' + p.status + '</span></div>'
        + '<div class="text-xs text-secondary">⏰ ' + schedTime + (p.affiliate_link ? ' 🔗มีลิงก์' : '') + '</div>'
        + '<div style="display:flex;gap:4px">'
        + (p.status === 'pending' ? '<button class="btn btn-ghost btn-sm" onclick="cancelScheduledPost(' + p.id + ')">✖ ยกเลิก</button>' : '')
        + '</div></div>';
    }).join('');
  } catch(e) {
    if (el) el.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:16px">Failed: ' + e.message + '</div>';
  }
}

async function cancelScheduledPost(postId) {
  if (!confirm('ยกเลิกโพสต์นี้?')) return;
  try {
    const r = await fetch(API + '/posts/scheduled/' + postId, {method:'DELETE'});
    const d = await r.json();
    if (d.success) { showToast('✅ ยกเลิกแล้ว', 'success'); loadScheduledPosts(); }
    else { showToast('❌ ' + (d.error || 'Failed'), 'error'); }
  } catch(e) { showToast('Error: ' + e.message, 'error'); }
}

/* ═══ Google Sheets ═══ */
let _sheetsConfigured = false;

// Auto-connect on page load: check status + prefill ID
async function autoInitSheets() {
  const sidInput = document.getElementById('sheetsSpreadsheetId');
  const badge = document.getElementById('sheetsStatusBadge');
  if (!sidInput) return;
  try {
    const r = await fetch(API + '/products/sheets/status');
    const d = await r.json();
    if (d.configured && d.spreadsheet_id) {
      sidInput.value = d.spreadsheet_id;
      _sheetsConfigured = true;
      badge.textContent = '✅ พร้อมเชื่อมต่อ'; badge.className = 'badge badge-indigo';
      // Auto-connect to get worksheet list
      connectSheet();
    } else if (d.configured) {
      badge.textContent = '✅ Credentials OK'; badge.className = 'badge badge-green';
      _sheetsConfigured = true;
    } else {
      badge.textContent = '❌ ไม่ได้ตั้งค่า'; badge.className = 'badge badge-red';
    }
  } catch(e) { /* silent */ }
}

async function connectSheet() {
  const sid = document.getElementById('sheetsSpreadsheetId').value.trim();
  const badge = document.getElementById('sheetsStatusBadge');
  const result = document.getElementById('sheetsResult');
  const configArea = document.getElementById('sheetsConfigArea');
  if (!sid) { showToast('ใส่ Spreadsheet ID ก่อน', 'error'); return; }

  badge.textContent = '⏳ กำลังเชื่อมต่อ...';
  result.innerHTML = '';
  try {
    const r = await fetch(API + '/products/sheets/connect', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({spreadsheet_id: sid, sheet_name: ''})
    });
    const d = await r.json();
    if (d.success) {
      badge.textContent = '✅ ' + d.title; badge.className = 'badge badge-green';
      _sheetsConfigured = true;
      result.innerHTML = '<span class="text-green">✔ เชื่อมต่อสำเร็จ: <strong>' + d.title + '</strong></span>';
      
      // Populate sheet selector dropdown
      const sel = document.getElementById('sheetsSheetSelector');
      sel.innerHTML = d.worksheets.map(ws => '<option value="' + ws + '">' + ws + '</option>').join('');
      configArea.style.display = 'block';
    } else {
      badge.textContent = '❌ Failed'; badge.className = 'badge badge-red';
      result.innerHTML = '<span class="text-red">' + (d.error || 'เชื่อมต่อไม่สำเร็จ') + '</span>';
    }
  } catch(e) {
    badge.textContent = '⚠ Error'; result.innerHTML = e.message;
  }
}

async function importFromSheets() {
  const sid = document.getElementById('sheetsSpreadsheetId').value.trim();
  const sname = document.getElementById('sheetsSheetSelector').value || 'Products';
  const result = document.getElementById('sheetsResult');
  if (!sid) { showToast('ใส่ Spreadsheet ID ก่อน', 'error'); return; }
  
  // Collect field mapping
  const mapping = {
    title: document.getElementById('map_title')?.value || 'ชื่อสินค้า',
    price: document.getElementById('map_price')?.value || 'ราคา',
    url: document.getElementById('map_url')?.value || 'ลิงก์',
    category: document.getElementById('map_category')?.value || 'หมวดหมู่',
    image_url: document.getElementById('map_image_url')?.value || 'รูปภาพ',
    commission: document.getElementById('map_commission')?.value || 'คอมมิชชั่น',
  };
  
  result.innerHTML = '<span>⏳ กำลัง Import...</span>';
  try {
    const r = await fetch(API + '/products/sheets/import', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({spreadsheet_id: sid, sheet_name: sname, limit: 50, mapping: mapping})
    });
    const d = await r.json();
    if (d.success) {
      result.innerHTML = '<span class="text-green">✅ Imported <strong>' + d.imported_count + '</strong> products!</span>';
      showToast('✅ Imported ' + d.imported_count + ' products!', 'success');
      loadAnalyzedProducts();
    } else {
      result.innerHTML = '<span class="text-red">❌ ' + (d.error || 'Import failed') + '</span>';
    }
  } catch(e) { result.innerHTML = '<span class="text-red">' + e.message + '</span>'; }
}

async function postToTikTok() {
  const account = document.getElementById('postAccountSelect').value;
  if (!account) { showToast('เลือกบัญชี TikTok ก่อน','error'); return; }
  
  const link = document.getElementById('postAffiliateLink').value.trim();
  const caption = document.getElementById('postCaption').value.trim();
  const schedule = document.getElementById('postScheduleTime').value;
  
  const progress = document.getElementById('postProgress');
  const bar = document.getElementById('postProgressBar');
  const text = document.getElementById('postProgressText');
  const btn = document.getElementById('postBtn');
  
  progress.style.display = 'block';
  bar.style.width = '30%';
  text.textContent = '⏳ กำลัง Post...';
  btn.disabled = true;
  
  try {
    const body = {
      job_id: _postJobId,
      account_id: account,
      affiliate_link: link,
      caption: caption,
      schedule_at: schedule || 'now',
    };
    
    const r = await fetch(API + '/video/post', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
    });
    bar.style.width = '80%';
    
    if (!r.ok) {
      const errData = await r.json().catch(() => ({}));
      throw new Error(errData.detail || 'Post failed');
    }
    
    const data = await r.json();
    bar.style.width = '100%';
    text.textContent = '✅ โพสต์สำเร็จ! Video ID: ' + (data.video_id || 'OK');
    showToast('✅ โพสต์ไปที่ @' + account + ' แล้ว!','success');
    
    setTimeout(() => {
      document.getElementById('postModal').classList.remove('open');
      if (d.scheduled) {
        showToast('📅 Scheduled! ' + new Date(d.schedule_at).toLocaleString('th-TH'), 'success');
        loadScheduledPosts();
      } else {
        showToast('✅ Posted to TikTok!', 'success');
      }
      loadPipeline();
      loadHistory();
    }, 1500);
  } catch(e) {
    bar.style.width = '100%';
    bar.style.background = '#ef4444';
    text.textContent = '❌ ' + e.message;
    showToast('Post failed: ' + e.message,'error');
    btn.disabled = false;
  }
}

async function cancelJob(id) {
  try { await fetch(API + '/video/cancel/'+id, {method:'POST'}); showToast('Job cancelled','info'); loadPipeline(); } catch(e) { showToast('Failed','error'); }
}

/* ═══ Accounts ═══ */
function showAddAccount() { document.getElementById('addAccountForm').style.display = 'block'; }

async function addAccount() {
  const username = document.getElementById('accUsername').value;
  const password = document.getElementById('accPassword').value;
  const sessionToken = document.getElementById('accToken').value.trim();
  if (!username) { showToast('ใส่ Username','error'); return; }
  try {
    const body = { username, password: password||undefined };
    if (sessionToken) body.session_token = sessionToken;
    const res = await fetch(API + '/tiktok/accounts', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error('Failed');
    showToast(sessionToken ? 'Account added with token ✅' : 'Account added','success');
    document.getElementById('addAccountForm').style.display = 'none';
    document.getElementById('accUsername').value = ''; document.getElementById('accPassword').value = ''; document.getElementById('accToken').value = '';
    loadAccounts(); populateAccountSelect();
  } catch(e) { showToast('Failed: '+e.message,'error'); }
}

async function loadAccounts() {
  const el = document.getElementById('accountsList');
  try {
    var html = '';
    
    // Fetch AitoEarn accounts
    try {
      var aeR = await fetch(API + '/aitoearn/platforms');
      var aeD = await aeR.json();
      var aePlatforms = aeD.platforms || [];
      
      aePlatforms.forEach(function(p) {
        (p.accounts || []).forEach(function(a) {
          html += '<div class="account-item">' +
            '<div class="avatar" style="background-image:url(' + (a.avatar||'') + ');background-size:cover;background-position:center;width:36px;height:36px;border-radius:50%">' + ((!a.avatar) ? (a.nickname||'?')[0].toUpperCase() : '') + '</div>' +
            '<div style="flex:1">' +
            '<div class="font-medium">' + (a.nickname || a.id) + ' <span style="font-size:10px;color:var(--text-tertiary)">' + p.platform.toUpperCase() + '</span></div>' +
            '<div style="display:flex;align-items:center;gap:6px;margin-top:2px">' +
            '<span class="status-dot online"></span>' +
            '<span class="text-xs text-secondary">' + a.fans + ' followers · ' + a.works + ' works</span>' +
            '</div></div>' +
            '<span style="font-size:11px;background:var(--bg-tertiary);padding:2px 6px;border-radius:4px">AitoEarn</span>' +
            '</div>';
        });
      });
    } catch(e) { console.log('AitoEarn load error (non-critical):', e); }
    
    // Also fetch local accounts
    try {
      var res = await fetch(API + '/tiktok/accounts');
      if (res.ok) {
        var data = await res.json();
        var accounts = data.accounts || data || [];
        accounts.forEach(function(a) {
          html += '<div class="account-item">' +
            '<div class="avatar" style="background:linear-gradient(135deg,' + hashColor(a.username||a.id||'A') + ',' + hashColor2(a.username||a.id||'A') + ')">' + (a.username||a.id||'?')[0].toUpperCase() + '</div>' +
            '<div style="flex:1">' +
            '<div class="font-medium">' + (a.username || a.id || 'Unknown') + '</div>' +
            '<div style="display:flex;align-items:center;gap:6px;margin-top:2px">' +
            '<span class="status-dot ' + (a.is_logged_in ? 'online' : 'offline') + '"></span>' +
            '<span class="text-xs text-secondary">' + (a.is_logged_in ? 'Logged in ✅' : (a.session_token ? 'Has token' : 'Not logged in')) + '</span>' +
            (a.session_token ? '<span class="text-xs text-secondary ml-1">🔑</span>' : '') +
            '</div></div>' +
            '<span style="font-size:11px;background:var(--bg-tertiary);padding:2px 6px;border-radius:4px">Local</span>' +
            '</div>';
        });
      }
    } catch(e) { console.log('Local accounts error:', e); }
    
    if (!html) { html = '<div class="text-sm text-secondary" style="text-align:center;padding:16px">No accounts yet — connect AitoEarn or add a local session</div>'; }
    el.innerHTML = html;
  } catch(e) { el.innerHTML = '<div class="text-sm text-secondary" style="padding:16px">Failed to load accounts</div>'; }
}

function hashColor(s) { const colors = ['#7c3aed','#2563eb','#0891b2','#059669','#d97706','#dc2626','#db2777','#7c2d12']; let h=0;for(let i=0;i<s.length;i++)h=s.charCodeAt(i)+((h<<5)-h);return colors[Math.abs(h)%colors.length]; }
function hashColor2(s) { const colors = ['#a78bfa','#60a5fa','#22d3ee','#34d399','#fbbf24','#f87171','#f472b6','#f97316']; let h=0;for(let i=0;i<s.length;i++)h=s.charCodeAt(i)+((h<<5)-h)+1;return colors[Math.abs(h)%colors.length]; }

/* ═══ TikTok QR Login ═══ */

async function requestTikTokQR() {
  // เรียก API หลังบ้านเพื่อขอ QR code login
  const el = document.getElementById('qrCodeContainer');
  const st = document.getElementById('qrStatus');
  el.innerHTML = '<div style="text-align:center;padding:20px"><div class="spinner"></div><div class="text-sm mt-2">กำลังสร้าง QR...</div></div>';
  st.textContent = 'กำลังเชื่อมต่อ TikTok...';
  
  try {
    const res = await fetch(API + '/tiktok/qr-login', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({})
    });
    const data = await res.json();
    
    if (data.qr_url || data.qr_code) {
      const qrUrl = data.qr_url || data.qr_code;
      el.innerHTML = `<img src="${qrUrl}" style="max-width:220px;border-radius:12px;display:block;margin:0 auto;box-shadow:0 4px 12px rgba(0,0,0,.15)" alt="TikTok QR Code">`;
      st.textContent = data.message || '📱 สแกน QR ด้วยแอป TikTok เพื่อล็อกอิน (QR หมดอายุ 300 วิ)';
      
      // Auto-poll สำหรับเช็ค login status
      if (data.token_id) {
        const tokenId = data.token_id;
        let attempts = 0;
        const pollInterval = setInterval(async () => {
          attempts++;
          try {
            const pollRes = await fetch(API + '/tiktok/qr-status/' + tokenId);
            const pollData = await pollRes.json();
            if (pollData.status === 'completed' || pollData.logged_in) {
              clearInterval(pollInterval);
              el.innerHTML = '<div style="text-align:center;padding:20px"><div style="font-size:48px;margin-bottom:8px">✅</div><div class="font-medium">ล็อกอินสำเร็จ!</div></div>';
              st.textContent = 'พร้อมใช้งานแล้ว 🎉';
              setTimeout(() => closeQrModal(), 2000);
              loadAccounts();
            } else if (pollData.status === 'expired' || pollData.status === 'failed') {
              clearInterval(pollInterval);
              el.innerHTML = '<div style="text-align:center;padding:20px"><div style="font-size:48px;margin-bottom:8px">⏰</div><div class="font-medium">QR หมดอายุแล้ว</div></div>';
              st.textContent = 'กด "สร้าง QR" เพื่อสร้างใหม่';
            }
          } catch(e) {}
          if (attempts > 60) { clearInterval(pollInterval); } // max 5 นาที
        }, 5000);
      }
    } else {
      el.innerHTML = '<div style="text-align:center;padding:20px"><div style="font-size:48px">❌</div><div class="text-sm mt-2">' + (data.error || 'สร้าง QR ไม่สำเร็จ') + '</div></div>';
      st.textContent = 'ลองอีกครั้ง';
    }
  } catch(e) {
    el.innerHTML = '<div style="text-align:center;padding:20px"><div style="font-size:48px">❌</div><div class="text-sm mt-2">Connection failed</div></div>';
    st.textContent = e.message;
  }
}

async function loginAccount(id) {
  try {
    const res = await fetch(API + '/tiktok/login', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ account_id: id })
    });
    const data = await res.json();
    if (data.qr_url || data.qr_code) {
      document.getElementById('qrCodeContainer').innerHTML = `<img src="${data.qr_url||data.qr_code}" style="max-width:200px;border-radius:8px" alt="QR">`;
      document.getElementById('qrModal').classList.add('open');
      
      // Auto-poll
      if (data.token_id) {
        const tokenId = data.token_id;
        const st = document.getElementById('qrStatus');
        st.textContent = 'สแกน QR ด้วย TikTok...';
        let attempts = 0;
        const pi = setInterval(async () => {
          attempts++;
          try {
            const pr = await fetch(API + '/tiktok/qr-status/' + tokenId);
            const pd = await pr.json();
            if (pd.status === 'completed' || pd.logged_in) {
              clearInterval(pi);
              st.textContent = '✅ ล็อกอินสำเร็จ!'; loadAccounts();
              setTimeout(() => closeQrModal(), 1500);
            } else if (pd.status === 'expired' || pd.status === 'failed') {
              clearInterval(pi);
              st.textContent = '⏰ QR หมดอายุ กด สร้าง QR ใหม่';
            }
          } catch(e) {}
          if (attempts > 60) clearInterval(pi);
        }, 5000);
      }
    } else if (data.status === 'poll' || data.status === 'pending') {
      document.getElementById('qrModal').classList.add('open');
      document.getElementById('qrCodeContainer').innerHTML = `<div style="text-align:center;padding:20px"><div style="font-size:48px">⏳</div><div class="text-sm mt-2">${data.message || 'รอการยืนยัน...'}</div></div>`;
    }
    showToast('Login initiated','info');
    loadAccounts();
  } catch(e) { showToast('Login failed: '+e.message,'error'); }
}

document.addEventListener('DOMContentLoaded', function() {
  // ── Restore tab from URL hash (PWA pull-to-refresh) ────
  if (location.hash) {
    var hashTab = location.hash.replace('#', '');
    if (hashTab && document.getElementById('page-' + hashTab)) {
      switchTab(hashTab);
    }
  } else {
    // First load — set default tab in URL hash
    location.hash = 'dashboard';
  }
  
  // ถ้ามีปุ่ม QR Login เพิ่มในหน้า Accounts
  const accountsHeader = document.querySelector('#page-accounts .page-header .flex');
  if (accountsHeader) {
    const qrBtn = document.createElement('button');
    qrBtn.className = 'btn btn-secondary btn-sm';
    qrBtn.innerHTML = '📱 QR Login';
    qrBtn.onclick = function() {
      document.getElementById('qrModal').classList.add('open');
      requestTikTokQR();
    };
    accountsHeader.appendChild(qrBtn);
  }
});

async function checkSession(id) {
  try {
    const res = await fetch(API + '/tiktok/check-session', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ account_id: id })
    });
    const data = await res.json();
    showToast(data.valid ? '✅ Session valid' : '❌ Session expired', data.valid ? 'success' : 'error');
    loadAccounts();
  } catch(e) { showToast('Check failed','error'); }
}

async function removeAccount(id) {
  if (!confirm('Remove account?')) return;
  try { await fetch(API + '/tiktok/accounts/'+id, {method:'DELETE'}); showToast('Removed','info'); loadAccounts(); populateAccountSelect(); }
  catch(e) { showToast('Failed','error'); }
}

function closeQrModal() { document.getElementById('qrModal').classList.remove('open'); }

async function populateAccountSelect() {
  const sel = document.getElementById('historyFilter');
  try {
    const res = await fetch(API + '/tiktok/accounts');
    const data = await res.json();
    const accounts = data.accounts || data || [];
    sel.innerHTML = '<option value="">All Accounts</option>' + accounts.map(a => `<option value="${a.id||a.username}">${a.username||a.id}</option>`).join('');
  } catch(e) {}
}

/* ═══ Upload functions (keep existing functionality) ═══ */
let batchItems = [];
function addBatchItem() { batchItems.push({}); showToast('Batch item added','info'); }
function runBatch() { showToast('Batch upload started','info'); }

async function uploadVideo() {
  try {
    const res = await fetch(API + '/tiktok/upload', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ account_id: document.getElementById('accUsername')?.value || 'test', video_path: '', caption: '' })
    });
    showToast('Upload function ready','info');
  } catch(e) { showToast('Upload failed','error'); }
}

/* ═══ History ═══ */
async function loadHistory() {
  const el = document.getElementById('historyBody');
  const filter = document.getElementById('historyFilter').value;
  try {
    let url = API + '/tiktok/published';
    if (filter) url += '?account='+filter;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();
    const items = data.published || data.videos || data || [];
    if (!items.length) { el.innerHTML = '<tr><td colspan="5" class="text-sm text-secondary" style="text-align:center;padding:32px">No published videos</td></tr>'; return; }
    el.innerHTML = items.map(v => `<tr>
      <td class="text-sm">${v.published_time || v.time || v.created_at || '-'}</td>
      <td class="text-sm" style="max-width:300px"><span class="truncate" style="display:block">${v.caption || v.description || '-'}</span></td>
      <td><span class="badge badge-indigo">${v.account || v.account_id || '-'}</span></td>
      <td><span class="badge badge-green">Published</span></td>
      <td><button class="btn btn-ghost btn-sm" onclick="showToast('Video ID: ${v.video_id || v.id || 'N/A'}','info')">View</button></td>
    </tr>`).join('');
  } catch(e) { el.innerHTML = '<tr><td colspan="5" class="text-sm text-secondary" style="text-align:center;padding:32px">Failed to load history</td></tr>'; }
}

/* ═══ Settings ═══ */
async function loadProviders() {
  const el = document.getElementById('providerList');
  try {
    const res = await fetch(API + '/video/providers');
    if (!res.ok) throw new Error('Failed');
    const data = await res.json();
    const providers = data.providers || data || [];
    el.innerHTML = '<div class="text-xs text-secondary mb-2">Available providers:</div>' +
      providers.map(p => `<div class="text-sm" style="padding:4px 0">• ${p.name || p.id || p}</div>`).join('') ||
      '<div class="text-sm">No provider data</div>';
  } catch(e) { el.innerHTML = '<div class="text-sm text-secondary">Failed to load providers</div>'; }
}

/* ═══ Side Nav Toggle ═══ */
function toggleSideNav() {
  const nav = document.getElementById('sideNav');
  const overlay = document.getElementById('sideOverlay');
  nav.classList.toggle('open');
  overlay.classList.toggle('open');
  document.body.style.overflow = nav.classList.contains('open') ? 'hidden' : '';
}

/* ═══ Refresh All ═══ */
function refreshAll() {
  loadDashboard(); loadPipeline(); loadAccounts(); loadHistory();
  showToast('Refreshed','success');
}
/* ═══ Social (Scout Targets + Clip Schedule) ═══ */

let _sSocialTargets = [];

async function renderSocial() {
  document.getElementById('socialStatus').innerHTML = '<span class="badge badge-neutral" id="socialTodayBadge">📊 กำลังโหลด...</span>';
  renderSocialTargets();
  renderSchedule();
  updateSocialBadge();
}

/* ─── Sub-tab switching ─── */
function switchSocialSub(name) {
  document.querySelectorAll('#socialTabs button').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.sub-page').forEach(p => p.classList.remove('active'));
  document.querySelector(`#socialTabs [data-subtab="${name}"]`)?.classList.add('active');
  document.getElementById('social-'+name)?.classList.add('active');
  document.getElementById('social-'+name).style.display = '';
  if (name === 'schedule') renderSchedule();
}

/* ─── Targets ─── */
async function renderSocialTargets() {
  const el = document.getElementById('socialTargetsList');
  el.innerHTML = '<div class="skeleton skeleton-line"></div>';
  try {
    const r = await rawGet('/scout/targets');
    _sSocialTargets = r.targets || [];
  } catch(e) { _sSocialTargets = []; }

  if (!_sSocialTargets.length) {
    el.innerHTML = '<div class="empty-state">📭 ยังไม่มีเป้าหมาย กด + เพิ่มเป้าหมาย</div>';
    return;
  }

  el.innerHTML = _sSocialTargets.map(t => `
    <div class="social-target-card" onclick="socialShowDetail(${t.id})">
      <div class="social-target-avatar">${(t.display_name||t.username||'?')[0].toUpperCase()}</div>
      <div class="social-target-info">
        <div class="social-target-name">${t.display_name || t.username}</div>
        <div class="social-target-meta">@${t.username}${t.niche ? ' · '+t.niche : ''} · ${t.follower_count?.toLocaleString()||0} followers · 🎬 ${t.clip_count||0} clips</div>
      </div>
      <div class="social-target-actions">
        <button class="btn btn-sm btn-ghost" onclick="event.stopPropagation();socialShowDetail(${t.id})">👁️</button>
        <button class="btn btn-sm btn-ghost" onclick="event.stopPropagation();socialDeleteTarget(${t.id})">❌</button>
      </div>
    </div>
  `).join('');
}

function showSocialAddTarget() {
  const el = document.getElementById('socialTargetForm');
  el.style.display = 'block';
  el.innerHTML = `
    <div class="card">
      <div class="card-title mb-2">+ เพิ่มเป้าหมาย</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div><label style="font-size:12px;color:var(--text-secondary)">TikTok Username</label><input id="stUser" class="inp" placeholder="username"></div>
        <div><label style="font-size:12px;color:var(--text-secondary)">Display Name</label><input id="stName" class="inp" placeholder="ชื่อร้าน"></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px">
        <div><label style="font-size:12px;color:var(--text-secondary)">Niche</label>
          <select id="stNiche" class="inp">
            <option value="product_review">Product Review</option>
            <option value="before_after">Before & After</option>
            <option value="tutorial">Tutorial</option>
            <option value="testimonial">Testimonial</option>
          </select>
        </div>
        <div><label style="font-size:12px;color:var(--text-secondary)">Followers</label><input id="stFollowers" class="inp" type="number" placeholder="0"></div>
      </div>
      <div style="margin-top:12px;display:flex;gap:8px">
        <button class="btn btn-primary btn-sm" onclick="socialSaveTarget()">💾 บันทึก</button>
        <button class="btn btn-sm" onclick="document.getElementById('socialTargetForm').style.display='none'">ยกเลิก</button>
      </div>
    </div>
  `;
}

async function socialSaveTarget() {
  const data = {
    username: document.getElementById('stUser').value.trim(),
    display_name: document.getElementById('stName').value.trim(),
    niche: document.getElementById('stNiche').value,
    follower_count: parseInt(document.getElementById('stFollowers').value) || 0,
    notes: '',
  };
  if (!data.username) { alert('กรุณากรอก Username'); return; }
  await rawPost('/scout/targets', data);
  document.getElementById('socialTargetForm').style.display = 'none';
  renderSocialTargets();
  updateSocialBadge();
}

async function socialDeleteTarget(id) {
  if (!confirm('ลบเป้าหมายนี้?')) return;
  await rawPost('/scout/targets/'+id+'/delete', {}).catch(()=>{});
  renderSocialTargets();
  updateSocialBadge();
}

async function socialShowDetail(id) {
  const r = await rawGet('/scout/targets/'+id);
  const t = r.target;
  if (!t) return;
  const clips = t.clips || [];
  const html = `
    <div class="social-target-detail">
      <div class="social-target-detail-header">
        <div class="social-target-avatar" style="width:48px;height:48px;font-size:22px">${(t.display_name||t.username)[0].toUpperCase()}</div>
        <div>
          <div style="font-weight:600;font-size:15px">${t.display_name||t.username}</div>
          <div style="font-size:12px;color:var(--text-secondary)">@${t.username}${t.niche ? ' · '+t.niche : ''} · ${t.follower_count?.toLocaleString()||0} followers</div>
        </div>
      </div>
      <div class="card-title mt-3 mb-1">🎬 Clips (${clips.length})</div>
      ${clips.length === 0 ? '<div class="empty-state" style="padding:16px">ไม่มี Clip</div>' : clips.map((c,i) => `
        <div class="social-clip-row">
          <span class="social-clip-num">#${i+1}</span>
          <span class="social-clip-caption">${c.caption?.slice(0,35)||'-'}</span>
          <span class="social-clip-stat">👁️ ${(c.views||0).toLocaleString()}</span>
          <span class="social-clip-stat">❤️ ${(c.likes||0).toLocaleString()}</span>
          <span class="social-clip-hook">${c.hook_type||'-'}</span>
          <button class="btn btn-sm btn-ghost" onclick="socialDeleteClip(${c.id})">❌</button>
        </div>
      `).join('')}
      <div style="margin-top:12px;display:flex;gap:8px">
        <button class="btn btn-sm" onclick="socialAddClipPrompt(${t.id})">+ เพิ่ม Clip</button>
        <button class="btn btn-sm btn-ghost" onclick="closeModal()">✕ ปิด</button>
      </div>
    </div>
  `;
  showModal('🎬 @'+t.username, html);
}

async function socialAddClipPrompt(targetId) {
  closeModal();
  const product = prompt('ลิงค์ TikTok:'); if (!product) return;
  const caption = prompt('แคปชั่น:'); if (!caption) return;
  const views = parseInt(prompt('Views:')) || 0;
  const hook = prompt('Hook type (problem/curiosity/benefit):') || '';
  await rawPost('/scout/targets/'+targetId+'/clips', {video_url: product.startsWith('http')?product:'', caption, views, likes: 0, hook_type: hook});
  renderSocial();
}

async function socialDeleteClip(clipId) {
  if (!confirm('ลบ Clip นี้?')) return;
  await rawPost('/scout/clips/'+clipId+'/delete', {}).catch(()=>{});
  renderSocial();
}

async function socialAnalyzeAll() {
  const ids = _sSocialTargets.map(t => t.id);
  if (!ids.length) return;
  const r = await rawPost('/scout/targets/analyze', {target_ids: ids});
  const el = document.getElementById('socialAnalyzeResult');
  el.style.display = 'block';
  el.innerHTML = `
    <div class="card">
      <div class="card-title mb-2">📊 ผลวิเคราะห์</div>
      ${(r.insights||[]).map(i => '<div style="font-size:13px;padding:3px 0">• '+i+'</div>').join('')}
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:12px">
        <div><div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px">Top Hooks</div>${(r.top_hooks||[]).map(h => '<div style="font-size:13px;display:flex;justify-content:space-between"><span>'+h.hook+'</span><span>'+h.total_views?.toLocaleString()+'</span></div>').join('')}</div>
        <div><div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px">Top Templates</div>${(r.top_templates||[]).map(h => '<div style="font-size:13px;display:flex;justify-content:space-between"><span>'+h.template+'</span><span>'+h.total_views?.toLocaleString()+'</span></div>').join('')}</div>
      </div>
      <button class="btn btn-sm btn-ghost mt-2" onclick="document.getElementById('socialAnalyzeResult').style.display='none'">✕ ปิด</button>
    </div>
  `;
}

/* ─── Schedule (Clip/day config) ─── */
async function renderSchedule() {
  let targets = _sSocialTargets;
  if (!targets.length) {
    try {
      const r = await rawGet('/scout/targets');
      targets = r.targets || [];
    } catch(e) {}
  }

  const el = document.getElementById('scheduleTargets');
  const summary = document.getElementById('scheduleSummary');

  if (!targets.length) {
    el.innerHTML = '<div class="empty-state">ยังไม่มีเป้าหมาย ไปที่ Scout Targets เพื่อเพิ่มก่อน</div>';
    summary.innerHTML = '<div style="text-align:center;padding:8px;color:var(--text-secondary)">รวม: 0 คลิป/วัน</div>';
    return;
  }

  // Load saved clip counts from localStorage
  const saved = JSON.parse(localStorage.getItem('socialClipsPerDay') || '{}');

  el.innerHTML = targets.map(t => `
    <div class="social-target-card schedule-card">
      <div class="social-target-avatar">${(t.display_name||t.username||'?')[0].toUpperCase()}</div>
      <div class="social-target-info">
        <div class="social-target-name">${t.display_name || t.username}</div>
        <div class="social-target-meta">@${t.username}</div>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <label style="font-size:12px;color:var(--text-secondary);white-space:nowrap">🎬</label>
        <input class="inp clip-count-input" type="number" min="0" max="20" value="${saved[t.id] || 2}"
          data-target-id="${t.id}" data-username="${t.username}" style="width:60px;text-align:center"
          onchange="socialUpdateClipCount(this)">
        <span style="font-size:12px;color:var(--text-secondary)">/ วัน</span>
      </div>
    </div>
  `).join('');

  socialUpdateSummary();
}

function socialUpdateClipCount(input) {
  const id = input.dataset.targetId;
  const val = parseInt(input.value) || 0;
  const saved = JSON.parse(localStorage.getItem('socialClipsPerDay') || '{}');
  if (val <= 0) { delete saved[id]; }
  else { saved[id] = val; }
  localStorage.setItem('socialClipsPerDay', JSON.stringify(saved));
  socialUpdateSummary();
  updateSocialBadge();
}

function socialUpdateSummary() {
  const saved = JSON.parse(localStorage.getItem('socialClipsPerDay') || '{}');
  const total = Object.values(saved).reduce((a,b) => a + b, 0);
  const targetCount = Object.keys(saved).length;
  const el = document.getElementById('scheduleSummary');
  el.innerHTML = `
    <div style="display:flex;justify-content:space-around;text-align:center">
      <div><div style="font-size:24px;font-weight:700">${targetCount}</div><div style="font-size:12px;color:var(--text-secondary)">Targets</div></div>
      <div><div style="font-size:24px;font-weight:700">${total}</div><div style="font-size:12px;color:var(--text-secondary)">คลิป/วัน</div></div>
      <div><div style="font-size:24px;font-weight:700" id="socialTodayGenerated">0</div><div style="font-size:12px;color:var(--text-secondary)">สร้างวันนี้</div></div>
    </div>
  `;
}

async function updateSocialBadge() {
  const saved = JSON.parse(localStorage.getItem('socialClipsPerDay') || '{}');
  const total = Object.values(saved).reduce((a,b) => a + b, 0);
  const el = document.getElementById('socialTodayBadge');
  if (el) {
    el.innerHTML = total > 0
      ? `🎯 ${total} คลิป/วัน · ${_sSocialTargets.length} Targets`
      : '📊 ยังไม่ได้ตั้งค่า';
  }
}

/* ─── Social helpers ─── */
async function rawGet(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error(r.status);
  return r.json();
}
async function rawPost(path, data) {
  const r = await fetch(API + path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data||{})});
  if (!r.ok) throw new Error(r.status);
  return r.json();
}
function closeModal() {
  const el = document.getElementById('modalOverlay');
  if (el) {
    const media = el.querySelectorAll('video, audio');
    media.forEach(m => { try { m.pause(); m.currentTime = 0; m.src = ''; } catch(e){} });
    el.remove();
  }
}
function showModal(title, bodyHtml) {
  const existing = document.getElementById('modalOverlay');
  if (existing) existing.remove();
  const overlay = document.createElement('div');
  overlay.id = 'modalOverlay';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;display:flex;align-items:center;justify-content:center;padding:16px';
  overlay.innerHTML = `
    <div style="background:var(--bg-primary);border-radius:var(--radius-xl);padding:24px;max-width:560px;width:100%;max-height:80vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,.3)">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h3 style="font-size:16px">${title}</h3>
        <button onclick="closeModal()" style="border:none;background:none;font-size:20px;cursor:pointer;padding:4px 8px">✕</button>
      </div>
      <div>${bodyHtml}</div>
    </div>
  `;
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
}

/* ═══ Init ═══ */
document.addEventListener('DOMContentLoaded', () => {
  // Dark mode
  if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark-mode');
  }

  // Set connection status
  fetch(API + '/health').then(r => {
    if (r.ok) { document.getElementById('connStatus').className = 'status-dot online'; document.getElementById('sideConnStatus').className = 'status-dot online'; }
  }).catch(() => { document.getElementById('connStatus').className = 'status-dot offline'; document.getElementById('sideConnStatus').className = 'status-dot offline'; });

  // Init default aspect ratio
  sessionStorage.setItem('aspectRatio', '9:16');

  // Initial loads
  loadDashboard(); loadAccounts(); populateAccountSelect(); loadProviders(); autoInitSheets(); loadRecipes();
  
  // Restore Auto Pipeline settings
  var savedMode = localStorage.getItem('autoPipelineMode');
  if (savedMode) {
    var modeEl = document.querySelector('.auto-pipeline-modes .mode-card[data-mode="' + savedMode + '"]');
    if (modeEl) selectAutoMode(modeEl);
  }
  var savedSettings = localStorage.getItem('autoPipelineSettings');
  if (savedSettings) {
    try {
      var s = JSON.parse(savedSettings);
      if (s.platforms) {
        document.querySelectorAll('#autoPfmPlatforms input[type="checkbox"]').forEach(function(c){
          c.checked = s.platforms.indexOf(c.value) !== -1;
        });
      }
      if (s.dailyCount) document.getElementById('autoDailyCount').value = s.dailyCount;
      if (s.postTime) document.getElementById('autoPostTime').value = s.postTime;
      if (s.productSource) document.getElementById('autoProductSource').value = s.productSource;
    } catch(e){}
  }
});
/* Products (Analyzer) */

/** Search products by name — queries tus_products.db */
async function searchProducts() {
  const q = document.getElementById('productSearchInput').value.trim();
  const grid = document.getElementById("productGrid");
  const resultInfo = document.getElementById("productSearchResults");
  
  if (!q) {
    // No query = load all
    resultInfo.textContent = '';
    loadAnalyzedProducts();
    return;
  }
  
  grid.innerHTML = '<div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line"></div>';
  resultInfo.textContent = '🔍 กำลังค้นหา "' + q + '"...';
  
  try {
    const encQ = encodeURIComponent(q);
    // Query both APIs in parallel
    
      	const r1 = await fetch(API + '/products/list?limit=50&search=' + encQ);

    const d1 = await r1.json();
    
    const analyzed = d1.products || [];
    
    // Update stats for analyzed (components may be hidden)
    const elProdTotal = document.getElementById("prodTotal");
    if (elProdTotal) elProdTotal.textContent = analyzed.length;
    const avg = analyzed.length ? Math.round(analyzed.reduce((a,p) => a + (p.commission_rate||0), 0) / analyzed.length) : 0;
    const elAvg = document.getElementById("prodAvgComm");
    if (elAvg) elAvg.textContent = avg + "%";
    const maxc = analyzed.length ? Math.max(...analyzed.map(p => p.commission_rate||0)) : 0;
    const elMax = document.getElementById("prodTopComm");
    if (elMax) elMax.textContent = maxc + "%";
    const ts = analyzed.length ? analyzed.reduce((a,p) => a + (p.sold_total||0), 0).toLocaleString() : "0";
    const elSold = document.getElementById("prodTotalSold");
    if (elSold) elSold.textContent = ts;
    
resultInfo.textContent = '🔍 พบ ' + analyzed.length + ' รายการ สำหรับ "' + q + '"';
    
    // Render analyzed
    if (!analyzed.length) {
      grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1">😕 ไม่พบสินค้าใน TUS Products</div>';
    } else {
      grid.innerHTML = analyzed.map(p => {
        const img = safeProductImage(p);
        const comm = p.commission_rate || 0;
        const sold = p.sold_total || 0;
        const price = p.price_thb || 0;
        const enc = encodeURIComponent(JSON.stringify(p));
        const imgHtml = img ? `<img class="product-card-img" src="${img}" alt="" loading="lazy" onerror="this.style.display='none'">` : '<div class="product-card-img" style="display:flex;align-items:center;justify-content:center;color:var(--text-tertiary);font-size:32px">📦</div>';
        const pUrl = p.url || "";
        var batchData = {enc:enc, title:p.title||'Unknown', image:img, url:p.url||''};
        return `<div class="product-card"><div class="product-card-checkbox" style="left:5px;top:5px"><input type="checkbox" onchange="toggleBatchSelect(this, ${JSON.stringify(batchData).replace(/'/g,"\\'")})"></div><div style="flex:0 0 100%;padding:0 16px;min-width:0"><div class="product-card-title" style="margin-bottom:4px;font-size:13.5px;font-weight:700;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;word-break:break-word;cursor:pointer" onclick="useProduct('${enc}')">${p.title || "Unknown"}</div></div><div style="margin-left:14px">${imgHtml}</div><div class="product-card-body" onclick="useProduct('${enc}')" style="margin-left:4px;cursor:pointer"><div style="display:flex;align-items:center;gap:12px;font-size:12px;color:var(--text-secondary)"><span style="font-weight:800;color:var(--brand);font-size:14.5px">฿${Number(price).toLocaleString()}</span><span class="badge badge-green" style="font-size:10px">💰 ${comm}%</span><span style="font-size:11px">🔥 ขายแล้ว ${sold.toLocaleString()} ชิ้น</span></div><div style="display:flex;align-items:center;gap:6px;margin-top:2px;flex-wrap:wrap"><span class="badge" style="font-size:10.5px;background:rgba(99,102,241,0.16);color:#a5b4fc;font-weight:700">🆔 ${p.product_id||"-"}</span><span class="badge" style="font-size:10.5px;background:rgba(236,72,153,0.16);color:#f9a8d4;font-weight:600">👤 ${p.gender || "ทุกเพศ"}</span><span class="badge" style="font-size:10.5px;background:rgba(249,115,22,0.16);color:#fdba74;font-weight:600">🎯 ${p.target_age || "ทุกวัย"}</span></div><div style="display:flex;align-items:center;gap:6px;margin-top:2px"><span class="badge" style="font-size:10px;background:rgba(255,255,255,0.06)">🥫 ${p.container_type||"ขวดมาตรฐาน"}</span><span class="badge" style="font-size:10px;background:rgba(255,255,255,0.06)">🔒 ${p.closure_type||"ฝามาตรฐาน"}</span></div></div><div class="product-card-actions" style="margin-left:auto"><button class="btn btn-primary btn-sm" style="background:linear-gradient(135deg, var(--brand), var(--accent-purple));border:none" onclick="event.stopPropagation();useProduct('${enc}')">🎬 สร้างคลิป</button></div></div>`;
      }).join("");
    }
    
  } catch(e) {
    grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1">Error: ' + e.message + '</div>';
    resultInfo.textContent = '❌ Error: ' + e.message;
  }
}

function safeProductImage(p) {
  const imgs = p.images || [];
  if (!imgs.length) return null;
  const first = imgs[0];
  const fn = String(first).split('/').pop() || '';
  const expected = String(p.product_id || '') + '.jpg';
  return fn === expected ? first : null;
}

async function loadAnalyzedProducts() {
  const grid = document.getElementById("productGrid");
  if (!grid) return;
  grid.innerHTML = '<div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line"></div>';
  try {
    const r = await fetch(API + "/products/list?limit=50&preset=all");
    if (!r.ok) throw new Error("API Error");
    const d = await r.json();
    const products = d.products || [];
    // Update stats (components may be hidden)
    const elProdTotal = document.getElementById("prodTotal");
    if (elProdTotal) elProdTotal.textContent = products.length;
    const avg = products.length ? Math.round(products.reduce((a,p) => a + (p.commission_rate||0), 0) / products.length) : 0;
    const elAvg = document.getElementById("prodAvgComm");
    if (elAvg) elAvg.textContent = avg + "%";
    const maxc = products.length ? Math.max(...products.map(p => p.commission_rate||0)) : 0;
    const elMax = document.getElementById("prodTopComm");
    if (elMax) elMax.textContent = maxc + "%";
    const ts = products.length ? products.reduce((a,p) => a + (p.sold_total||0), 0).toLocaleString() : "0";
    const elSold = document.getElementById("prodTotalSold");
    if (elSold) elSold.textContent = ts;
    if (!products.length) { grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1">No products</div>'; return; }
    grid.innerHTML = products.map(p => {
      const img = safeProductImage(p);
      const comm = p.commission_rate || 0;
      const sold = p.sold_total || 0;
      const price = p.price_thb || 0;
      const enc = encodeURIComponent(JSON.stringify(p));
      const imgHtml = img ? `<img class="product-card-img" src="${img}" alt="" loading="lazy" onerror="this.style.display=\'none\'">` : '<div class="product-card-img" style="display:flex;align-items:center;justify-content:center;color:var(--text-tertiary);font-size:32px">\ud83d\udce6</div>';
      const pUrl = p.url || "";
      const imgCount = p.image_count || (p.images ? p.images.length : 0);
      return `<div class="product-card"><div class="product-card-checkbox"><input type="checkbox" data-enc="${enc}" onchange="toggleBatchSelect(this)"></div><div style="flex:0 0 100%;padding:0 16px;min-width:0"><div class="product-card-title" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;word-break:break-word;cursor:pointer" onclick="useProduct('${enc}')">${p.title || "Unknown"}</div></div>${imgHtml}<div class="product-card-body" onclick="useProduct('${enc}')"><div class="product-card-meta"><span class="product-card-price">฿${Number(price).toLocaleString()}</span><span class="product-card-comm">💰 ${comm}%</span><span class="product-card-platform">${p.source || "tiktok"}</span></div><div class="product-card-sold">🔥 Sold ${sold.toLocaleString()} pcs ${imgCount ? '· 📸 ' + imgCount + ' รูป' : ''}</div><div class="product-card-sold" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:2px"><span class="badge" style="font-size:10.5px;background:rgba(99,102,241,0.16);color:#a5b4fc;font-weight:700">🆔 ${p.product_id||"-"}</span><span class="badge" style="font-size:10.5px;background:rgba(236,72,153,0.16);color:#f9a8d4;font-weight:600">👤 ${p.gender || "ทุกเพศ"}</span><span class="badge" style="font-size:10.5px;background:rgba(249,115,22,0.16);color:#fdba74;font-weight:600">🎯 ${p.target_age || "ทุกวัย"}</span></div><div class="product-card-footer"><span class="text-xs text-secondary truncate" style="max-width:80px;flex-shrink:1">${pUrl}</span><button class="btn btn-primary btn-sm" onclick="event.stopPropagation();useProduct('${enc}')">🎬 Create Video</button></div></div></div>`;
    }).join("");
  } catch(e) { grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1">Error: ' + e.message + '</div>'; }
}

function useProduct(jsonEncoded) {
  try {
    const p = JSON.parse(decodeURIComponent(jsonEncoded));
    document.getElementById("productUrl").value = p.url || "";
    document.getElementById("productTitle").value = p.title || "";
    document.getElementById("productDetails").value = (p.description_th || p.description || "");

    if (p.ugc_style) {
      const sel = "#styleModalGrid .style-card" + (p.ugc_style === "holding" ? ".selected" : "[data-style=\x27" + p.ugc_style + "\x27]");
      const el = document.querySelector(sel);
      if (el) selectStyleFromModal(el, p.ugc_style);
    }
    if (p.images && p.images[0]) {
      const img = p.images[0];
      uploadedImages.product = img.startsWith("http") ? img : window.location.origin + img;
      const zone = document.getElementById("productImgZone");
      const pl = document.getElementById("productImgPlaceholder");
      zone.classList.add("has-image");
      pl.innerHTML = "<img class=\"preview\" src=\"" + p.images[0] + "\" alt=\"product\"><button class=\"remove-img\" onclick=\"event.stopPropagation();removeImage(\x27product\x27)\">✕</button>";
    }
    switchTab("content");
    goContentStep(1);
    showToast("✅ " + (p.title || "").slice(0,40), "success");
  } catch(e) { showToast("Error: " + e.message, "error"); }
}

let lightboxIndex = -1;

async function loadAssets(type) {
  currentAssetFilter = type || 'all';
  const gallery = document.getElementById('assetGallery');
  if (!gallery) return;
  gallery.innerHTML = '<div class="skeleton skeleton-line" style="height:200px"></div><div class="skeleton skeleton-line" style="height:200px"></div><div class="skeleton skeleton-line" style="height:200px"></div><div class="skeleton skeleton-line" style="height:200px"></div>';

  try {
    const resp = await fetch(API + '/pipeline/assets');
    const data = await resp.json();
    if (!data.success) throw new Error(data.error || 'Failed to load assets');

    cachedAssets = data;
    renderAssets(currentAssetFilter);
  } catch (e) {
    gallery.innerHTML = '<div class="asset-empty"><div class="icon">⚠️</div><div class="msg">Could not load assets</div><div class="hint">' + e.message + '</div></div>';
  }
}

function filterAssets(type) {
  currentAssetFilter = type;
  document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
  document.querySelector('.filter-tab[data-asset-type="' + type + '"]')?.classList.add('active');
  renderAssets(type);
}

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '-';
  const kb = bytes / 1024;
  if (kb < 1024) return kb.toFixed(1) + ' KB';
  return (kb / 1024).toFixed(1) + ' MB';
}

function renderAssets(type) {
  const gallery = document.getElementById('assetGallery');
  if (!gallery) return;

  let items = [];
  if (type === 'all' || type === 'images') {
    items = items.concat((cachedAssets.images || []).map(i => ({ ...i, _type: 'image' })));
  }
  if (type === 'all' || type === 'videos') {
    items = items.concat((cachedAssets.videos || []).map(v => ({ ...v, _type: 'video' })));
  }

  // Update stats
  const imgCount = (cachedAssets.images || []).length;
  const vidCount = (cachedAssets.videos || []).length;
  document.getElementById('assetImgCount').textContent = imgCount;
  document.getElementById('assetVidCount').textContent = vidCount;
  document.getElementById('assetTotalCount').textContent = imgCount + vidCount;

  if (items.length === 0) {
    gallery.innerHTML = '<div class="asset-empty"><div class="icon">📂</div><div class="msg">No assets yet</div><div class="hint">Generate some content first!</div></div>';
    return;
  }

  // Sort by date descending
  items.sort((a, b) => (b.created || '').localeCompare(a.created || ''));

  lightboxItems = items;

  gallery.innerHTML = items.map((item, idx) => {
    const isVideo = item._type === 'video';
    const url = item.url || '/tiktok/storage/' + item.path;
    const ext = (item.name || '').split('.').pop().toLowerCase();
    const isVideoExt = ['mp4', 'mov', 'webm', 'gif'].includes(ext);
    const showPlay = isVideo || isVideoExt;
    const badgeIcon = showPlay ? '🎬' : '📷';
    const created = timeSince(item.created);
    const size = formatSize(item.size);

    return '<div class="asset-card" onclick="openAssetLightbox(' + idx + ')">'
      + '<div class="asset-thumb">'
      + (showPlay
        ? '<video src="' + url + '" muted preload="metadata" style="width:100%;height:100%;object-fit:cover;pointer-events:none"></video>'
        : '<img src="' + url + '" alt="' + (item.name || '') + '" loading="lazy" onerror="this.style.display=\'none\'" crossorigin="anonymous">'
      )
      + (showPlay ? '<div class="asset-play-overlay">▶️</div>' : '')
      + '<span class="asset-type-badge">' + badgeIcon + '</span>'
      + '</div>'
      + '<div class="asset-info">'
      + '<div class="asset-name" title="' + (item.name || '') + '">' + (item.name || '') + '</div>'
      + '<div class="asset-meta">' + size + ' · ' + created + '</div>'
      + '</div>'
      + '</div>';
  }).join('');
}

function openAssetLightbox(idx) {
  lightboxIndex = idx;
  const item = lightboxItems[idx];
  if (!item) return;

  const url = item.url || '/tiktok/storage/' + item.path;
  const ext = (item.name || '').split('.').pop().toLowerCase();
  const isVideo = item._type === 'video' || ['mp4', 'mov', 'webm'].includes(ext);

  const content = document.getElementById('lightboxContent');
  if (isVideo) {
    content.innerHTML = '<video src="' + url + '" controls autoplay style="max-width:100%;max-height:90vh;border-radius:var(--radius-xl);display:block"></video>';
  } else {
    content.innerHTML = '<img src="' + url + '" alt="' + (item.name || '') + '" style="max-width:100%;max-height:90vh;object-fit:contain;display:block">';
  }

  document.getElementById('lightboxCaption').textContent = (item.name || '') + ' · ' + formatSize(item.size);

  // Show/hide prev/next
  document.getElementById('lightboxPrev').style.display = idx > 0 ? 'flex' : 'none';
  document.getElementById('lightboxNext').style.display = idx < lightboxItems.length - 1 ? 'flex' : 'none';

  document.getElementById('assetLightbox').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeAssetLightbox(e) {
  if (e && e.target !== e.currentTarget) return;
  var contentEl = document.getElementById('lightboxContent');
  if (contentEl) { var vids = contentEl.querySelectorAll('video, audio'); vids.forEach(function(v) { try { v.pause(); v.removeAttribute('src'); } catch(e) {} }); }
  document.getElementById('assetLightbox').classList.remove('open');
  document.body.style.overflow = '';
  if (contentEl) { contentEl.innerHTML = ''; }
}

function navigateLightbox(dir) {
  const next = lightboxIndex + dir;
  if (next < 0 || next >= lightboxItems.length) return;
  openAssetLightbox(next);
}

// Keyboard navigation
document.addEventListener('keydown', function(e) {
  if (!document.getElementById('assetLightbox')?.classList.contains('open')) return;
  if (e.key === 'Escape') closeAssetLightbox();
  if (e.key === 'ArrowLeft') navigateLightbox(-1);
  if (e.key === 'ArrowRight') navigateLightbox(1);
});

/* ═══ Post For Me — JS ═══ */
const PFM_API = window.location.origin + '/api/tiktok';

// AitoEarn platform cache
let _aePlatforms = [];
let _aeAccounts = [];

async function aeFetchStatus() {
  try {
    const r = await fetch(PFM_API + '/aitoearn/status');
    const d = await r.json();
    _aePlatforms = d.platforms || [];
    _aeAccounts = [];
    _aePlatforms.forEach(function(p){ _aeAccounts = _aeAccounts.concat(p.accounts||[]); });
    return d;
  } catch(e) { return {connected:false, error:e.message}; }
}

// Platform brand data — colors, icons, display names
const PFM_BRANDS = {
  tiktok:     { color:'#ff0050', icon:'🎵', name:'TikTok', bg:'linear-gradient(135deg, #ff0050, #00f2ea)' },
  tiktok_local:{ color:'#ff0050', icon:'🔑', name:'TikTok Local', bg:'linear-gradient(135deg, #333, #666)' },
  youtube:    { color:'#ff0000', icon:'▶️', name:'YouTube', bg:'linear-gradient(135deg, #cc0000, #ff0000)' },
  twitter:    { color:'#1da1f2', icon:'𝕏', name:'X (Twitter)', bg:'linear-gradient(135deg, #000, #1da1f2)' },
  x:          { color:'#1da1f2', icon:'𝕏', name:'X', bg:'linear-gradient(135deg, #000, #555)' },
  facebook:   { color:'#1877f2', icon:'📘', name:'Facebook', bg:'linear-gradient(135deg, #0d6efd, #1877f2)' },
  instagram:  { color:'#e4405f', icon:'📷', name:'Instagram', bg:'linear-gradient(135deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888)' },
  linkedin:   { color:'#0a66c2', icon:'💼', name:'LinkedIn', bg:'linear-gradient(135deg, #0a66c2, #0077b5)' },
  pinterest:  { color:'#e60023', icon:'📌', name:'Pinterest', bg:'linear-gradient(135deg, #bd081c, #e60023)' },
  threads:    { color:'#000', icon:'🧵', name:'Threads', bg:'linear-gradient(135deg, #000, #333)' },
  tiktok_business:{ color:'#ff0050', icon:'💼', name:'TikTok Biz', bg:'linear-gradient(135deg, #333, #ff0050)' },
};

// Platform SVG logos (loaded from external file)
const PFM_PLATFORMS = {
  tiktok: { icon:'🎵', name:'TikTok' },
  tiktok_local: { icon:'🔑', name:'TikTok (Local)' },
  tiktok_business: { icon:'💼', name:'TikTok Business' },
  facebook: { icon:'📘', name:'Facebook' },
  instagram: { icon:'📷', name:'Instagram' },
  x: { icon:'𝕏', name:'X (Twitter)' },
  linkedin: { icon:'💼', name:'LinkedIn' },
  youtube: { icon:'▶️', name:'YouTube' },
  pinterest: { icon:'📌', name:'Pinterest' },
  threads: { icon:'🧵', name:'Threads' }
};

let pfmConnectPlatform = 'tiktok';
let pfmConnectPopup = null;
let pfmConnectInterval = null;
let pfmDetailAccountId = null;

// Load SVG logos from external file
!function(){var s=document.createElement('script');s.src='/tiktok/svg-platforms.js?'+Date.now();document.head.appendChild(s)}();

function pfmSwitchTab(name) {
  document.querySelectorAll('.pfm-tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.pfm-pane').forEach(p => p.style.display = 'none');
  document.querySelector(`.pfm-tab-btn[data-tab="${name}"]`)?.classList.add('active');
  document.getElementById('pfm-'+name).style.display = 'block';
}

async function pfmFetch(url, opts={}) {
  try {
    const r = await fetch(PFM_API + url, { headers: {'Content-Type':'application/json', ...opts.headers}, ...opts });
    return await r.json();
  } catch(e) { return {success:false, error: e.message}; }
}

// ─── Publisher: Completed Videos from TUS ───────────────────

// ─── Publisher: Video Preview Modal ─────────────────────────
function pubOpenVideoModal(videoUrl, jobId, productName, title, description, hashtags, style, duration) {
  var overlay = document.getElementById('pub-video-modal');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'pub-video-modal';
    overlay.className = 'modal-overlay';
    overlay.style.cssText = 'z-index:200';
    overlay.onclick = function(e) { if (e.target === this) { var v=document.getElementById('pub-modal-video'); if(v)v.pause(); this.style.display = 'none'; } };
    overlay.innerHTML = 
      '<div class="modal" style="max-width:440px;padding:0;background:#000;border-radius:16px;overflow:hidden;position:relative">' +
      '<button onclick="var m=document.getElementById(\'pub-video-modal\');var v=document.getElementById(\'pub-modal-video\');if(v)v.pause();m.style.display=\'none\'" style="position:absolute;top:10px;right:10px;z-index:20;background:rgba(0,0,0,0.7);color:#fff;border:2px solid rgba(255,255,255,0.3);border-radius:50%;width:34px;height:34px;font-size:16px;cursor:pointer;line-height:1;display:flex;align-items:center;justify-content:center">✕</button>' +
      '<video id="pub-modal-video" controls autoplay style="width:100%;max-height:60vh;display:block"></video>' +
      '<div id="pub-modal-info" style="padding:14px 16px;background:var(--bg-secondary);color:var(--text-primary)"></div>' +
      '</div>';
    document.body.appendChild(overlay);
  }
  document.getElementById('pub-modal-video').src = videoUrl;
  
  var styleMap = {holding_product:'🤳 ถือสินค้า',product_usage:'✨ ใช้สินค้า',ugc_review:'📝 รีวิว',ugc:'🎬 ทั่วไป',talking_head:'🗣️ พูดกล้อง',unboxing:'📦 แกะกล่อง'};
  var displayTitle = title || productName || 'Untitled';
  var htagsHtml = '';
  if (hashtags && hashtags.length) {
    htagsHtml = '<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px">' + hashtags.slice(0,8).map(function(t){ return '<span style="font-size:10px;background:rgba(59,130,246,0.15);color:#60a5fa;padding:2px 8px;border-radius:10px">#' + t.replace(/^#/,'') + '</span>'; }).join('') + '</div>';
  }
  var descHtml = '';
  if (description) {
    descHtml = '<div style="font-size:11px;color:var(--text-secondary);margin-top:6px;line-height:1.5;max-height:60px;overflow-y:auto">' + escapeHtml(description) + '</div>';
  }
  document.getElementById('pub-modal-info').innerHTML =
    '<div style="font-size:15px;font-weight:700;margin-bottom:2px">' + escapeHtml(displayTitle) + '</div>' +
    '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap">' +
    '<span style="font-size:10px;font-family:mono;color:var(--text-tertiary)">#' + escapeHtml(jobId) + '</span>' +
    (style ? '<span style="font-size:10px;color:var(--text-secondary);background:var(--bg-tertiary);padding:1px 6px;border-radius:8px">' + (styleMap[style] || style) + '</span>' : '') +
    (duration ? '<span style="font-size:10px;color:var(--text-tertiary)">🕐 ' + duration + 's</span>' : '') +
    '</div>' +
    descHtml +
    htagsHtml +
    '<div style="display:flex;gap:6px;margin-top:10px">' +
    '<button class="btn btn-primary btn-sm" onclick="pubPostNow(' + JSON.stringify(jobId).replace(/"/g,'&quot;') + ', ' + JSON.stringify(productName).replace(/"/g,'&quot;') + ')" style="flex:1;font-size:12px">🚀 Post Now</button>' +
    '<button class="btn btn-secondary btn-sm" onclick="pubSchedule(' + JSON.stringify(jobId).replace(/"/g,'&quot;') + ', ' + JSON.stringify(productName).replace(/"/g,'&quot;') + ')" style="flex:1;font-size:12px">📅 Schedule</button>'
    '</div>';
  overlay.style.display = 'flex';
}

async function loadPublisherVideos() {
  var grid = document.getElementById('pub-videos-grid');
  if (!grid) return;
  grid.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:32px">⏳ Loading completed videos...</div>';
  
  // Fetch AitoEarn accounts first (for platform info)
  await aeFetchStatus();
  
  try {
    var r = await fetch(API + '/video/completed');
    var d = await r.json();
    var jobs = d.jobs || [];
    
    if (!jobs.length) {
      grid.innerHTML = '<div style="text-align:center;padding:48px;color:var(--text-tertiary)"><div style="font-size:48px;margin-bottom:12px">📭</div><div>No completed videos yet</div><div style="font-size:12px;margin-top:4px">Generate videos in the Studio tab first</div></div>';
      return;
    }
    
    grid.innerHTML = '';
    
    var scIcons = {
      holding_product: '🤳', product_usage: '✨', ugc_review: '📝',
      talking_head: '🗣️', ugc: '🎬', unboxing: '📦'
    };
    
    jobs.forEach(function(job) {
      var vid = job.video_url || '';
      var name = job.title || job.product_name || 'Untitled';
      var htags = job.hashtags || [];
      var dur = job.duration || 8;
      var style = job.style || job.ugc_style || 'ugc';
      var styleLabel = {holding_product:'ถือสินค้า',product_usage:'ใช้สินค้า',ugc_review:'รีวิว',ugc:'ทั่วไป',talking_head:'พูดกล้อง',unboxing:'แกะกล่อง'}[style] || style;
      var styleIcon = scIcons[style] || '🎬';
      var jobId = job.job_id || '';
      var cost = job.cost ? ('$' + job.cost.toFixed(3)) : '—';
      var size = job.size_mb ? (job.size_mb + 'MB') : '';
      var created = job.created || '';
      var vidSrc = vid.startsWith('http') ? vid : (window.location.origin + vid);
      
      // Get platform brand info (default TikTok)
      var plat = 'tiktok';
      var brand = PFM_BRANDS[plat] || PFM_BRANDS['tiktok'];
      var platSvg = window.PLATFORM_SVGS && window.PLATFORM_SVGS[plat] ? window.PLATFORM_SVGS[plat] : brand.icon;
      
      var card = document.createElement('div');
      card.style.cssText = 'background:var(--bg-secondary);border:1px solid var(--border-primary);border-radius:12px;overflow:hidden;transition:all 0.2s ease;display:flex;flex-direction:column';
      card.onmouseenter = function(){ this.style.borderColor='var(--brand)'; this.style.boxShadow='0 4px 16px rgba(0,0,0,0.12)'; };
      card.onmouseleave = function(){ this.style.borderColor='var(--border-primary)'; this.style.boxShadow='none'; };
      
      // ── Card Layout ──
      var inner = '';
      
      // Top bar: Job ID + platform icon + duration
      inner += '<div style="padding:8px 14px;background:var(--bg-tertiary);display:flex;align-items:center;justify-content:space-between;gap:8px">';
      inner += '<div style="display:flex;align-items:center;gap:8px;min-width:0">';
      inner += '<span style="font-family:mono;font-size:10px;color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">#' + escapeHtml(jobId) + '</span>';
      inner += '<span style="display:inline-flex;align-items:center;flex-shrink:0">' + platSvg + '</span>';
      inner += '</div>';
      inner += '<span style="font-size:10px;color:var(--text-secondary);white-space:nowrap;flex-shrink:0">🕐 ' + dur + 's</span>';
      inner += '</div>';
      
      // Body: Thumbnail left + Details right
      inner += '<div style="display:flex;padding:12px;gap:12px;flex:1">';
      
      // Thumbnail
      var thumbW = 100;
      var titleSafe = job.title || '';
      var descSafe = job.description || '';
      var onclickModal = "pubOpenVideoModal(" + JSON.stringify(vidSrc) + "," + JSON.stringify(jobId) + "," + JSON.stringify(name) + "," + JSON.stringify(titleSafe) + "," + JSON.stringify(descSafe) + "," + JSON.stringify(htags) + "," + JSON.stringify(style) + "," + dur + ")";
      // Escape "!important" -> &quot; for HTML attribute safety
      onclickModal = onclickModal.replace(/"/g, '&quot;');
      inner += '<div style="width:' + thumbW + 'px;flex-shrink:0;border-radius:8px;overflow:hidden;aspect-ratio:9/16;background:var(--bg-tertiary);cursor:pointer;position:relative" onclick="' + onclickModal + '">';
      if (vid) {
        inner += '<video src="' + vid + '" muted preload="metadata" style="width:100%;height:100%;object-fit:cover;pointer-events:none"></video>';
        inner += '<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.2);transition:opacity 0.2s;opacity:0" onmouseenter="this.style.opacity=\'1\'" onmouseleave="this.style.opacity=\'0\'"><span style="font-size:28px">▶️</span></div>';
        // Product name overlay
        if (job.product_name) {
          inner += '<div style="position:absolute;bottom:0;left:0;right:0;background:linear-gradient(transparent,rgba(0,0,0,0.7));padding:16px 6px 4px;font-size:9px;font-weight:600;color:#fff;text-align:center;line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + escapeHtml(job.product_name.substring(0,30)) + '</div>';
        }
      } else {
        inner += '<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:28px">🎬</div>';
      }
      inner += '</div>';
      
      // Details
      inner += '<div style="flex:1;min-width:0;display:flex;flex-direction:column;justify-content:space-between">';
      // Product name (2 lines)
      inner += '<div>';
      inner += '<div style="font-size:13px;font-weight:700;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:6px" title="' + escapeHtml(name) + '">' + escapeHtml(name) + '</div>';
      // Style badge + meta
      inner += '<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px">';
      inner += '<span style="font-size:10px;background:var(--bg-tertiary);padding:2px 7px;border-radius:10px;color:var(--text-secondary)">' + styleIcon + ' ' + styleLabel + '</span>';
      if (size) inner += '<span style="font-size:10px;color:var(--text-tertiary)">' + size + '</span>';
      if (created) inner += '<span style="font-size:10px;color:var(--text-tertiary)">' + created + '</span>';
      inner += '</div>';
      // Cost
      inner += '<div style="font-size:10px;color:var(--text-tertiary);margin-bottom:4px">💰 ' + cost + '</div>';
      // Hashtags (if available)
      if (htags.length) {
        inner += '<div style="font-size:9px;color:var(--brand);margin-bottom:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%">';
        inner += htags.slice(0,5).map(function(t){ return '#' + t.replace(/^#/,''); }).join(' ');
        if (htags.length > 5) inner += ' ...';
        inner += '</div>';
      }
      // Action buttons (wrap safely, compact padding)
      inner += '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:auto;padding-top:4px">';
      inner += '<button class="btn btn-primary btn-sm" onclick="pubPostNow(' + JSON.stringify(jobId).replace(/"/g,'&quot;') + ', ' + JSON.stringify(name).replace(/"/g,'&quot;') + ')" style="flex:1;min-width:90px;font-size:11px;padding:4px 8px;white-space:nowrap">🚀 Post Now</button>';
      inner += '<button class="btn btn-secondary btn-sm" onclick="pubSchedule(' + JSON.stringify(jobId).replace(/"/g,'&quot;') + ', ' + JSON.stringify(name).replace(/"/g,'&quot;') + ')" style="flex:1;min-width:90px;font-size:11px;padding:4px 8px;white-space:nowrap">📅 Schedule</button>';
      inner += '</div>';
      inner += '</div>';
      
      inner += '</div>'; // end body
      
      card.innerHTML = inner;
      grid.appendChild(card);
    });
  } catch(e) {
    grid.innerHTML = '<div style="text-align:center;padding:32px;color:var(--color-red-400)">❌ Error: ' + e.message + '</div>';
  }
}

// ─── Publisher: Post Now ────────────────────────────────────

// ─── Publisher: Platform helpers ───────────────────────────────

function getBatchPlatforms() {
  var checks = document.querySelectorAll('#batch-platforms input[type="checkbox"]:checked');
  var platforms = [];
  checks.forEach(function(c){ platforms.push(c.value); });
  return platforms.length ? platforms : ['tiktok'];
}

function getCardPlatform(jobId) {
  var sel = document.getElementById('plat-' + jobId);
  return sel ? sel.value : 'tiktok';
}

// ─── Publisher: Post Now ────────────────────────────────────

async function pubPostNow(jobId, productName) {
  var r, vid;
  try {
    r = await fetch(API + '/video/completed');
    var d = await r.json();
    vid = (d.jobs||[]).find(function(j){ return j.job_id === jobId; });
  } catch(e) {}
  
  if (!vid || !vid.video_url) { alert('Video not found'); return; }
  
  var overlay = document.getElementById('pub-postnow-modal');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'pub-postnow-modal';
    overlay.className = 'modal-overlay';
    overlay.style.cssText = 'z-index:200';
    overlay.onclick = function(e) { if (e.target === this) this.style.display = 'none'; };
    overlay.innerHTML =
      '<div onclick="event.stopPropagation()" style="background:var(--bg-primary);border-radius:16px;padding:24px;max-width:520px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.3);position:relative">' +
      '<button onclick="document.getElementById(\'pub-postnow-modal\').style.display=\'none\'" style="position:absolute;top:12px;right:12px;background:none;border:none;font-size:20px;cursor:pointer;color:var(--text-secondary)">✕</button>' +
      '<h3 style="margin:0 0 4px 0">🚀 Post Now</h3>' +
      '<div id="pub-postnow-title" style="font-size:13px;color:var(--text-secondary);margin-bottom:12px"></div>' +
      '<!-- Title -->' +
      '<div style="margin-bottom:10px">' +
      '<label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:4px;font-weight:600">📌 Title</label>' +
      '<input id="pub-edit-title" class="input" maxlength="120" style="width:100%" placeholder="ชื่อโพสต์ (กระชับ ดึงดูด)">' +
      '</div>' +
      '<!-- Description -->' +
      '<div style="margin-bottom:10px">' +
      '<label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:4px;font-weight:600">📝 Description <span id="pub-desc-chars" style="font-size:10px;color:var(--text-tertiary)"></span></label>' +
      '<textarea id="pub-edit-desc" class="input" maxlength="2200" style="width:100%;min-height:80px" placeholder="คำอธิบาย CTA แฮชแท็ก"></textarea>' +
      '</div>' +
      '<!-- AI Generate button -->' +
      '<div style="margin-bottom:12px;display:flex;gap:6px;flex-wrap:wrap">' +
      '<button class="btn btn-sm" id="pub-ai-gen" onclick="pubAIGenContent(\'postnow\')" style="background:rgba(139,92,246,0.1);color:var(--accent-purple);border-color:rgba(139,92,246,0.2)">✨ AI Generate</button>' +
      '<span id="pub-ai-status" style="font-size:11px;color:var(--text-tertiary);align-self:center;display:none">⏳ Generating...</span>' +
      '</div>' +
      '<!-- Platforms -->' +
      '<div style="margin-bottom:16px"><label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:6px;font-weight:600">📱 Select Platforms</label>' +
      '<div id="pub-postnow-platforms" style="display:flex;flex-wrap:wrap;gap:8px">' +
      '<label style="display:flex;align-items:center;gap:4px;font-size:13px;cursor:pointer;padding:6px 14px;border:1px solid var(--border-primary);border-radius:20px;background:var(--bg-secondary)"><input type="checkbox" value="tiktok" checked> 🎵 TikTok</label>' +
      '<label style="display:flex;align-items:center;gap:4px;font-size:13px;cursor:pointer;padding:6px 14px;border:1px solid var(--border-primary);border-radius:20px;background:var(--bg-secondary)"><input type="checkbox" value="instagram"> 📸 Instagram</label>' +
      '<label style="display:flex;align-items:center;gap:4px;font-size:13px;cursor:pointer;padding:6px 14px;border:1px solid var(--border-primary);border-radius:20px;background:var(--bg-secondary)"><input type="checkbox" value="youtube"> ▶️ YouTube</label>' +
      '<label style="display:flex;align-items:center;gap:4px;font-size:13px;cursor:pointer;padding:6px 14px;border:1px solid var(--border-primary);border-radius:20px;background:var(--bg-secondary)"><input type="checkbox" value="facebook"> 👤 Facebook</label>' +
      '</div></div>' +
      '<div style="display:flex;gap:8px;justify-content:flex-end">' +
      '<button class="btn btn-secondary btn-sm" onclick="document.getElementById(\'pub-postnow-modal\').style.display=\'none\'">Cancel</button>' +
      '<button class="btn btn-primary btn-sm" id="pub-postnow-confirm">🚀 Post Now</button>' +
      '</div></div>';
    document.body.appendChild(overlay);
  }
  
  var defaultTitle = vid.title || vid.product_name || productName;
  var defaultDesc = vid.description || '';
  var defaultHtags = vid.hashtags || [];
  document.getElementById('pub-postnow-title').textContent = '🎬 ' + defaultTitle;
  document.getElementById('pub-edit-title').value = defaultTitle;
  document.getElementById('pub-edit-desc').value = defaultDesc || (defaultHtags.length ? defaultHtags.map(function(t){ return '#' + t.replace(/^#/,''); }).join(' ') : '');
  document.getElementById('pub-desc-chars').textContent = document.getElementById('pub-edit-desc').value.length + '/2200';
  document.getElementById('pub-edit-desc').oninput = function(){ document.getElementById('pub-desc-chars').textContent = this.value.length + '/2200'; };
  
  // Store product data for AI gen
  overlay._prodName = productName || vid.product_name || '';
  overlay._prodDesc = vid.description || '';
  overlay._prodTags = defaultHtags || [];
  overlay._vid = vid;
  overlay._jobId = jobId;
  
  overlay.style.display = 'flex';
  
  document.getElementById('pub-postnow-confirm').onclick = async function(){
    var checks = document.querySelectorAll('#pub-postnow-platforms input[type="checkbox"]:checked');
    var platforms = [];
    checks.forEach(function(c){ platforms.push(c.value); });
    if (!platforms.length) { alert('กรุณาเลือกอย่างน้อย 1 platform'); return; }
    
    var title = document.getElementById('pub-edit-title').value.trim() || defaultTitle;
    var desc = document.getElementById('pub-edit-desc').value.trim() || defaultDesc;
    var htags = defaultHtags;
    var cap = title;
    if (htags.length) cap = cap + '\n' + htags.map(function(t){ return '#' + t.replace(/^#/,''); }).join(' ');
    
    overlay.style.display = 'none';
    
    var results = [];
    for (var i = 0; i < platforms.length; i++) {
      var plat = platforms[i];
      var enqR = await pfmFetch('/publisher/enqueue', {
        method: 'POST', body: JSON.stringify({
          video_path: vid.video_url, title: title, description: desc,
          caption: cap, hashtags: htags, platform: plat, job_id: jobId
        })
      });
      
      if (enqR.success) {
        var postR = await pfmFetch('/publisher/' + enqR.post_id + '/post-now', {method:'POST'});
        results.push({platform: plat, success: postR.success, id: enqR.post_id, error: postR.detail||postR.error});
      } else {
        results.push({platform: plat, success: false, error: enqR.detail||enqR.error});
      }
    }
    
    var ok = results.filter(function(r){ return r.success; });
    var fail = results.filter(function(r){ return !r.success; });
    var msg = '✅ Posted to ' + ok.length + ' platforms';
    ok.forEach(function(r){ msg += '\n  ' + r.platform + ': ✅'; });
    if (fail.length) {
      msg += '\n\n❌ Failed on ' + fail.length + ':';   
      fail.forEach(function(r){ msg += '\n  ' + r.platform + ': ' + (r.error||'Unknown'); });
    }
    alert(msg);
    loadPublisherQueue();
  };
}

// ─── AI Generate Title+Description ─────────────────────────

var _pubAiSource = null; // 'postnow' | 'schedule'

async function pubAIGenContent(source) {
  _pubAiSource = source;
  var overlay = document.getElementById('pub-postnow-modal');
  var isPostNow = source === 'postnow';
  var modalEl = overlay;
  if (!isPostNow) {
    modalEl = document.getElementById('pub-schedule-modal');
  }
  
  var productName = modalEl._prodName || '';
  var productDesc = modalEl._prodDesc || '';
  var tags = modalEl._prodTags || [];
  
  // Pick first checked platform as target
  var platChecks = modalEl.querySelectorAll('input[type="checkbox"]:checked');
  var platform = 'tiktok';
  if (platChecks.length) platform = platChecks[0].value;
  
  if (!productName) { alert('No product name available'); return; }
  
  var statusEl = document.getElementById('pub-ai-status');
  var btn = document.getElementById('pub-ai-gen');
  if (statusEl) statusEl.style.display = 'inline';
  if (btn) btn.disabled = true;
  
  // Determine which field IDs to use based on source
  var titleId = isPostNow ? 'pub-edit-title' : 'pub-sched-edit-title';
  var descId = isPostNow ? 'pub-edit-desc' : 'pub-sched-edit-desc';
  var charsId = isPostNow ? 'pub-desc-chars' : 'pub-sched-desc-chars';
  
  try {
    var r = await fetch(API + '/publisher/generate-content', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        product_name: productName,
        description: productDesc,
        tags: tags,
        platform: platform
      })
    });
    var data = await r.json();
    
    if (data.success) {
      var titleInput = document.getElementById(titleId);
      var descInput = document.getElementById(descId);
      if (titleInput && data.title) titleInput.value = data.title;
      if (descInput && data.description) {
        descInput.value = data.description;
        var charEl = document.getElementById(charsId);
        if (charEl) charEl.textContent = data.description.length + '/2200';
      }
      // Save to pipeline_logs.db for persistence
      var jobId = modalEl._jobId || '';
      if (jobId) {
        fetch(API + '/publisher/save-content', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            job_id: jobId,
            title: data.title || '',
            description: data.description || '',
            platform: platform
          })
        }).catch(function(){}); // fire-and-forget
      }
      showToast('✨ AI generated content for ' + platform, 'success');
    } else {
      showToast('AI generation failed', 'error');
    }
  } catch(e) {
    showToast('Error: ' + e.message, 'error');
  } finally {
    if (statusEl) statusEl.style.display = 'none';
    if (btn) btn.disabled = false;
  }
}

// ─── Publisher: Schedule ────────────────────────────────────

async function pubSchedule(jobId, productName) {
  var r, vid;
  try {
    r = await fetch(API + '/video/completed');
    var d = await r.json();
    vid = (d.jobs||[]).find(function(j){ return j.job_id === jobId; });
  } catch(e) {}
  
  if (!vid || !vid.video_url) { alert('Video not found'); return; }
  
  var overlay = document.getElementById('pub-schedule-modal');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'pub-schedule-modal';
    overlay.className = 'modal-overlay';
    overlay.style.cssText = 'z-index:200';
    overlay.onclick = function(e) { if (e.target === this) this.style.display = 'none'; };
    overlay.innerHTML =
      '<div onclick="event.stopPropagation()" style="background:var(--bg-primary);border-radius:16px;padding:24px;max-width:520px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.3);position:relative">' +
      '<button onclick="document.getElementById(\'pub-schedule-modal\').style.display=\'none\'" style="position:absolute;top:12px;right:12px;background:none;border:none;font-size:20px;cursor:pointer;color:var(--text-secondary)">✕</button>' +
      '<h3 style="margin:0 0 4px 0">📅 Schedule Post</h3>' +
      '<div id="pub-schedule-title" style="font-size:13px;color:var(--text-secondary);margin-bottom:12px"></div>' +
      '<!-- Title -->' +
      '<div style="margin-bottom:10px">' +
      '<label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:4px;font-weight:600">📌 Title</label>' +
      '<input id="pub-sched-edit-title" class="input" maxlength="120" style="width:100%" placeholder="ชื่อโพสต์ (กระชับ ดึงดูด)">' +
      '</div>' +
      '<!-- Description -->' +
      '<div style="margin-bottom:10px">' +
      '<label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:4px;font-weight:600">📝 Description <span id="pub-sched-desc-chars" style="font-size:10px;color:var(--text-tertiary)"></span></label>' +
      '<textarea id="pub-sched-edit-desc" class="input" maxlength="2200" style="width:100%;min-height:80px" placeholder="คำอธิบาย CTA แฮชแท็ก"></textarea>' +
      '</div>' +
      '<!-- AI Generate -->' +
      '<div style="margin-bottom:12px;display:flex;gap:6px;flex-wrap:wrap">' +
      '<button class="btn btn-sm" onclick="pubAIGenContent(\'schedule\')" style="background:rgba(139,92,246,0.1);color:var(--accent-purple);border-color:rgba(139,92,246,0.2)">✨ AI Generate</button>' +
      '</div>' +
      '<div style="margin-bottom:12px"><label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:6px;font-weight:600">📱 Platforms</label>' +
      '<div id="pub-schedule-platforms" style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px">' +
      '<label style="display:flex;align-items:center;gap:4px;font-size:13px;cursor:pointer;padding:6px 14px;border:1px solid var(--border-primary);border-radius:20px;background:var(--bg-secondary)"><input type="checkbox" value="tiktok" checked> 🎵 TikTok</label>' +
      '<label style="display:flex;align-items:center;gap:4px;font-size:13px;cursor:pointer;padding:6px 14px;border:1px solid var(--border-primary);border-radius:20px;background:var(--bg-secondary)"><input type="checkbox" value="instagram"> 📸 Instagram</label>' +
      '<label style="display:flex;align-items:center;gap:4px;font-size:13px;cursor:pointer;padding:6px 14px;border:1px solid var(--border-primary);border-radius:20px;background:var(--bg-secondary)"><input type="checkbox" value="youtube"> ▶️ YouTube</label>' +
      '<label style="display:flex;align-items:center;gap:4px;font-size:13px;cursor:pointer;padding:6px 14px;border:1px solid var(--border-primary);border-radius:20px;background:var(--bg-secondary)"><input type="checkbox" value="facebook"> 👤 Facebook</label>' +
      '</div></div>' +
      '<div style="margin-bottom:12px"><label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:6px;font-weight:600">🎯 Mode</label>' +
      '<div style="display:flex;flex-wrap:wrap;gap:16px;margin-bottom:12px">' +
      '<label style="display:flex;align-items:center;gap:4px;font-size:13px;cursor:pointer"><input type="radio" name="sched-mode" value="random" checked> 🎲 Random</label>' +
      '<label style="display:flex;align-items:center;gap:4px;font-size:13px;cursor:pointer"><input type="radio" name="sched-mode" value="fixed"> 🔒 Fixed</label>' +
      '<label style="display:flex;align-items:center;gap:4px;font-size:13px;cursor:pointer"><input type="radio" name="sched-mode" value="sequential"> 📏 Sequential</label>' +
      '</div></div>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">' +
      '<div><label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:4px;font-weight:600">📅 Date</label>' +
      '<input type="date" id="sched-date" style="width:100%;padding:10px;border-radius:8px;border:1px solid var(--border-primary);background:var(--bg-secondary);color:var(--text-primary);font-size:13px"></div>' +
      '<div id="sched-fixed-time"><label style="font-size:12px;color:var(--text-secondary);display:block;margin-bottom:4px;font-weight:600">⏰ Time</label>' +
      '<input type="time" id="sched-time" value="14:00" style="width:100%;padding:10px;border-radius:8px;border:1px solid var(--border-primary);background:var(--bg-secondary);color:var(--text-primary);font-size:13px"></div>' +
      '</div>' +
      '<div style="display:flex;gap:8px;justify-content:flex-end">' +
      '<button class="btn btn-secondary btn-sm" onclick="document.getElementById(\'pub-schedule-modal\').style.display=\'none\'">Cancel</button>' +
      '<button class="btn btn-primary btn-sm" id="pub-schedule-confirm">📅 Schedule</button>' +
      '</div></div>';
    document.body.appendChild(overlay);
  }
  
  var defaultTitle = vid.title || vid.product_name || productName;
  var defaultDesc = vid.description || '';
  var defaultHtags = vid.hashtags || [];
  document.getElementById('pub-schedule-title').textContent = '🎬 ' + defaultTitle;
  document.getElementById('pub-sched-edit-title').value = defaultTitle;
  document.getElementById('pub-sched-edit-desc').value = defaultDesc || (defaultHtags.length ? defaultHtags.map(function(t){ return '#' + t.replace(/^#/,''); }).join(' ') : '');
  document.getElementById('pub-sched-desc-chars').textContent = document.getElementById('pub-sched-edit-desc').value.length + '/2200';
  document.getElementById('pub-sched-edit-desc').oninput = function(){ document.getElementById('pub-sched-desc-chars').textContent = this.value.length + '/2200'; };
  
  document.getElementById('sched-date').value = new Date().toISOString().split('T')[0];
  
  document.querySelectorAll('input[name="sched-mode"]').forEach(function(rd){
    rd.onchange = function(){
      document.getElementById('sched-fixed-time').style.display = this.value === 'fixed' ? 'block' : 'none';
    };
  });
  
  // Store product data for AI gen
  overlay._prodName = productName || vid.product_name || '';
  overlay._prodDesc = vid.description || '';
  overlay._prodTags = defaultHtags || [];
  overlay._vid = vid;
  overlay._jobId = jobId;
  
  overlay.style.display = 'flex';
  
  document.getElementById('pub-schedule-confirm').onclick = async function(){
    var checks = document.querySelectorAll('#pub-schedule-platforms input[type="checkbox"]:checked');
    var platforms = [];
    checks.forEach(function(c){ platforms.push(c.value); });
    if (!platforms.length) { alert('กรุณาเลือก platform'); return; }
    
    var mode = (document.querySelector('input[name="sched-mode"]:checked') || {}).value || 'random';
    var schedDate = document.getElementById('sched-date').value;
    if (!schedDate) { alert('กรุณาเลือกวันที่'); return; }
    
    var scheduleAt;
    if (mode === 'random') {
      var h = 8 + Math.floor(Math.random() * 14);
      var m = Math.floor(Math.random() * 60);
      scheduleAt = new Date(schedDate + 'T' + String(h).padStart(2,'0') + ':' + String(m).padStart(2,'0') + ':00Z').toISOString();
    } else if (mode === 'fixed') {
      var timeStr = document.getElementById('sched-time').value;
      if (!timeStr) { alert('กรุณากรอกเวลา'); return; }
      scheduleAt = new Date(schedDate + 'T' + timeStr + ':00Z').toISOString();
    } else {
      scheduleAt = new Date(Date.now() + 30 * 60000).toISOString();
    }
    
    var title = document.getElementById('pub-sched-edit-title').value.trim() || defaultTitle;
    var desc = document.getElementById('pub-sched-edit-desc').value.trim() || defaultDesc;
    var htags = defaultHtags;
    var cap = title;
    if (htags.length) cap = cap + '\n' + htags.map(function(t){ return '#' + t.replace(/^#/,''); }).join(' ');
    
    overlay.style.display = 'none';
    
    var ok = 0;
    for (var i = 0; i < platforms.length; i++) {
      var enqR = await pfmFetch('/publisher/enqueue', {
        method: 'POST', body: JSON.stringify({
          video_path: vid.video_url, title: title, description: desc,
          caption: cap, hashtags: htags, platform: platforms[i],
          job_id: jobId, schedule_at: scheduleAt
        })
      });
      if (enqR.success) ok++;
    }
    
    alert('✅ Scheduled ' + ok + '/' + platforms.length + ' platforms\n⏰ ' + new Date(scheduleAt).toLocaleString());
    loadPublisherQueue();
  };
}

// ─── Publisher: Batch Schedule ──────────────────────────────

function showBatchSchedule() {
  var modal = document.getElementById('batch-schedule-modal');
  if (!modal) return;
  modal.style.display = 'flex';
  
  // Set default dates
  var today = new Date();
  var nextWeek = new Date(today);
  nextWeek.setDate(nextWeek.getDate() + 7);
  
  var bs = document.getElementById('batch-start');
  var be = document.getElementById('batch-end');
  if (bs && !bs.value) bs.value = today.toISOString().split('T')[0];
  if (be && !be.value) be.value = nextWeek.toISOString().split('T')[0];
  
  updateBatchPreview();
}

function closeBatchSchedule() {
  var modal = document.getElementById('batch-schedule-modal');
  if (modal) modal.style.display = 'none';
}

function updateBatchPreview() {
  var preview = document.getElementById('batch-preview');
  if (!preview) return;
  
  var start = document.getElementById('batch-start').value;
  var end = document.getElementById('batch-end').value;
  var count = parseInt(document.getElementById('batch-count').value) || 3;
  var tStart = document.getElementById('batch-time-start').value;
  var tEnd = document.getElementById('batch-time-end').value;
  var mode = (document.querySelector('input[name="batch-mode"]:checked') || {}).value || 'random';
  var platforms = getBatchPlatforms();
  
  if (!start || !end) {
    preview.innerHTML = '<span style="color:var(--text-tertiary)">กรุณาเลือกวันที่เริ่มและวันที่สิ้นสุด...</span>';
    return;
  }
  
  var startDate = new Date(start);
  var endDate = new Date(end);
  var days = Math.floor((endDate - startDate) / 86400000) + 1;
  var total = days * count;
  
  if (days < 0) {
    preview.innerHTML = '<span style="color:var(--color-red-400)">วันที่สิ้นสุดต้องมาหลังวันที่เริ่ม</span>';
    return;
  }
  
  var modeLabels = {random:'🎲 Random', fixed:'🔒 Fixed ('+tStart+')', sequential:'📏 Sequential'};
  var platNames = {tiktok:'🎵 TikTok', instagram:'📸 IG', youtube:'▶️ YT', facebook:'👤 FB'};
  var platList = platforms.map(function(p){ return platNames[p] || p; }).join(', ');
  
  preview.innerHTML = 
    '<div style="font-weight:600;margin-bottom:6px">📊 ตัวอย่างตารางโพสต์</div>' +
    '<div>📱 <strong>' + platList + '</strong> (' + platforms.length + ' platforms)</div>' +
    '<div>📅 ' + days + ' วัน (' + start + ' → ' + end + ')</div>' +
    '<div>📈 ' + count + ' โพสต์/วัน/แพลตฟอร์ม = <strong>' + total + ' total/plat</strong></div>' +
    '<div>⏰ ' + tStart + ' – ' + tEnd + ' (' + modeLabels[mode] + ')</div>' +
    '<div style="margin-top:6px;font-size:10px;color:var(--text-tertiary)">วิดีโอจะถูกกระจายตามวันที่เลือก กด "Schedule All" เพื่อเพิ่มลงคิว</div>';
}

async function executeBatchSchedule() {
  // Gather all visible completed video job IDs
  var vids = [];
  try {
    var r = await fetch(API + '/video/completed');
    var d = await r.json();
    var platforms = getBatchPlatforms();
    (d.jobs||[]).forEach(function(j){
      platforms.forEach(function(plat){
        vids.push({
          job_id: j.job_id,
          video_path: j.video_url || ('/api/tiktok/static/videos/final_' + j.job_id + '.mp4'),
          title: j.title || j.product_name || '',
          description: j.description || '',
          caption: j.product_name || '',
          hashtags: j.hashtags || [],
          platform: plat
        });
      });
    });
  } catch(e) {}
  
  if (!vids.length) {
    alert('No completed videos found. Run a pipeline first.');
    return;
  }
  
  var mode = (document.querySelector('input[name="batch-mode"]:checked') || {}).value || 'random';
  var count = parseInt(document.getElementById('batch-count').value) || 3;
  
  if (!confirm('Schedule ' + vids.length + ' videos | Mode: ' + mode + ', ' + count + '/day | ' + document.getElementById('batch-start').value + ' - ' + document.getElementById('batch-end').value + ' | ' + document.getElementById('batch-time-start').value + '-' + document.getElementById('batch-time-end').value)) return;
  
  var btn = document.querySelector('#batch-schedule-modal .btn-primary');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Scheduling...'; }
  
  try {
    var r = await pfmFetch('/publisher/bulk-schedule', {
      method: 'POST', body: JSON.stringify({
        video_ids: vids,
        date_range_start: document.getElementById('batch-start').value,
        date_range_end: document.getElementById('batch-end').value,
        count_per_day: count,
        mode: mode,
        time_window_start: document.getElementById('batch-time-start').value,
        time_window_end: document.getElementById('batch-time-end').value,
        platform: platforms[0]
      })
    });
    
    if (r.success) {
      alert('✅ ' + r.scheduled + ' posts scheduled! ' + r.config.date_range + ' | ' + r.config.count_per_day + '/day | ' + r.config.mode);
      closeBatchSchedule();
      loadPublisherQueue();
    } else {
      alert('❌ Failed: ' + (r.detail||r.error||'Unknown'));
    }
  } catch(e) {
    alert('❌ Error: ' + e.message);
  }
  
  if (btn) { btn.disabled = false; btn.textContent = '📅 Schedule All'; }
}

// ─── Publisher: Queue ────────────────────────────────────────

async function loadPublisherQueue() {
  var list = document.getElementById('pub-queue-list');
  var stats = document.getElementById('pub-queue-stats');
  if (!list) return;
  list.innerHTML = '<div class="text-sm text-secondary">⏳ Loading...</div>';
  
  try {
    var r = await fetch(API + '/publisher/queue');
    var posts = (await r.json()).posts || [];
    
    // Stats
    var counts = {pending:0,scheduled:0,posting:0,posted:0,failed:0};
    posts.forEach(function(p){ counts[p.status] = (counts[p.status]||0) + 1; });
    if (stats) stats.innerHTML = '⏳' + counts.pending + ' Pending | 📅' + counts.scheduled + ' Scheduled | ✅' + counts.posted + ' Posted | ❌' + counts.failed + ' Failed';
    
    if (!posts.length) {
      list.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:24px">No posts in queue. Click "Post Now" or "Schedule" on a video above.</div>';
      return;
    }
    
    var scColors = {pending:'#f59e0b',scheduled:'#3b82f6',posting:'#f59e0b',posted:'#10b981',failed:'#ef4444',cancelled:'#6b7280'};
    var scIcons = {pending:'⏳',scheduled:'📅',posting:'⬆️',posted:'✅',failed:'❌',cancelled:'🚫'};
    
    var html = '';
    posts.forEach(function(p){
      var vidName = (p.video_path||'').split('/').pop() || '-';
      var title = p.title || p.caption || vidName;
      var pal = {tiktok:{icon:'🎵',name:'TikTok'},instagram:{icon:'📸',name:'IG'},youtube:{icon:'▶️',name:'YT'},facebook:{icon:'👤',name:'FB'}};
      var sColor = scColors[p.status]||'gray';
      var sIco = scIcons[p.status]||'';
      html += '<div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border-primary);transition:background .15s">' +
        '<div style="flex-shrink:0;width:36px;height:36px;border-radius:50%;background:' + sColor + '20;display:flex;align-items:center;justify-content:center;font-size:16px">' + sIco + '</div>' +
        '<div style="flex:1;min-width:0">' +
          '<div style="font-size:13px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + escapeHtml(title) + '">' + escapeHtml(title) + '</div>' +
          '<div style="display:flex;align-items:center;gap:8px;margin-top:2px;flex-wrap:wrap">' +
            '<span style="font-size:10px;font-family:mono;color:var(--text-tertiary)">' + (p.id||'').substring(0,12) + '</span>' +
            '<span style="display:inline-flex;align-items:center;gap:3px;font-size:10px;color:var(--text-secondary);background:var(--bg-tertiary);padding:1px 8px;border-radius:10px;font-weight:500">' + (pal[p.platform] ? pal[p.platform].icon + ' ' + pal[p.platform].name : '📱') + '</span>' +
            (p.schedule_at ? '<span style="font-size:10px;color:var(--text-tertiary)">' + new Date(p.schedule_at).toLocaleTimeString('th-TH',{hour:'2-digit',minute:'2-digit'}) + '</span>' : '') +
            (p.publish_id ? '<span style="font-size:10px;color:var(--color-green-400);font-family:mono">✓ ' + (p.publish_id||'').substring(0,12) + '</span>' : '') +
            (p.error ? '<span style="font-size:10px;color:var(--color-red-400)" title="' + escapeHtml(p.error||'') + '">⚠ ' + (p.error||'').substring(0,30) + '</span>' : '') +
          '</div>' +
        '</div>' +
        '<div style="flex-shrink:0;display:flex;gap:6px">' +
          (p.status === 'pending' ? '<button class="btn btn-primary btn-sm" onclick="pubPostNowById(\'' + p.id + '\')" style="font-size:11px;padding:4px 12px">▶ Post</button>' : '') +
          (p.status === 'failed' ? '<button class="btn btn-secondary btn-sm" onclick="pubPostNowById(\'' + p.id + '\')" style="font-size:11px;padding:4px 12px">🔁 Retry</button>' : '') +
        '</div>' +
      '</div>';
    });
    list.innerHTML = html;
  } catch(e) {
    list.innerHTML = '<div class="text-sm" style="color:var(--color-red-400)">❌ ' + e.message + '</div>';
  }
}

// ─── Publisher: Post By ID (from queue) ────────────────────────

async function pubPostNowById(postId) {
  var r = await pfmFetch('/publisher/' + postId + '/post-now', {method:'POST'});
  if (r.success) {
    alert('✅ Posted!');
    loadPublisherQueue();
  } else {
    alert('❌ Failed: ' + (r.detail||r.error||'Unknown'));
    loadPublisherQueue();
  }
}

function escapeHtml(str) {
  return (str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function pfmOpenConnectModal(platform) {
  pfmConnectPlatform = platform;
  const p = PFM_PLATFORMS[platform] || { icon: '❓', name: platform };
  const svgs = window.PLATFORM_SVGS || {};
  var iconEl = document.getElementById('pfm-connect-icon');
  if (svgs[platform]) { iconEl.innerHTML = svgs[platform]; } else { iconEl.textContent = p.icon; }
  document.getElementById('pfm-connect-name').textContent = p.name;
  document.getElementById('pfm-connect-title').textContent = '🔗 Connect ' + p.name;
  document.getElementById('pfm-connect-result').innerHTML = '';
  document.getElementById('pfm-connect-btn').disabled = false;
  document.getElementById('pfm-connect-btn').textContent = '🔗 Connect';
  document.getElementById('pfm-connect-modal').classList.add('open');
}

function pfmCloseConnectModal() {
  document.getElementById('pfm-connect-modal').classList.remove('open');
  if (pfmConnectPopup && !pfmConnectPopup.closed) pfmConnectPopup.close();
  if (pfmConnectInterval) { clearInterval(pfmConnectInterval); pfmConnectInterval = null; }
}

async function pfmDoConnect() {
  const btn = document.getElementById('pfm-connect-btn');
  const result = document.getElementById('pfm-connect-result');
  btn.disabled = true;
  btn.textContent = '⏳ Connecting...';
  result.innerHTML = '<div class="text-sm text-secondary">Getting auth URL...</div>';
  
  const perms = [];
  if (document.getElementById('pfm-perm-posts').checked) perms.push('posts');
  if (document.getElementById('pfm-perm-feeds').checked) perms.push('feeds');
  
  const r = await pfmFetch('/accounts/connect', {method:'POST', body:JSON.stringify({platform:pfmConnectPlatform, permissions:perms})});
  
  if (r.success && r.auth_url) {
    result.innerHTML = '<div class="text-sm text-secondary">⏳ Opening login popup...</div>';
    const w=600, h=700;
    const left = (screen.width-w)/2, top = (screen.height-h)/2;
    pfmConnectPopup = window.open(r.auth_url, 'pfm-oauth', 'width='+w+',height='+h+',left='+left+',top='+top+',resizable=yes,scrollbars=yes');
    
    result.innerHTML = '<div class="text-sm text-secondary">⏳ Waiting for login...<br><span class="text-xs">Complete login in the popup window</span></div>';
    
    pfmConnectInterval = setInterval(async function(){
      if (!pfmConnectPopup || pfmConnectPopup.closed) {
        clearInterval(pfmConnectInterval);
        pfmConnectInterval = null;
        result.innerHTML = '<div class="text-sm text-secondary">⏳ Checking for new account...</div>';
        await new Promise(function(r){ setTimeout(r, 2000); });
        pfmFetchAccounts();
        setTimeout(function(){ pfmCloseConnectModal(); }, 1000);
      }
    }, 500);
    
    setTimeout(function(){
      if (pfmConnectInterval) { clearInterval(pfmConnectInterval); pfmConnectInterval = null; }
    }, 300000);
  } else {
    result.innerHTML = '<div class="text-sm" style="color:var(--color-red-400)">❌ ' + (r.error||'Failed') + '</div>';
    btn.disabled = false;
    btn.textContent = '🔗 Connect';
  }
}

async function pfmFetchAccounts() {
  // Fetch AitoEarn platforms + local accounts
  await aeFetchStatus();
  
  var localAccounts = [];
  try {
    var localR = await pfmFetch('/tiktok/accounts');
    localAccounts = localR.accounts || [];
  } catch(e) { console.log('No local accounts:', e.message); }

  // Build account map from AitoEarn
  var accountMap = {};
  _aeAccounts.forEach(function(a){
    var plat = a.platform || 'unknown';
    if (!accountMap[plat]) accountMap[plat] = [];
    accountMap[plat].push({
      id: a.id, platform: plat,
      username: a.nickname || a.id,
      avatar: a.avatar || '',
      status: a.status === 1 ? 'active' : 'inactive',
      fans: a.fans || 0, works: a.works || 0,
      source: 'aitoearn'
    });
  });
  
  localAccounts.forEach(function(a){
    if (!accountMap['tiktok_local']) accountMap['tiktok_local'] = [];
    accountMap['tiktok_local'].push(Object.assign({source:'local'}, a));
  });
  
  // Update selects for Post/Schedule tabs
  ['pfm-post-accounts','pfm-sched-accounts'].forEach(function(id){
    var sel = document.getElementById(id); if(!sel) return;
    sel.innerHTML = '';
    _aeAccounts.forEach(function(a){
      var opt = document.createElement('option');
      opt.value = a.id;
      opt.textContent = '[' + (a.platform||'?').toUpperCase() + '] ' + (a.nickname||a.id);
      sel.appendChild(opt);
    });
    localAccounts.forEach(function(a){
      var opt = document.createElement('option');
      opt.value = a.account_id || a.id;
      opt.textContent = '[LOCAL] ' + (a.username||a.account_id||'?');
      sel.appendChild(opt);
    });
  });
}

// ─── AitoEarn OAuth Connect ────────────────────────────────────────
var _oauthPopup = null;
var _oauthInterval = null;

async function pfmStartOAuth(platform) {
  var brand = PFM_BRANDS[platform] || { name: platform };
  if (!confirm('Connect ' + brand.name + ' via AitoEarn?\\n\\nThis will open a popup to authorize your ' + brand.name + ' account.')) return;
  
  try {
    var r = await fetch(PFM_API + '/aitoearn/connect/' + platform + '?redirect_uri=' + encodeURIComponent(window.location.origin + '/tiktok/'));
    var d = await r.json();
    if (!d.success || !d.data || !d.data.url) {
      alert('OAuth failed: ' + (d.error || 'No URL returned'));
      return;
    }
    
    var w = 600, h = 700;
    var left = (screen.width - w) / 2, top = (screen.height - h) / 2;
    _oauthPopup = window.open(d.data.url, 'aitoearn-oauth', 'width=' + w + ',height=' + h + ',left=' + left + ',top=' + top);
    
    if (!_oauthPopup) {
      // Popup blocked — redirect instead
      window.location.href = d.data.url;
      return;
    }
    
    var sessionId = d.data.sessionId;
    // Poll for completion
    var attempts = 0;
    _oauthInterval = setInterval(async function() {
      attempts++;
      if (_oauthPopup.closed) {
        clearInterval(_oauthInterval);
        // Refresh accounts
        await pfmFetchAccounts();
        return;
      }
      if (attempts > 120) { // 2 min timeout
        clearInterval(_oauthInterval);
        if (!_oauthPopup.closed) _oauthPopup.close();
        alert('OAuth timed out. Try again.');
        return;
      }
      // Check status every 5 seconds
      if (sessionId && attempts % 5 === 0) {
        try {
          var sr = await fetch(PFM_API + '/aitoearn/connect/' + platform + '/status/' + sessionId);
          var sd = await sr.json();
          if (sd.success && sd.status === 'completed') {
            clearInterval(_oauthInterval);
            if (!_oauthPopup.closed) _oauthPopup.close();
            await pfmFetchAccounts();
          }
        } catch(e) {}
      }
    }, 1000);
  } catch(e) {
    alert('OAuth error: ' + e.message);
  }
}

function pfmOpenDetail(platform, accounts) {
  var pf = PFM_PLATFORMS[platform] || { icon:'?', name:platform };
  var acc = accounts[0] || {};
  pfmDetailAccountId = acc.id;
  
  var svgs = window.PLATFORM_SVGS || {};
  var iconEl = document.getElementById('pfm-detail-icon');
  if (svgs[platform]) { iconEl.innerHTML = svgs[platform]; } else { iconEl.textContent = pf.icon; }
  document.getElementById('pfm-detail-name').textContent = acc.username || acc.id || 'Unknown';
  document.getElementById('pfm-detail-title').textContent = pf.icon + ' ' + pf.name;
  
  var infoHtml = '<div style="background:var(--bg-tertiary);border-radius:var(--radius);padding:12px">';
  infoHtml += '<div class="mb-2"><span class="text-xs text-secondary">Account ID</span><br><span style="font-size:13px;font-family:monospace">' + (acc.id||'-') + '</span></div>';
  infoHtml += '<div class="mb-2"><span class="text-xs text-secondary">Platform</span><br><span style="font-size:13px">' + (acc.platform||'-') + '</span></div>';
  infoHtml += '<div class="mb-2"><span class="text-xs text-secondary">Username</span><br><span style="font-size:13px">' + (acc.username||'-') + '</span></div>';
  infoHtml += '<div class="mb-2"><span class="text-xs text-secondary">Status</span><br><span style="font-size:13px;color:var(--color-green-400)">' + (acc.status||'-') + '</span></div>';
  if (acc.access_token_expires_at) {
    infoHtml += '<div class="mb-2"><span class="text-xs text-secondary">Token Expires</span><br><span style="font-size:13px">' + new Date(acc.access_token_expires_at).toLocaleDateString() + '</span></div>';
  }
  infoHtml += '</div>';
  
  document.getElementById('pfm-detail-info').innerHTML = infoHtml;
  document.getElementById('pfm-account-detail-modal').classList.add('open');
}

function pfmCloseDetailModal() {
  document.getElementById('pfm-account-detail-modal').classList.remove('open');
  pfmDetailAccountId = null;
}

function pfmDisconnectAccount() {
  if (!pfmDetailAccountId) return;
  pfmCloseDetailModal();
}

/* ═══ Auth Functions ═══ */
function getUserToken() { return localStorage.getItem('tus_token'); }
function getUserInfo() { try { return JSON.parse(localStorage.getItem('tus_user') || '{}'); } catch(e) { return {}; } }
function isLoggedIn() { return !!getUserToken(); }

function switchAuthTab(tab) {
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('authLoginForm').style.display = tab === 'login' ? 'block' : 'none';
  document.getElementById('authRegisterForm').style.display = tab === 'register' ? 'block' : 'none';
  document.getElementById('authTab' + tab.charAt(0).toUpperCase() + tab.slice(1))?.classList.add('active');
  document.getElementById('authLoginResult').textContent = '';
  document.getElementById('authRegisterResult').textContent = '';
  document.getElementById('authResult').textContent = '';
}

function openAuthModal() {
  document.getElementById('authModal').classList.add('open');
  document.getElementById('authLoginResult').textContent = '';
  document.getElementById('authRegisterResult').textContent = '';
  document.getElementById('authResult').textContent = '';
}

function closeAuthModal() {
  document.getElementById('authModal').classList.remove('open');
}

async function authLogin() {
  const email = document.getElementById('authLoginEmail').value.trim();
  const password = document.getElementById('authLoginPassword').value;
  const result = document.getElementById('authLoginResult');
  if (!email || !password) { result.textContent = 'Please fill in all fields'; result.style.color = 'var(--color-red-400)'; return; }
  result.textContent = '⏳ Signing in...'; result.style.color = 'var(--text-secondary)';
  try {
    const r = await fetch(window.location.origin + '/api/auth/login', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({email, password})
    });
    const d = await r.json();
    if (d.ok && d.token) {
      localStorage.setItem('tus_token', d.token);
      localStorage.setItem('tus_user', JSON.stringify(d.user || {email:email, name: (d.user?.name || email.split('@')[0])}));
      closeAuthModal();
      updateAuthUI();
    } else {
      result.textContent = d.message || d.error || 'Login failed';
      result.style.color = 'var(--color-red-400)';
    }
  } catch(e) {
    result.textContent = 'Error: ' + e.message;
    result.style.color = 'var(--color-red-400)';
  }
}

async function authRegister() {
  const name = document.getElementById('authRegisterName').value.trim();
  const email = document.getElementById('authRegisterEmail').value.trim();
  const password = document.getElementById('authRegisterPassword').value;
  const result = document.getElementById('authRegisterResult');
  if (!name || !email || !password) { result.textContent = 'Please fill in all fields'; result.style.color = 'var(--color-red-400)'; return; }
  result.textContent = '⏳ Creating account...'; result.style.color = 'var(--text-secondary)';
  try {
    const r = await fetch(window.location.origin + '/api/auth/register', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({name, email, password})
    });
    const d = await r.json();
    if (d.ok && d.token) {
      localStorage.setItem('tus_token', d.token);
      localStorage.setItem('tus_user', JSON.stringify(d.user || {name:name, email:email}));
      closeAuthModal();
      updateAuthUI();
    } else {
      result.textContent = d.message || d.error || 'Registration failed';
      result.style.color = 'var(--color-red-400)';
    }
  } catch(e) {
    result.textContent = 'Error: ' + e.message;
    result.style.color = 'var(--color-red-400)';
  }
}

function authOAuth(provider) {
  window.location.href = window.location.origin + '/api/auth/' + provider + '/login';
}

function authLogout() {
  localStorage.removeItem('tus_token');
  localStorage.removeItem('tus_user');
  updateAuthUI();
  showToast('Logged out', 'info');
}

function updateAuthUI() {
  const token = getUserToken();
  const user = getUserInfo();
  const badge = document.getElementById('userBadge');
  const badgeName = document.getElementById('userBadgeName');
  const badgeAvatar = document.getElementById('userBadgeAvatar');
  const loginBtn = document.getElementById('btn-topbar-login');
  
  const loggedOutPanel = document.getElementById('profile-logged-out');
  const loggedInPanel = document.getElementById('profile-logged-in');
  
  if (token && user) {
    if (badge) { badge.style.display = 'flex'; }
    if (loginBtn) { loginBtn.style.display = 'none'; }
    if (badgeName) { badgeName.textContent = user.name || user.email || 'User'; }
    if (badgeAvatar) { badgeAvatar.textContent = (user.name || user.email || 'U')[0].toUpperCase(); }
    document.getElementById('userBadgeLogout').style.display = 'inline-flex';
    
    // Update top header balance display
    const balanceVal = user.balance !== undefined ? parseFloat(user.balance).toFixed(2) : '0.00';
    const badgeBalance = document.getElementById('userBadgeBalance');
    if (badgeBalance) { badgeBalance.textContent = '฿' + balanceVal; }
    
    if (loggedOutPanel) loggedOutPanel.style.display = 'none';
    if (loggedInPanel) {
      loggedInPanel.style.display = 'block';
      
      document.getElementById('profile-user-name').textContent = user.name || user.email || 'User';
      document.getElementById('profile-user-email').textContent = user.email || '';
      document.getElementById('profile-avatar-big').textContent = (user.name || user.email || 'U')[0].toUpperCase();
      document.getElementById('profile-user-tier').textContent = user.member_tier || 'Free Member';
      
      const balanceVal = user.balance !== undefined ? parseFloat(user.balance).toFixed(2) : '0.00';
      document.getElementById('profile-balance').textContent = '฿' + balanceVal;
      
      const creditsVal = user.credits || 0;
      const maxCreditsVal = user.max_credits || 200;
      document.getElementById('profile-credits').textContent = creditsVal + ' / ' + maxCreditsVal + ' Credits';
      
      const percent = Math.min(100, Math.round((creditsVal / maxCreditsVal) * 100));
      document.getElementById('profile-credits-bar').style.width = percent + '%';
      
      const providersDiv = document.getElementById('profile-auth-providers');
      if (providersDiv) {
        let email = user.email || '';
        let isLine = email.includes('@line.me');
        let isGoogle = !isLine && email.includes('@gmail.com');
        
        providersDiv.innerHTML = `
          <div style="display:flex;align-items:center;justify-content:space-between;padding:10px;background:var(--bg-tertiary);border-radius:var(--radius)">
            <div style="display:flex;align-items:center;gap:10px">
              <svg viewBox="0 0 24 24" width="16" height="16" style="flex-shrink:0"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
              <strong>Google Account</strong>
            </div>
            <span style="font-size:12.5px;font-weight:600;color:${isGoogle ? 'var(--accent-green)' : 'var(--text-secondary)'}">${isGoogle ? 'Connected' : 'Not Linked'}</span>
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;padding:10px;background:var(--bg-tertiary);border-radius:var(--radius);margin-top:10px">
            <div style="display:flex;align-items:center;gap:10px">
              <svg viewBox="0 0 24 24" width="16" height="16" style="flex-shrink:0"><path fill="#06C755" d="M12 2C6.48 2 2 5.82 2 10.53c0 4.21 3.56 7.73 8.39 8.43.33.07.78.22.89.57.1.31.07.8.03 1.12l-.12.75c-.04.25-.19.97.83.53 1.02-.44 5.51-3.25 7.52-5.57 1.4-1.62 2.36-3.46 2.36-5.78C22 5.82 17.52 2 12 2zm-4.7 11.23h-1.3c-.22 0-.4-.18-.4-.4V7.5c0-.22.18-.4.4-.4h1.3c.22 0 .4.18.4.4v5.33c0 .22-.18.4-.4.4zm3.87 0H9.72c-.22 0-.4-.18-.4-.4V7.5c0-.22.18-.4.4-.4h1.3c.22 0 .4.18.4.4v.93c0 .22-.18.4-.4.4H10.6v.87h.57c.22 0 .4.18.4.4v.93c0 .22-.18.4-.4.4h-.57v.88h1.12c.22 0 .4.18.4.4v.93c0 .22-.18.4-.4.4zm2.84 0h-1.3c-.22 0-.4-.18-.4-.4V7.5c0-.22.18-.4.4-.4h1.3c.22 0 .4.18.4.4v5.33c0 .22-.18.4-.4.4zm4.84 0h-1.12c-.08 0-.15-.03-.21-.08L16.2 9.56v3.27c0 .22-.18.4-.4.4h-1.3c-.22 0-.4-.18-.4-.4V7.5c0-.22.18-.4.4-.4h1.12c.08 0 .15.03.21.08l1.43 1.95V7.5c0-.22.18-.4.4-.4h1.3c.22 0 .4.18.4.4v5.33c0 .22-.18.4-.4.4z"/></svg>
              <strong>LINE Account</strong>
            </div>
            <span style="font-size:12.5px;font-weight:600;color:${isLine ? 'var(--accent-green)' : 'var(--text-secondary)'}">${isLine ? 'Connected' : 'Not Linked'}</span>
          </div>
        `;
      }
    }
  } else {
    if (badge) { badge.style.display = 'none'; }
    if (loginBtn) { loginBtn.style.display = 'inline-block'; }
    if (loggedOutPanel) {
      loggedOutPanel.style.display = 'block';
      toggleLocalAuthTab('login');
    }
    if (loggedInPanel) loggedInPanel.style.display = 'none';
  }
}

// Run updateAuthUI on load
document.addEventListener('DOMContentLoaded', function() {
  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get('token');
  if (token) {
    localStorage.setItem('tus_token', token);
    fetch(window.location.origin + '/api/auth/me', {
      headers: { 'Authorization': 'Bearer ' + token }
    })
    .then(r => r.json())
    .then(d => {
      if (d.ok && d.user) {
        localStorage.setItem('tus_user', JSON.stringify(d.user));
      }
      window.history.replaceState({}, document.title, window.location.pathname);
      updateAuthUI();
    })
    .catch(e => {
      console.error('Error fetching user profile:', e);
      window.history.replaceState({}, document.title, window.location.pathname);
      updateAuthUI();
    });
  } else {
    setTimeout(updateAuthUI, 50);
  }
});

/* ═══ Scout — Facebook/IG Viral Clip Search ═══ */
let _scoutNicheCache = [];
let _scoutResults = [];

async function scoutRefreshNiches() {
  const sel = document.getElementById('scout-niche');
  if (!sel) return;
  sel.innerHTML = '<option value="">Loading...</option>';
  try {
    const r = await fetch(API + '/scout/facebook/niches');
    const d = await r.json();
    _scoutNicheCache = d.niches || [];
    sel.innerHTML = '<option value="">All Niches</option>'
      + _scoutNicheCache.map(function(n){ return '<option value="' + (n.id||n) + '">' + (n.name||n) + '</option>'; }).join('');
  } catch(e) {
    sel.innerHTML = '<option value="">All Niches</option><option value="beauty">Beauty</option><option value="fashion">Fashion</option><option value="food">Food</option>';
  }
}

async function scoutSearch() {
  const niche = document.getElementById('scout-niche').value;
  const minEng = parseInt(document.getElementById('scout-min-eng').value) || 500;
  const el = document.getElementById('scout-results');
  el.innerHTML = '<div class="text-sm text-secondary"><div class="spinner" style="margin:12px auto"></div>Searching...</div>';
  try {
    const r = await fetch(API + '/scout/facebook/search', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({niche: niche || undefined, min_engagement: minEng, limit: 20})
    });
    const d = await r.json();
    _scoutResults = d.posts || d.clips || d.results || [];
    if (!_scoutResults.length) {
      el.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:24px">📭 0 posts found. Try a different niche or lower min engagement.</div>';
      return;
    }
    el.innerHTML = '<div class="scout-grid">' + _scoutResults.map((c, i) => {
      const isViral = (c.views || 0) >= 10000 || (c.likes || 0) >= 2000;
      const viralBadge = isViral ? '<span class="scout-viral-badge">🔥 VIRAL</span>' : '';
      const eng = c.engagement_total || c.likes || 0;
      const thumb = c.video_url || '';
      const platform = c.platform || 'facebook';
      return `<div class="scout-card ${isViral ? 'scout-card-viral' : ''}">
        <div class="scout-card-thumb">
          ${thumb ? `<img src="${thumb}" alt="" loading="lazy">` : '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-tertiary);font-size:32px">🎬</div>'}
          ${viralBadge}
          <span class="scout-eng-badge">❤️ ${eng.toLocaleString()}</span>
        </div>
        <div class="scout-card-body">
          <div class="scout-card-title">${(c.message||c.caption||'').slice(0,60) || 'Untitled Clip'}</div>
          <div class="scout-card-meta">
            <span>👁️ ${(c.views || 0).toLocaleString()}</span>
            <span>❤️ ${(c.likes || 0).toLocaleString()}</span>
            <span>💬 ${(c.comments || 0).toLocaleString()}</span>
            <span>📱 ${platform}</span>
          </div>
          <div class="scout-card-actions">
            <button class="btn btn-primary btn-sm" onclick="scoutOpenDetail(${i})" style="flex:1">🎬 Clone</button>
            <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation();scoutClone(${i}, 'quick')">⚡ Quick</button>
          </div>
        </div>
      </div>`;
    }).join('') + '</div>';
  } catch(e) {
    el.innerHTML = '<div class="text-sm text-secondary" style="text-align:center;padding:24px;color:var(--color-red-400)">❌ Search failed: ' + e.message + '</div>';
  }
}

function scoutOpenDetail(idx) {
  const clip = _scoutResults[idx];
  if (!clip) return;
  const html = `
    <div style="margin-bottom:12px">
      ${clip.video_url ? `<video src="${clip.video_url}" controls style="width:100%;max-height:320px;border-radius:var(--radius-lg);background:#000"></video>` : ''}
      ${clip.thumbnail ? `<img src="${clip.thumbnail}" style="width:100%;max-height:320px;object-fit:contain;border-radius:var(--radius-lg)">` : ''}
    </div>
    <div class="text-sm mb-2"><strong>Message:</strong> ' + (clip.message||clip.caption||'-') + '</div>
    <div class="scout-card-meta mb-3">
      <span>❤️ ' + (clip.likes||0).toLocaleString() + '</span>
      <span>🔄 ' + (clip.shares||0).toLocaleString() + '</span>
      <span>💬 ' + (clip.comments||0).toLocaleString() + '</span>
    </div>
    <div class="flex gap-2">
      <button class="btn btn-primary" onclick="scoutClone(' + idx + ', \'full\')" style="flex:1">🎬 Clone to Pipeline</button>
      <button class="btn btn-secondary" onclick="scoutClone(' + idx + ', \'quick\')">⚡ Quick Clone</button>
    </div>
    <div id="scout-clone-progress-${idx}" class="mt-2"></div>
  `;
  showModal('🎬 Clip Detail', html);
}

async function scoutClone(idx, mode) {
  const clip = _scoutResults[idx];
  if (!clip) { showToast('No clip selected','error'); return; }
  const progressEl = document.getElementById('scout-clone-progress-' + idx) || document.getElementById('scout-clone-result');
  if (progressEl) progressEl.innerHTML = '<div class="text-sm text-secondary">⏳ Cloning to pipeline...</div>';
  try {
    const r = await fetch(API + '/scout/facebook/clone', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        source_clip: clip,
        mode: mode,
        product_name: document.getElementById('scout-clone-product')?.value || '',
      })
    });
    const d = await r.json();
    if (d.success) {
      showToast('✅ Clone initiated! Job: ' + (d.job_id || 'OK'), 'success');
      if (progressEl) progressEl.innerHTML = '<div class="text-sm" style="color:var(--color-green-400)">✅ Clone started! <a href="#" onclick="switchTab(\'pipeline\');return false">View in Pipeline →</a></div>';
    } else {
      showToast('❌ ' + (d.error || 'Clone failed'), 'error');
      if (progressEl) progressEl.innerHTML = '<div class="text-sm" style="color:var(--color-red-400)">❌ ' + (d.error || 'Failed') + '</div>';
    }
  } catch(e) {
    showToast('Error: ' + e.message, 'error');
    if (progressEl) progressEl.innerHTML = '<div class="text-sm" style="color:var(--color-red-400)">❌ ' + e.message + '</div>';
  }
}

async function scoutQuickClone() {
  const productName = document.getElementById('scout-clone-product')?.value.trim();
  const template = document.getElementById('scout-clone-template')?.value || 'quick_review';
  if (!productName) { showToast('Enter a product name','error'); return; }
  const el = document.getElementById('scout-clone-result');
  el.innerHTML = '<div class="text-sm text-secondary">⏳ Generating clone script for "' + productName + '" using ' + template + '...</div>';
  try {
    const r = await fetch(API + '/scout/facebook/clone', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({product_name: productName, template: template})
    });
    const d = await r.json();
    if (d.success) {
      el.innerHTML = '<div class="text-sm" style="color:var(--color-green-400)">✅ Script generated! <a href="#" onclick="document.getElementById(\'productTitle\').value=\'' + productName.replace(/'/g, "\\'") + '\';switchTab(\'content\');return false">Open in Video Wizard →</a></div>'
        + (d.script ? '<pre style="font-size:11px;background:var(--bg-tertiary);padding:8px;border-radius:var(--radius);margin-top:6px;max-height:120px;overflow:auto">' + d.script + '</pre>' : '');
      showToast('✅ Clone script ready!', 'success');
    } else {
      el.innerHTML = '<div class="text-sm" style="color:var(--color-red-400)">❌ ' + (d.error || 'Generation failed') + '</div>';
    }
  } catch(e) {
    el.innerHTML = '<div class="text-sm" style="color:var(--color-red-400)">❌ ' + e.message + '</div>';
  }
}

/* ═══ Batch Generator Functions ═══ */
let _batchSelected = new Map(); // key -> { title, image, enc }

function toggleBatchSelect(cb) {
  const card = cb.closest('.product-card');
  const enc = cb.getAttribute('data-enc');
  if (!enc) return;
  // Decode product info from enc
  var info;
  try { 
    info = JSON.parse(decodeURIComponent(enc));
    info = {enc: enc, title: info.title || info.name || 'Unknown', image: (info.images && info.images[0]) || (info.image_urls && info.image_urls[0]) || '', url: info.url || ''};
  } catch(e) { 
    info = {enc: enc, title: 'Unknown', image: '', url: ''};
  }
  if (cb.checked) {
    _batchSelected.set(enc, info);
    card.classList.add('batch-selected');
  } else {
    _batchSelected.delete(enc);
    card.classList.remove('batch-selected');
  }
  updateBatchBar();
}

function updateBatchBar() {
  const bar = document.getElementById('batchBar');
  const count = document.getElementById('batchCount');
  const n = _batchSelected.size;
  count.textContent = n;
  bar.style.display = n > 0 ? 'flex' : 'none';
}

function clearBatchSelection() {
  document.querySelectorAll('.product-card.batch-selected').forEach(function(c) { c.classList.remove('batch-selected'); });
  document.querySelectorAll('.product-card-checkbox input').forEach(function(c) { c.checked = false; });
  _batchSelected.clear();
  updateBatchBar();
}

function openBatchModal() {
  const list = document.getElementById('batchProductList');
  const modal = document.getElementById('batchModal');
  let html = '';
  let i = 0;
  _batchSelected.forEach(function(v) {
    i++;
    html += '<div style="padding:4px 0;border-bottom:1px solid var(--border-primary)">' + i + '. ' + (v.title || 'Unknown').slice(0, 60) + '</div>';
  });
  list.innerHTML = html || '<div class="text-secondary">No products selected</div>';
  // Copy config from batch bar
  document.getElementById('batchModalStyle').value = document.getElementById('batchStyle').value;
  document.getElementById('batchModalDuration').value = document.getElementById('batchDuration').value;
  document.getElementById('batchModalConcurrency').value = document.getElementById('batchConcurrency').value;
  modal.classList.add('open');
}

function closeBatchModal() {
  document.getElementById('batchModal').classList.remove('open');
}

async function startBatch() {
  const btn = document.getElementById('startBatchBtn');
  btn.disabled = true;
  btn.textContent = '⏳ Starting...';
  
  const products = [];
  _batchSelected.forEach(function(v) { products.push(v); });
  
  try {
    const payload = {
      products: products.map(function(p) { return { title: p.title, image: p.image, url: p.url }; }),
      style: document.getElementById('batchModalStyle').value,
      duration: document.getElementById('batchModalDuration').value === 'auto' ? 'auto' : (parseInt(document.getElementById('batchModalDuration').value) || 15),
      concurrency: parseInt(document.getElementById('batchModalConcurrency').value) || 3,
    };
    
    const r = await fetch(API + '/batch/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const d = await r.json();
    
    if (d.success) {
      showToast('✅ Batch ' + d.batch_id + ' started! Generating ' + products.length + ' videos with ' + payload.concurrency + ' concurrent workers...', 'success');
      closeBatchModal();
      clearBatchSelection();
      switchTab('pipeline');
      loadBatches();
      loadPipelineJobs();
    } else {
      showToast('❌ ' + (d.error || 'Failed'), 'error');
    }
  } catch(e) {
    showToast('❌ Error: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '🚀 Start Batch';
  }
}

async function loadBatches() {
  const section = document.getElementById('batchHistorySection');
  const list = document.getElementById('batchHistoryList');
  if (!section) return;
  try {
    const r = await fetch(API + '/batch/list');
    const d = await r.json();
    const batches = d.batches || [];
    if (batches.length) {
      section.style.display = 'block';
      list.innerHTML = batches.map(function(b) {
        var pct = b.total > 0 ? Math.round((b.completed + b.failed) / b.total * 100) : 0;
        return '<div class="batch-card">' +
          '<div class="batch-header">' +
          '<div><strong>' + (b.name || b.id) + '</strong> <span class="text-xs text-secondary">' + b.created_at + '</span></div>' +
          '<span class="badge" style="background:' + (b.status==='running'?'rgba(139,92,246,0.1);color:var(--accent-purple)':b.status==='completed'?'rgba(16,185,129,0.1);color:var(--accent-green)':'rgba(244,63,94,0.1);color:var(--accent-magenta)') + '">' + b.status + '</span>' +
          '</div>' +
          '<div style="margin-top:4px;font-size:12px;color:var(--text-secondary)">✅ ' + b.completed + ' ❌ ' + b.failed + ' / ' + b.total + '</div>' +
          '<div class="batch-progress"><div class="bar" style="width:' + pct + '%"></div></div>' +
          '</div>';
      }).join('');
    }
  } catch(e) { /* ignore */ }
}

// ── Late-load JS ──
// ── Pull-to-Refresh for Mobile ──
// ใช้ gesture swipe down ที่ขอบบนเพื่อ refresh หน้าปัจจุบัน
(function() {
  var ptr = document.createElement('div');
  ptr.id = 'ptr-indicator';
  ptr.style.cssText = 'position:fixed;top:-50px;left:0;right:0;z-index:9999;display:flex;align-items:center;justify-content:center;height:50px;background:var(--bg-primary);color:var(--text-secondary);font-size:13px;font-weight:600;transition:top .2s;border-bottom:1px solid var(--border-primary);-webkit-user-select:none;user-select:none';
  ptr.textContent = '↓ ดึงเพื่อรีเฟรช';
  document.body.appendChild(ptr);

  var main = document.querySelector('.main');
  if (!main) return;

  var sy = 0, pulling = false, firstMoved = false;
  main.addEventListener('touchstart', function(e) {
    if (main.scrollTop <= 0) { sy = e.touches[0].clientY; pulling = true; firstMoved = false; }
  }, {passive:true});

  main.addEventListener('touchmove', function(e) {
    if (!pulling) return;
    var dy = e.touches[0].clientY - sy;
    if (dy > 80 && !firstMoved) firstMoved = true;
    if (firstMoved && dy > 80) {
      ptr.style.top = Math.min(Math.max(dy - 50, -50), 0) + 'px';
      ptr.textContent = dy >= 200 ? '↻ ปล่อยเพื่อรีเฟรช' : '↓ ดึงเพื่อรีเฟรช';
    }
  }, {passive:true});

  main.addEventListener('touchend', function(e) {
    if (!pulling) return;
    var dy = e.changedTouches[0].clientY - sy;
    pulling = false;
    if (firstMoved && dy >= 200) {
      ptr.textContent = '↻ กำลังรีเฟรช...';
      ptr.style.top = '0';
      var active = document.querySelector('.page.active');
      if (active) {
        var id = active.id;
        if (id === 'page-publisher') { loadPublisherVideos(); loadPublisherQueue(); }
        else if (typeof window['switchTab'] === 'function') { location.reload(); }
      }
      setTimeout(function() { ptr.style.top = '-50px'; }, 1200);
    } else {
      ptr.style.top = '-50px';
    }
  }, {passive:true});
})();

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/tiktok/sw.js')
      .then(() => console.log('✅ PWA SW registered'))
      .catch(e => console.warn('PWA SW:', e.message));
  });
}
