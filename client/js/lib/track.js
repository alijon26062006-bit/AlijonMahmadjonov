import { loadLeaflet } from './map.js';

// Живая карта доставки: курьер (жёлтая точка с машиной) едет к дому покупателя.
// Карта одна на экран заказа и переживает перерисовки: app.js переносит её узел в новую разметку.

const maps = new WeakMap();
const carPin = '<svg viewBox="0 0 40 40" width="40" height="40"><circle cx="20" cy="20" r="18" fill="#fce000" stroke="#1f1e1c" stroke-width="2.5"/><path d="M12 23v-4l2-5h12l2 5v4M12 23h16v3h-2v-2M14 23v3h-2M15.5 21h.01M24.5 21h.01M12 19h16" fill="none" stroke="#1f1e1c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const homePin = '<svg viewBox="0 0 24 30" width="30" height="38"><path d="M12 29s10-10 10-17A10 10 0 0 0 2 12c0 7 10 17 10 17z" fill="#1f1e1c"/><path d="M7.5 12.5 12 8.8l4.5 3.7V17h-9z" fill="#fff"/></svg>';

/** Показать или обновить карту в el: courier { lat, lng } и home { lat, lng }. Без интернета — тихо ничего. */
export async function showTrack(el, { courier, home }) {
  if (!el || !courier) return;
  let m = maps.get(el);
  try {
    const L = await loadLeaflet();
    if (!m) {
      const map = L.map(el, { zoomControl: false, attributionControl: true, dragging: true, scrollWheelZoom: false });
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(map);
      const car = L.marker([courier.lat, courier.lng], { icon: L.divIcon({ className: 'pin-icon', html: carPin, iconSize: [40, 40], iconAnchor: [20, 20] }), zIndexOffset: 1000 }).addTo(map);
      const house = home ? L.marker([home.lat, home.lng], { icon: L.divIcon({ className: 'pin-icon', html: homePin, iconSize: [30, 38], iconAnchor: [15, 38] }) }).addTo(map) : null;
      m = { map, car, house, fitted: false }; maps.set(el, m);
      setTimeout(() => map.invalidateSize(), 60);
    }
    m.car.setLatLng([courier.lat, courier.lng]);
    // первый раз показываем обоих; дальше не дёргаем карту, если покупатель её двигал
    if (!m.fitted) { m.fitted = true; m.house ? m.map.fitBounds([[courier.lat, courier.lng], [home.lat, home.lng]], { padding: [48, 48], maxZoom: 16 }) : m.map.setView([courier.lat, courier.lng], 15); }
  } catch { el.hidden = true; }
}
