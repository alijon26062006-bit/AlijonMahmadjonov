import * as api from '../api.js';
import { ago, esc, money, phone, tel } from '../lib/format.js';
import { empty, head, ICON, tabs } from '../ui.js';

// Курьеры: кто на линии, кто везёт заказ, кто давно без связи, сколько заработал и сколько наличных на руках. И карта.

const STEP = { going: 'едет в магазин', at_shop: 'в магазине', picked: 'везёт покупателю', at_client: 'у двери покупателя' };
const fresh = c => c.loc_at && Date.now() - Date.parse(c.loc_at) < 15 * 60e3;

export const couriers = {
  title: 'Курьеры',
  load: () => api.couriers(),
  html(list, q) {
    const f = q.f || '';
    const pick = { online: c => c.online && c.status === 'active', busy: c => !!c.job, lost: c => c.online && !fresh(c), blocked: c => c.status === 'blocked' };
    const shown = f ? list.filter(pick[f] || Boolean) : list;
    return `${head('Курьеры', 'Кто на линии, кто везёт заказ и кто пропал со связи', `<a class="btn" href="#/map">${ICON.map} Карта</a>`)}
      ${tabs('f', f, [['', 'Все', list.length], ['online', 'На линии', list.filter(pick.online).length], ['busy', 'С заказом', list.filter(pick.busy).length],
        ['lost', 'Без связи', list.filter(pick.lost).length], ['blocked', 'Заблокированы', list.filter(pick.blocked).length]])}
      ${shown.length ? `<div class="list">${shown.map(c => {
        const state = c.status === 'blocked' ? ['bad', 'Заблокирован'] : c.job ? ['info', `Заказ № ${c.job.no}: ${STEP[c.job.step] || c.job.step}`]
          : c.online ? (fresh(c) ? ['ok', 'На линии, свободен'] : ['warn', 'На линии, без связи']) : ['', 'Не на линии'];
        return `<div class="item"><span class="avatar" aria-hidden="true">${esc(c.name.charAt(0).toUpperCase())}</span>
          <span class="item-main"><a class="link" href="#/person/${c.id}"><b>${esc(c.name)}</b></a> <span class="chip ${state[0]}">${esc(state[1])}</span>
            <span class="item-sub">${esc([c.car, c.plate].filter(Boolean).join(' · ') || 'машина не указана')} · ${c.rating_count ? `${c.rating} ★ (${c.rating_count})` : 'без оценок'}</span>
            <span class="item-sub">место ${ago(c.loc_at)} · за 7 дней ${c.done_7d} доставок, ${money(c.earned_7d)} · наличные сегодня ${money(c.cash_today)}${c.returned ? ` · возвратов ${c.returned}` : ''}</span>
            ${c.status === 'blocked' && c.block_reason ? `<span class="item-sub bad-t">${esc(c.block_reason)}</span>` : ''}</span>
          <span class="item-end"><a class="btn sm" href="${tel(c.phone)}" aria-label="Позвонить ${esc(c.name)}">${ICON.phone}<span class="hide-sm">${phone(c.phone)}</span></a>
            ${c.job ? `<a class="btn sm" href="#/order/${encodeURIComponent(c.job.id)}">Заказ</a>` : ''}</span></div>`;
      }).join('')}</div>` : empty('Курьеров нет', f ? 'Уберите фильтр' : 'Курьер появится здесь, когда заполнит анкету в приложении /courier/')}`;
  },
};

// ---------- карта ----------
let L = null, mapObj = null, layer = null, loading = null;
function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  return loading ||= new Promise((ok, no) => {
    const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = 'js/vendor/leaflet/leaflet.css'; document.head.append(css);
    const js = document.createElement('script'); js.src = 'js/vendor/leaflet/leaflet.js';
    js.onload = () => ok(window.L); js.onerror = () => { loading = null; no(new Error('Карта не загрузилась')); };
    document.head.append(js);
  });
}
const dotIcon = (cls, text = '') => L.divIcon({ className: 'mk-wrap', html: `<span class="mk ${cls}">${esc(text)}</span>`, iconSize: [28, 28], iconAnchor: [14, 14] });

function draw(d) {
  if (!mapObj) return;
  layer?.remove(); layer = L.layerGroup().addTo(mapObj);
  const pts = [];
  for (const s of d.shops) {
    pts.push([s.lat, s.lng]);
    L.marker([s.lat, s.lng], { icon: dotIcon(`shop${s.blocked ? ' off' : s.paused ? ' paused' : ''}`, 'М') }).bindPopup(`<b>${esc(s.name)}</b><br><a href="#/shop/${s.id}">Открыть магазин</a>`).addTo(layer);
  }
  for (const o of d.orders) {
    if (o.to_lat == null || o.to_lng == null) continue;
    pts.push([o.to_lat, o.to_lng]);
    L.marker([o.to_lat, o.to_lng], { icon: dotIcon('client', '') }).bindPopup(`<b>Заказ № ${o.no}</b><br><a href="#/order/${encodeURIComponent(o.id)}">Открыть заказ</a>`).addTo(layer);
    if (o.shop_lat != null) L.polyline([[o.shop_lat, o.shop_lng], [o.to_lat, o.to_lng]], { color: '#8a8780', weight: 2, dashArray: '4 6' }).addTo(layer);
  }
  for (const c of d.couriers) {
    pts.push([c.lat, c.lng]);
    L.marker([c.lat, c.lng], { icon: dotIcon(`courier${c.busy ? ' busy' : ''}`, c.name.charAt(0).toUpperCase()), zIndexOffset: 100 })
      .bindPopup(`<b>${esc(c.name)}</b><br>${c.busy ? 'везёт заказ' : 'свободен'} · место ${ago(c.loc_at)}<br><a href="#/person/${c.id}">Открыть</a>`).addTo(layer);
  }
  if (pts.length && !mapObj._fitted) { mapObj.fitBounds(pts, { padding: [40, 40], maxZoom: 15, animate: false }); mapObj._fitted = true; }
}

export const map = {
  title: 'Карта',
  live: true,
  load: () => api.map(),
  html(d) {
    return `${head('Карта', `Курьеры на линии: ${d.couriers.length} · заказы в работе: ${d.orders.length} · магазины с точкой: ${d.shops.length}`)}
      <p class="small muted legend"><span class="mk courier">К</span> свободный курьер <span class="mk courier busy">К</span> везёт заказ
        <span class="mk shop">М</span> магазин <span class="mk client"></span> куда везут</p>
      <div id="admin-map" class="admin-map" role="region" aria-label="Карта курьеров и заказов"></div>`;
  },
  async after(d) {
    const el = document.getElementById('admin-map'); if (!el) return;
    try { L = await loadLeaflet(); } catch { el.innerHTML = '<div class="empty"><b>Карта не загрузилась</b><span>Список курьеров работает: раздел «Курьеры»</span></div>'; return; }
    if (!document.body.contains(el)) return;
    map.leave();
    mapObj = L.map(el, { zoomControl: true }).setView([37.267, 68.133], 13, { animate: false });
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(mapObj);
    draw(d);
  },
  /** Обновить точки без перерисовки экрана — карта не мигает и не сбрасывает масштаб. */
  update(d) { draw(d); const p = document.querySelector('.page-head .muted'); if (p) p.textContent = `Курьеры на линии: ${d.couriers.length} · заказы в работе: ${d.orders.length} · магазины с точкой: ${d.shops.length}`; },
  // карту убираем при уходе с экрана; анимацию масштаба сначала останавливаем — иначе Leaflet дорисовывает в уже удалённый блок
  leave() { if (mapObj) { mapObj.stop(); mapObj.off(); mapObj.remove(); } mapObj = null; layer = null; },
};
