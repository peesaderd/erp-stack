// Business OS — Modular PWA Service Worker
// ==========================================
// Drop-in PWA for any Business OS frontend.
// To opt in: <link rel="manifest" href="/bos-pwa/manifest.json">
//            <script>navigator.serviceWorker.register('/bos-pwa/sw.js')</script>

const CACHE = "bos-pwa-v2";

// Known Business OS static paths (auto-extended at runtime)
const BOS_PATHS = [
  "/etsy-dashboard/",
  "/tiktok/",
  "/bos-pwa/",
];

// ─── Install ──────────────────────────────────────────────
self.addEventListener("install", (event) => {
  // Pre-cache shared PWA assets
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      await cache.addAll([
        "/bos-pwa/offline.html",
        "/bos-pwa/icon-192.svg",
        "/bos-pwa/icon-512.svg",
      ]);
    })()
  );
  self.skipWaiting();
});

// ─── Activate ─────────────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // Clean old cache versions
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => k.startsWith("bos-") && k !== CACHE)
          .map((k) => caches.delete(k))
      );
    })()
  );
  self.clients.claim();
});

// ─── Fetch ────────────────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Same-origin only
  if (url.origin !== self.location.origin) return;

  const path = url.pathname;

  // Only handle Business OS paths
  const isBosPath = BOS_PATHS.some((p) => path.startsWith(p));
  if (!isBosPath) return;

  // Static assets: JS, CSS, SVG, PNG, JSON, fonts → cache-first
  if (path.match(/\.(js|css|svg|png|ico|json|woff2?)$/)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // ── NAVIGATION: always network-only ─────────────────
  // Never cache HTML pages. This ensures pull-to-refresh
  // works correctly in PWA mode after SPA tab switches.
  if (request.mode === "navigate") {
    event.respondWith(fetch(request));
    return;
  }
});

// ─── Strategies ───────────────────────────────────────────

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response("", { status: 503 });
  }
}
