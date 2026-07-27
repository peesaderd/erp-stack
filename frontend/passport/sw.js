// Passport Photo AI — Service Worker v2
// ล้าง cache เก่าทั้งหมด, network-first อย่างเดียว

const CACHE = 'passport-v2';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    Promise.all([
      // ล้าง cache เก่าหมด
      caches.keys().then((keys) =>
        Promise.all(keys.map((k) => { if (k !== CACHE) return caches.delete(k); }))
      ),
      clients.claim(),
    ])
  );
});

self.addEventListener('fetch', (e) => {
  // Network-first for EVERYTHING — ไม่ cache หน้าเว็บ
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        // Cache only API responses for offline
        if (e.request.url.includes('/api/passport/')) {
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, clone));
        }
        return res;
      })
      .catch(() => {
        // Offline fallback: serve cached API or basic offline page
        return caches.match(e.request).then((cached) => {
          if (cached) return cached;
          if (e.request.mode === 'navigate') {
            return new Response(
              '<html><body><h1>Offline</h1><p>กรุณาเชื่อมต่ออินเทอร์เน็ต</p></body></html>',
              { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
            );
          }
          return new Response('Offline', { status: 503 });
        });
      })
  );
});
