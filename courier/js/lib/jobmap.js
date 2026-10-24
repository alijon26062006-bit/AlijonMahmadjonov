// Карта доставки на весь экран — как в приложениях такси и доставки: где курьер, куда ехать, маршрут по дорогам.
// Карта живёт в отдельном слое #map-layer вне #app: экран перерисовывается каждые несколько секунд, а карта — нет
// (не мигает, не сбрасывает масштаб). Библиотека Leaflet лежит в проекте (js/vendor/leaflet) — для APK ничего не нужно.
//
// Подложка: OpenStreetMap (без ключа; в тёмной теме перекрашиваем сами) или MapTiler, если вписан ключ в config.js.
// Маршрут по дорогам: открытый сервер OSRM (для теста; перед запуском заменим на свой или платный).
// Нет интернета — вместо карты спокойный фон, всё остальное работает.

import { MAP } from '../config.js';

/** @typedef {{ lat: number, lng: number }} Pt */

const layer = () => /** @type {HTMLElement} */ (document.getElementById('map-layer'));
const hasPin = p => p?.lat != null && p?.lng != null;
const dark = () => document.documentElement.dataset.theme === 'dark' || (document.documentElement.dataset.theme !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);

let L = null, map = null, tiles = null, tileDark = null, line = null, lastKey = '', follow = true;
const marks = {};
/** Последний расчёт пути: минуты и км по дорогам (или null, пока не посчитали). */
export const route = { min: null, km: null };
let onRoute = () => {};
/** Что сделать, когда маршрут посчитан (перерисовать «7 мин · 2,1 км»). */
export const onRouteReady = fn => { onRoute = fn; };

// Загружаем один раз: экран перерисовывается часто, и без этого второй вызов подгрузил бы вторую копию Leaflet —
// карта от одной копии, линии от другой, и внутренние проверки библиотеки ломаются.
let loading = null;
function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  return loading ||= new Promise((ok, no) => {
    const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = 'js/vendor/leaflet/leaflet.css'; document.head.append(css);
    const js = document.createElement('script'); js.src = 'js/vendor/leaflet/leaflet.js';
    js.onload = () => ok(window.L); js.onerror = () => { loading = null; no(new Error('карта не загрузилась')); };
    document.head.append(js);
  });
}

const pin = (cls, glyph) => `<span class="mpin ${cls}"><svg viewBox="0 0 24 24" aria-hidden="true">${glyph}</svg></span>`;
const GLYPH = {
  shop: '<path d="M4 10v9h16v-9M3 10l2-5h14l2 5M9 19v-5h6v5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
  client: '<path d="M4 11l8-6 8 6v8a1 1 0 0 1-1 1h-4v-5H9v5H5a1 1 0 0 1-1-1z" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/>',
};

function useTiles() {
  const want = dark();
  if (tiles && tileDark === want) return;
  tiles?.remove();
  const key = MAP.maptilerKey;
  tiles = key
    ? L.tileLayer(`https://api.maptiler.com/maps/${want ? 'streets-v2-dark' : 'streets-v2'}/256/{z}/{x}/{y}.png?key=${key}`,
      { maxZoom: 19, attribution: '&copy; MapTiler &copy; OpenStreetMap' })
    : L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' });
  tiles.addTo(map);
  // у OpenStreetMap нет тёмной подложки — перекрашиваем плитки фильтром (у MapTiler тёмная своя)
  layer().classList.toggle('dark-tiles', want && !key);
  tileDark = want;
}

function setMark(key, p, html, size, anchor, z = 0) {
  if (!hasPin(p)) { marks[key]?.remove(); delete marks[key]; return; }
  if (!marks[key]) marks[key] = L.marker([p.lat, p.lng], { icon: L.divIcon({ className: 'mwrap', html, iconSize: size, iconAnchor: anchor }), zIndexOffset: z, keyboard: false }).addTo(map);
  else marks[key].setLatLng([p.lat, p.lng]);
}

/** Маршрут по дорогам от a до b. Не получилось — пунктир по прямой и примерное время. */
async function drawRoute(a, b) {
  const key = `${a.lat.toFixed(3)},${a.lng.toFixed(3)}>${b.lat.toFixed(4)},${b.lng.toFixed(4)}`;
  if (key === lastKey) return; lastKey = key;
  let pts = [[a.lat, a.lng], [b.lat, b.lng]], straight = true;
  try {
    const r = await fetch(`https://router.project-osrm.org/route/v1/driving/${a.lng},${a.lat};${b.lng},${b.lat}?overview=full&geometries=geojson`, { signal: AbortSignal.timeout(6000) });
    const j = r.ok ? await r.json() : null, best = j?.routes?.[0];
    if (best) {
      pts = best.geometry.coordinates.map(([x, y]) => [y, x]); straight = false;
      route.min = Math.max(1, Math.round(best.duration / 60)); route.km = Math.round(best.distance / 100) / 10;
    }
  } catch { /* сервера маршрутов нет — рисуем по прямой */ }
  if (straight) {
    const d = map.distance([a.lat, a.lng], [b.lat, b.lng]) / 1000 * 1.3;
    route.km = Math.round(d * 10) / 10; route.min = Math.max(1, Math.round(3 + d * 2.5));
  }
  line?.remove();
  line = L.layerGroup([
    L.polyline(pts, { color: dark() ? '#000' : '#1f1e1c', weight: 9, opacity: .35, lineCap: 'round' }),
    L.polyline(pts, { color: '#fce000', weight: 5, lineCap: 'round', dashArray: straight ? '2 10' : null }),
  ]).addTo(map);
  onRoute();
}

// обновления карты — строго по одному: пока идёт одно (ждём библиотеку, маршрут), следующее ждёт и берёт свежие точки
let running = false, pending = null, wanted = false;   // wanted — карту сейчас должно быть видно
/**
 * Показать или обновить карту доставки.
 * @param {{ me: Pt|null, target: Pt|null, kind: 'shop'|'client', shop: Pt|null, client: Pt|null }} s
 */
export async function showJobMap(s) {
  wanted = true; pending = s; if (running) return;
  running = true;
  try { while (pending) { const next = pending; pending = null; await update(next); } }
  catch (e) { console.warn('map', e); }
  finally { running = false; }
}
async function update(s) {
  const el = layer(); if (!el || !wanted) return;
  el.hidden = false; document.body.classList.add('has-map');
  try { L = await loadLeaflet(); } catch { el.classList.add('nomap'); return; }
  if (!wanted) return;   // пока грузилась библиотека, заказ закрыли
  if (!map) {
    map = L.map(el, { zoomControl: false, attributionControl: true, tap: true });
    map.attributionControl.setPrefix('');
    map.on('dragstart', () => { follow = false; });
    map.setView(hasPin(s.target) ? [s.target.lat, s.target.lng] : [37.267, 68.133], 15);
  }
  useTiles();
  setMark('shop', s.shop, pin('shop', GLYPH.shop), [40, 48], [20, 46], 10);
  setMark('client', s.client, pin('client', GLYPH.client), [40, 48], [20, 46], 10);
  marks.shop?.getElement()?.classList.toggle('dim', s.kind === 'client');   // магазин уже позади
  setMark('me', s.me, '<span class="mme"><i></i></span>', [28, 28], [14, 14], 20);
  if (hasPin(s.me) && hasPin(s.target)) await drawRoute(s.me, s.target);
  else if (hasPin(s.shop) && hasPin(s.client)) await drawRoute(s.shop, s.client);
  if (follow) fit(s);
  setTimeout(() => map?.invalidateSize(), 50);
}

function fit(s) {
  const pts = [s.me, s.target].filter(hasPin).map(p => [p.lat, p.lng]);
  if (pts.length === 2) map.fitBounds(pts, { paddingTopLeft: [40, 90], paddingBottomRight: [40, Math.round(innerHeight * 0.55)], maxZoom: 16 });
  else if (pts.length === 1) map.setView(pts[0], 16);
}
/** Вернуть карту к курьеру и цели (кнопка «По центру»). */
export function recenter(s) { follow = true; if (map) fit(s); }

/** Убрать карту (заказа нет). */
export function hideJobMap() {
  if (!wanted && !pending) return;
  wanted = false; pending = null;
  const el = layer(); if (el) el.hidden = true;
  document.body.classList.remove('has-map');
  lastKey = ''; route.min = route.km = null; follow = true;
  line?.remove(); line = null;
  for (const k of Object.keys(marks)) { marks[k].remove(); delete marks[k]; }
}
