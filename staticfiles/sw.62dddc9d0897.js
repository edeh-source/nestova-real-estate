/**
 * Nestova Service Worker
 * Provides offline support and caching for the PWA.
 */

const CACHE_VERSION = 'v1';
const STATIC_CACHE  = `nestova-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `nestova-dynamic-${CACHE_VERSION}`;

/* ---- Assets to pre-cache on install ---- */
const STATIC_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/assets/img/android-chrome-192x192.png',
  '/static/assets/img/android-chrome-512x512.png',
  '/static/assets/img/apple-touch-icon.png',
  '/static/assets/img/favicon-32x32.png',
  '/static/assets/img/logo.webp',
];

/* ---- Install: pre-cache static shell ---- */
self.addEventListener('install', event => {
  console.log('[SW] Installing Nestova Service Worker…');
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

/* ---- Activate: clean up old caches ---- */
self.addEventListener('activate', event => {
  console.log('[SW] Activating Nestova Service Worker…');
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== STATIC_CACHE && k !== DYNAMIC_CACHE)
          .map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

/* ---- Fetch: Network-first for HTML pages, Cache-first for assets ---- */
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle same-origin and GET requests
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  // For HTML navigation: network-first, fall back to offline page
  if (request.headers.get('Accept') && request.headers.get('Accept').includes('text/html')) {
    event.respondWith(networkFirstStrategy(request));
    return;
  }

  // For static assets: cache-first
  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')) {
    event.respondWith(cacheFirstStrategy(request));
    return;
  }

  // Default: network-first
  event.respondWith(networkFirstStrategy(request));
});

/* ---- Strategy: Network First ---- */
async function networkFirstStrategy(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    // Return offline fallback for HTML navigation
    if (request.headers.get('Accept') && request.headers.get('Accept').includes('text/html')) {
      return caches.match('/');
    }
  }
}

/* ---- Strategy: Cache First ---- */
async function cacheFirstStrategy(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (err) {
    console.warn('[SW] Fetch failed for:', request.url, err);
  }
}
