// Карта для выбора места магазина: Leaflet + OpenStreetMap, без ключей.
// Библиотека грузится только когда карта действительно нужна.

const LEAFLET = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet';
let loading = null;

export function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = `${LEAFLET}.css`;
    document.head.append(css);
    const js = document.createElement('script');
    js.src = `${LEAFLET}.js`;
    js.onload = () => resolve(window.L);
    js.onerror = () => { loading = null; reject(new Error('Не удалось загрузить карту. Проверьте интернет.')); };
    document.head.append(js);
  });
  return loading;
}

/**
 * Карта с перетаскиваемой меткой. onMove({ lat, lng }) вызывается после каждого перемещения.
 * Возвращает { moveTo(lat, lng, zoom), destroy() }.
 */
export async function mountPicker(el, { lat, lng, zoom = 15 }, onMove) {
  const L = await loadLeaflet();
  const map = L.map(el, { zoomControl: true, attributionControl: true }).setView([lat, lng], zoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);
  const icon = L.divIcon({
    className: 'pin-icon',
    html: '<svg viewBox="0 0 24 30" width="30" height="38"><path d="M12 29s10-10 10-17A10 10 0 0 0 2 12c0 7 10 17 10 17z" fill="#b3261e"/><circle cx="12" cy="12" r="4" fill="#fff"/></svg>',
    iconSize: [30, 38], iconAnchor: [15, 38],
  });
  const marker = L.marker([lat, lng], { draggable: true, icon }).addTo(map);
  const emit = () => { const p = marker.getLatLng(); onMove({ lat: +p.lat.toFixed(6), lng: +p.lng.toFixed(6) }); };
  marker.on('dragend', emit);
  map.on('click', e => { marker.setLatLng(e.latlng); emit(); });
  // контейнер мог поменять размер, пока грузилась библиотека
  setTimeout(() => map.invalidateSize(), 50);
  return {
    moveTo(la, ln, z = map.getZoom()) { marker.setLatLng([la, ln]); map.setView([la, ln], z); emit(); },
    destroy() { map.remove(); },
  };
}

/** Текущее местоположение устройства. Работает только по https. */
export function locate() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('Телефон не умеет определять место. Поставьте метку пальцем.'));
    if (!window.isSecureContext) return reject(new Error('Определение места работает только на защищённом адресе (https). Поставьте метку пальцем.'));
    navigator.geolocation.getCurrentPosition(
      p => resolve({ lat: +p.coords.latitude.toFixed(6), lng: +p.coords.longitude.toFixed(6) }),
      err => reject(new Error(err.code === 1
        ? 'Нет доступа к местоположению. Разрешите его в настройках браузера или поставьте метку пальцем.'
        : 'Не удалось определить место. Поставьте метку пальцем.')),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 },
    );
  });
}

/** Место по координатам: улица с домом и город. Пустые строки, если сервис не ответил. */
export async function placeAt({ lat, lng }) {
  try {
    const r = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}&zoom=18&accept-language=ru`);
    if (!r.ok) return { street: '', city: '' };
    const a = (await r.json()).address || {};
    const street = a.road || a.pedestrian || a.neighbourhood || a.suburb || '';
    return { street: [street, a.house_number].filter(Boolean).join(', '), city: a.city || a.town || a.village || a.municipality || a.county || '' };
  } catch {
    return { street: '', city: '' };
  }
}
/** Адрес по координатам: «улица, дом». Пустая строка, если сервис не ответил. */
export const addressAt = async pt => (await placeAt(pt)).street;

/** Найти город или адрес по названию: { lat, lng } или null. */
export async function findPlace(q) {
  try {
    const r = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&accept-language=ru&q=${encodeURIComponent(q)}`);
    const [f] = r.ok ? await r.json() : [];
    return f ? { lat: +(+f.lat).toFixed(6), lng: +(+f.lon).toFixed(6) } : null;
  } catch {
    return null;
  }
}
