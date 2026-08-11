const CACHE_NAME = 'gps-queue-v1';
const STATIC_ASSETS = [
    '/app',
    '/app/manifest.json',
    '/app/icons/icon-192.png',
    '/app/icons/icon-512.png'
];

// Install — cache static assets
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

// Fetch — network first, fallback to cache
self.addEventListener('fetch', event => {
    // Skip API calls — always network
    if (event.request.url.includes('/queue') || 
        event.request.url.includes('/gps') || 
        event.request.url.includes('/webhook') ||
        event.request.url.includes('/analytics')) {
        event.respondWith(fetch(event.request));
        return;
    }

    // Static assets — cache first
    event.respondWith(
        caches.match(event.request).then(cached => {
            return cached || fetch(event.request).then(response => {
                // Cache new static assets
                if (response.status === 200) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            });
        }).catch(() => {
            // Offline fallback
            return caches.match('/app');
        })
    );
});

// Push notification
self.addEventListener('push', event => {
    const data = event.data ? event.data.json() : {};
    const title = data.title || 'Queue Update';
    const body = data.body || 'คิวของคุณถูกเรียกแล้ว!';
    const ticket = data.ticket || '';
    
    event.waitUntil(
        self.registration.showNotification(title, {
            body: body,
            icon: '/app/icons/icon-192.png',
            badge: '/app/icons/icon-192.png',
            vibrate: [200, 100, 200],
            tag: `queue-${ticket}`,
            data: { ticket },
            actions: [
                { action: 'open', title: 'เปิดดูคิว' }
            ]
        })
    );
});

// Notification click
self.addEventListener('notificationclick', event => {
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/app')
    );
});
