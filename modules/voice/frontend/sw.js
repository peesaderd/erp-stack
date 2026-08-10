const CACHE_NAME = 'voice-pos-v1';
const ASSETS = [
  '/voice/',
  '/voice/index.html',
  '/voice/app.js?v=2',
  '/voice/manifest.json',
  '/voice/icon-192.png',
  '/voice/icon-512.png'
];

// Install: cache core assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[SW] Caching assets');
        return cache.addAll(ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(key => key !== CACHE_NAME)
          .map(key => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: network first, fallback to cache (for API requests), cache first for static
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  // API calls → network only, no cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(event.request).catch(() => {
      return new Response(JSON.stringify({ 
        success: false, 
        error: 'Network offline', 
        reply: 'ขออภัยครับ ไม่มีการเชื่อมต่ออินเทอร์เน็ต' 
      }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      });
    }));
    return;
  }

  // Static assets → cache first
  event.respondWith(
    caches.match(event.request)
      .then(cached => cached || fetch(event.request))
      .catch(() => {
        // Offline fallback for HTML
        if (event.request.headers.get('Accept')?.includes('text/html')) {
          return caches.match('/voice/index.html');
        }
        return new Response('Offline', { status: 503 });
      })
  );
});
