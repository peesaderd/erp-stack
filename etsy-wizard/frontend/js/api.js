/* ─── API Client ─── */
const API = {
  BASE: '/etsy',
  
  async _fetch(path, opts={}) {
    const url = this.BASE + path;
    const headers = { 'Content-Type': 'application/json', ...opts.headers };
    try {
      const res = await fetch(url, { ...opts, headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      return await res.json();
    } catch(e) {
      console.warn(`API ${path}:`, e);
      throw e;
    }
  },

  // Health
  health: () => API._fetch('/health'),

  // Stats
  getStats: async () => {
    // Try real endpoint, fallback to mock
    try {
      const data = await API._fetch('/pod/stats');
      if (data) return data;
    } catch(e) {}
    return API._mockStats();
  },

  // Wizard
  wizardStart: (provider) => API._fetch('/pod/wizard/start', { method:'POST', body:JSON.stringify({provider}) }),
  wizardStep: (sessionId, step, data) => API._fetch('/pod/wizard/step', { method:'POST', body:JSON.stringify({session_id:sessionId, step, data}) }),
  wizardCancel: (sessionId) => API._fetch('/pod/wizard/cancel', { method:'POST', body:JSON.stringify({session_id:sessionId}) }),
  
  // Products
  getProducts: () => API._fetch('/pod/products'),
  getPrintInfo: (productId) => API._fetch(`/pod/print-info/${productId}`),
  
  // Listings / Drafts
  getDrafts: (shopId) => API._fetch(`/listing/drafts/${shopId}`),
  saveDraft: (data) => API._fetch('/listing/draft', { method:'POST', body:JSON.stringify(data) }),
  
  // AI Tools
  generateListing: (data) => API._fetch('/ai/generate-listing', { method:'POST', body:JSON.stringify(data) }),
  optimizeTags: (data) => API._fetch('/ai/optimize-tags', { method:'POST', body:JSON.stringify(data) }),
  generateImage: (data) => API._fetch('/ai/generate-image', { method:'POST', body:JSON.stringify(data) }),
  generateProduct: (data) => API._fetch('/ai/generate-product', { method:'POST', body:JSON.stringify(data) }),
  generateConcept: (data) => API._fetch('/ai/generate-concept', { method:'POST', body:JSON.stringify(data) }),
  fixListing: (data) => API._fetch('/validate/listing', { method:'POST', body:JSON.stringify(data) }),

  // Mock data for display
  _mockStats() {
    return {
      revenue: { value: 361, change: '+12.5%', trend: 'up' },
      listings: { value: 6, change: '+3 new', trend: 'up' },
      orders: { value: 3, change: '+8.3%', trend: 'up' },
      avgOrder: { value: 45.13, change: '-2.1%', trend: 'down' },
      weeklySales: [
        { day: 'Mon', value: 0 }, { day: 'Tue', value: 180 },
        { day: 'Wed', value: 240 }, { day: 'Thu', value: 320 },
        { day: 'Fri', value: 560 }, { day: 'Sat', value: 720 },
        { day: 'Sun', value: 480 }
      ],
      listingStatus: [
        { label: 'Active', value: 6, color: '#22c55e' },
        { label: 'Draft', value: 1, color: '#eab308' },
        { label: 'Expired', value: 1, color: '#7f7f8f' }
      ],
      recentOrders: [
        { id: '#5001', buyer: 'Sarah Johnson', date: '2026-06-05', total: 24, status: 'Shipped' },
        { id: '#5002', buyer: 'Michael Chen', date: '2026-06-04', total: 68, status: 'Paid' },
        { id: '#5003', buyer: 'Emma Williams', date: '2026-06-04', total: 45, status: 'Paid' },
        { id: '#5004', buyer: 'James Rodriguez', date: '2026-06-03', total: 56, status: 'Processing' },
        { id: '#5005', buyer: 'Olivia Brown', date: '2026-06-02', total: 24, status: 'Shipped' }
      ],
      activeListings: [
        { name: 'Vintage Botanical Art Print — Set of 3', price: 24, views: 3421, favs: 189, stock: 25, status: 'Active' },
        { name: 'Hand-Carved Wooden Spoon Set', price: 45, views: 2156, favs: 94, stock: 12, status: 'Active' },
        { name: 'Minimalist Ceramic Vase — Stoneware', price: 32, views: 1872, favs: 156, stock: 8, status: 'Active' },
        { name: 'Macrame Wall Hanging — Large', price: 68, views: 891, favs: 67, stock: 5, status: 'Active' },
        { name: 'Scented Soy Candle Trio — Lavender', price: 28, views: 4567, favs: 234, stock: 30, status: 'Active' }
      ]
    };
  }
};
