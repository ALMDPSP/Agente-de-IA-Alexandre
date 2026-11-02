/* PWA: cache exclusivamente para recursos públicos e tela offline. */
const CACHE = 'meu-controle-peso-pwa-v4';
const ASSETS = ['/static/offline.html','/static/icons/icon-192.png','/static/icons/icon-512.png','/static/icons/apple-touch-icon.png'];
self.addEventListener('install', event => {event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()));});
self.addEventListener('activate', event => {event.waitUntil(Promise.all([caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))),self.clients.claim()]));});
self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  if (req.mode === 'navigate') {
    event.respondWith(fetch(req).catch(async () => (await caches.match('/static/offline.html')) || Response.error()));
    return;
  }
  const u = new URL(req.url);
  if (!ASSETS.includes(u.pathname)) return;
  event.respondWith(caches.match(req).then(cached => cached || fetch(req)));
});
