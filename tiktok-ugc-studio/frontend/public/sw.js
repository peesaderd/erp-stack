
const CACHE_NAME = 'tus-cache-v20260724-v2';
self.addEventListener('install', (event) => {
  self.skipWaiting();
});
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          return caches.delete(cache);
        })
      );
    }).then(() => self.clients.claim())
  );
});
self.addEventListener('fetch', (event) => {
  // Network first strategy
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
