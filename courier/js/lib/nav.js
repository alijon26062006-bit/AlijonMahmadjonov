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
export const kmText = km => km == null ? '' : km < 0.05 ? 'рядом' : km < 1 ? `${Math.round(km * 1000 / 10) * 10} м` : `${km.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} км`;

/**
 * Ссылка на маршрут до точки target. origin — откуда (по умолчанию — где курьер сейчас). Если метки нет — поиск по адресу.
 * Возвращает { url, fallback }: fallback — веб-версия, если приложения навигатора на телефоне нет.
 * @param {string} app
 * @param {{ lat?: number|null, lng?: number|null, address?: string }} target
 * @param {{ lat: number, lng: number }|null} [origin]
 * @returns {{ url: string, fallback?: string }}
 */
export function routeUrl(app, { lat, lng, address = '' }, origin = null) {
  const pin = lat != null && lng != null, q = encodeURIComponent(address), from = origin && hasPin(origin) ? origin : null;
  const yandexWeb = pin ? `https://yandex.ru/maps/?rtext=${from ? `${from.lat},${from.lng}` : ''}~${lat},${lng}&rtt=auto` : `https://yandex.ru/maps/?text=${q}`;
  switch (app) {
    case '2gis': {
      // официальная ссылка приложения 2GIS (сначала долгота, потом широта); без «from» 2GIS ведёт от места, где курьер сейчас
      const path = `routeSearch/rsType/car${from ? `/from/${from.lng},${from.lat}` : ''}/to/${lng},${lat}`;
      return pin ? { url: `dgis://2gis.ru/${path}`, fallback: `https://2gis.ru/${path}` } : { url: `https://2gis.ru/search/${q}` };
    }
    case 'yandexnavi': return pin ? { url: `yandexnavi://build_route_on_map?lat_to=${lat}&lon_to=${lng}${from ? `&lat_from=${from.lat}&lon_from=${from.lng}` : ''}`, fallback: yandexWeb } : { url: yandexWeb };
    case 'google': return { url: pin ? `https://www.google.com/maps/dir/?api=1${from ? `&origin=${from.lat},${from.lng}` : ''}&destination=${lat},${lng}&travelmode=driving` : `https://www.google.com/maps/search/?api=1&query=${q}` };
    default: return { url: yandexWeb };
  }
}

/** Номер для WhatsApp: только цифры с кодом страны. */
export const waUrl = phone => `https://wa.me/${String(phone || '').replace(/\D/g, '')}`;
