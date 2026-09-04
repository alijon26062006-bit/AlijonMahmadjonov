/* Кэш сайта. Первый заход — обычная загрузка, дальше страница открывается
   мгновенно из памяти телефона, даже когда связь еле дышит или её нет совсем.

   Правила разные, потому что данные разные:
   — оболочка сайта и шрифты меняются редко: берём из кэша, обновляем молча;
   — меню с сервера показываем сохранённое сразу, а свежее подкладываем следом;
   — заказы через кэш не ходят никогда: их место только на сервере. */

const VERSION = 'v1';
const SHELL = `burger-shell-${VERSION}`;
const DATA = `burger-data-${VERSION}`;
const PHOTOS = `burger-photos-${VERSION}`;

const SHELL_FILES = [
  './',
  'index.html',
  'css/style.css',
  'css/fonts.css',
  'js/menu.js',
  'js/main.js',
  'manifest.webmanifest',
  'assets/logo.jpg',
  'assets/fonts/manrope-400-800-cyrillic.woff2',
  'assets/fonts/manrope-400-800-latin.woff2',
  'assets/fonts/bebas-400-latin.woff2',
  'assets/fonts/plexmono-400-cyrillic.woff2',
  'assets/fonts/plexmono-400-latin.woff2',
];

self.addEventListener('install', e => {
  // addAll падает целиком, если хоть один файл не нашёлся, — кладём по одному
  e.waitUntil(caches.open(SHELL)
    .then(c => Promise.all(SHELL_FILES.map(f => c.add(f).catch(() => {}))))
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  const mine = [SHELL, DATA, PHOTOS];
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => !mine.includes(k)).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

/* Свежее, но с подстраховкой: пока сервер думает, показываем сохранённое. */
async function freshOrSaved(req, cacheName) {
  const cache = await caches.open(cacheName);
  const saved = await cache.match(req);

  const fresh = fetch(req).then(res => {
    if (res.ok) cache.put(req, res.clone());
    return res;
  }).catch(() => null);

  if (saved) {
    fresh.catch(() => {});          // обновится в фоне, ответ уже отдан
    return saved;
  }
  return (await fresh) || Response.error();
}

async function savedOrFresh(req, cacheName) {
  const cache = await caches.open(cacheName);
  const saved = await cache.match(req);
  if (saved) return saved;

  const res = await fetch(req);
  if (res.ok) cache.put(req, res.clone());
  return res;
}

self.addEventListener('fetch', e => {
  const { request } = e;
  if (request.method !== 'GET') return;              // заказы идут только на сервер

  const url = new URL(request.url);
  if (url.origin !== location.origin) return;        // чужие адреса не трогаем

  // админка, кухня, курьеры, бот — всегда живьём, кэш тут только навредит
  if (/^\/(admin|kitchen|courier|tg)/.test(url.pathname)) return;

  /* Оболочка рабочих панелей (стили, скрипты, иконки). Планшет на кухне и
     телефон курьера в подъезде поднимут экран даже на моргающем wi-fi —
     а сами заказы всё равно придут только с сервера. */
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(freshOrSaved(request, SHELL));
    return;
  }

  if (url.pathname.endsWith('/api/menu')) {
    e.respondWith(freshOrSaved(request, DATA));
    return;
  }
  if (url.pathname.startsWith('/api/')) return;

  if (/\.(jpg|jpeg|png|webp|avif)$/i.test(url.pathname)) {
    e.respondWith(savedOrFresh(request, PHOTOS).catch(() => caches.match('assets/logo.jpg')));
    return;
  }

  // страница: сначала сеть — вдруг поменялось меню; не ответила — отдаём сохранённое
  if (request.mode === 'navigate') {
    e.respondWith(freshOrSaved(request, SHELL).catch(() => caches.match('index.html')));
    return;
  }

  e.respondWith(caches.match(request).then(r => r || fetch(request)));
});
