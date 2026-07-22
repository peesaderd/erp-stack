self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(clients.claim());
});

self.addEventListener('fetch', (e) => {
  // Network-first for API calls
  if (e.request.url.includes('/api/passport/')) {
    e.respondWith(
      fetch(e.request).catch(() => new Response(
        JSON.stringify({ ok: false, error: 'offline' }),
        { status: 503, headers: { 'Content-Type': 'application/json' } }
      ))
    );
    return;
  }
  // Cache-first for static assets
  e.respondWith(
    caches.match(e.request).then((cached) => {
      if (cached) return cached;
      return fetch(e.request).then((res) => {
        if (res.ok && e.request.method === 'GET') {
          const clone = res.clone();
          caches.open('passport-v1').then((cache) => cache.put(e.request, clone));
        }
        return res;
      });
    }).catch(() => {
      // Fallback for offline
      if (e.request.mode === 'navigate') {
        return caches.match('/');
      }
      return new Response('offline', { status: 503 });
    })
  );
});
