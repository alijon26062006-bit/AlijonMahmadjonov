import { ROAD_FACTOR } from '../config.js';

// Маршрут во внешнем навигаторе и расстояния. Чистые функции — без DOM, легко проверить.

const rad = d => d * Math.PI / 180;
/** Расстояние по прямой, км. */
export function straightKm(a, b) {
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}
const hasPin = p => p?.lat != null && p?.lng != null;
/** Примерно по дороге, км (как считает база), или null, если одна из точек неизвестна. */
export const roadKm = (a, b) => hasPin(a) && hasPin(b) ? Math.max(0.1, Math.round(straightKm(a, b) * ROAD_FACTOR * 10) / 10) : null;
export const kmText = km => km == null ? '' : km < 1 ? `${Math.round(km * 1000 / 10) * 10} м` : `${km.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} км`;

/**
 * Ссылка на маршрут до точки. Если метки нет — поиск по адресу.
 * Возвращает { url, fallback }: fallback — веб-версия, если приложения навигатора на телефоне нет.
 */
export function routeUrl(app, { lat, lng, address = '' }) {
  const pin = lat != null && lng != null, q = encodeURIComponent(address);
  const yandexWeb = pin ? `https://yandex.ru/maps/?rtext=~${lat},${lng}&rtt=auto` : `https://yandex.ru/maps/?text=${q}`;
  switch (app) {
    case 'yandexnavi': return pin ? { url: `yandexnavi://build_route_on_map?lat_to=${lat}&lon_to=${lng}`, fallback: yandexWeb } : { url: yandexWeb };
    case '2gis': return { url: pin ? `https://2gis.ru/routeSearch/rsType/car/to/${lng},${lat}` : `https://2gis.ru/search/${q}` };
    case 'google': return { url: pin ? `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving` : `https://www.google.com/maps/search/?api=1&query=${q}` };
    default: return { url: yandexWeb };
  }
}

/** Номер для WhatsApp: только цифры с кодом страны. */
export const waUrl = phone => `https://wa.me/${String(phone || '').replace(/\D/g, '')}`;
