import { CITIES, SERVICE_AREA } from '../config.js';
import { C } from '../state.js';

// Доставка до двери, возят таксисты. Цена считается сразу, на телефоне, без запроса к серверу.
// Ступени выбраны по местным ценам: такси по посёлку ~10 смн, +5 смн за то, что водитель ждёт у магазина и несёт до двери.
export const TARIFF = {
  steps: [[2, 15], [5, 20]],  // до 2 км — 15 смн, до 5 км — 20 смн
  farBase: 20,                // дальше 5 км: 20 смн
  farPerKm: 2,                // + 2 смн за каждый км сверх 5
  maxKm: 30,                  // по дороге дальше не возим
  roadFactor: 1.3,            // дорога длиннее прямой линии примерно на треть
  minPerKm: 3,                // минут в пути на километр
  pickupMin: 5,               // минут, чтобы водитель забрал заказ
};

const R = 6371;
const rad = d => d * Math.PI / 180;
/** Расстояние по прямой между двумя точками на карте, км (формула гаверсинуса). */
export function straightKm(a, b) {
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
const hasPin = x => x?.lat != null && x?.lng != null;
/** Точка в зоне работы сервиса? Без метки на карте считаем, что адрес в посёлке. */
export const inZone = x => !hasPin(x) || straightKm(SERVICE_AREA, x) <= SERVICE_AREA.radiusKm;
// без метки на карте берём центр посёлка и честно помечаем расчёт как примерный
const point = (x, city) => hasPin(x) ? { lat: x.lat, lng: x.lng, exact: true } : { ...(CITIES.find(c => c.name === city) || CITIES[0]), exact: false };

/** Путь от магазина до адреса: км по дороге, минуты, точный ли расчёт, можно ли доставить. */
export function route(shop, addr = C.addr) {
  const from = point(shop, shop.city), to = point(addr, addr?.city || shop.city);
  const km = Math.max(0.3, Math.round(straightKm(from, to) * TARIFF.roadFactor * 10) / 10);
  return { km, min: Math.round(TARIFF.pickupMin + km * TARIFF.minPerKm), exact: from.exact && to.exact && !!addr, ok: km <= TARIFF.maxKm && inZone(addr) };
}
/** Цена по километрам: 15 → 20 → 20 + 2 за каждый км после пятого. */
export function priceForKm(km) {
  const step = TARIFF.steps.find(([upTo]) => km <= upTo);
  return step ? step[1] : TARIFF.farBase + Math.ceil(km - TARIFF.steps.at(-1)[0]) * TARIFF.farPerKm;
}
export const feeFor = (shop, addr = C.addr) => priceForKm(route(shop, addr).km);
export const kmText = km => `${km.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} км`;
