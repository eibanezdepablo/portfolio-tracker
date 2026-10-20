// Service worker: la app abre al instante desde caché y se actualiza por detrás.
//  · App, iconos, Chart.js y fuentes: caché primero y se refresca en segundo plano
//    (una versión nueva de la app se ve en la siguiente apertura).
//  · data/*.json: red primero; si tarda más de 3 s o no hay conexión, los últimos datos guardados.
const CACHE = 'cartera-v2';
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png'];
const CDN = ['cdn.jsdelivr.net', 'fonts.googleapis.com', 'fonts.gstatic.com'];
const TIMEOUT = 3000;

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

const guardar = (req, r) => {
  if (r && (r.ok || r.type === 'opaque')) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
  return r;
};

function cacheYRefresco(e) {
  const red = fetch(e.request).then(r => guardar(e.request, r));
  e.waitUntil(red.catch(() => {}));
  return caches.match(e.request, { ignoreSearch: true }).then(c => c || red);
}

function redConLimite(req) {
  const red = fetch(req).then(r => guardar(req, r));
  const guardado = caches.match(req, { ignoreSearch: true });
  const limite = new Promise(res => setTimeout(res, TIMEOUT)).then(() => guardado);
  return Promise.race([red.catch(() => guardado), limite.then(c => c || red)]).then(r => r || red);
}

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  const propio = url.origin === location.origin;
  if (!propio && !CDN.includes(url.hostname)) return;          // la API de GitHub va directa
  if (propio && url.pathname.includes('/data/')) e.respondWith(redConLimite(e.request));
  else e.respondWith(cacheYRefresco(e));
});
