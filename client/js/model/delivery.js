import { CITIES } from '../config.js';
import { C } from '../state.js';

// Доставка по расстоянию: от метки магазина до метки покупателя.
// Возят таксисты: как в такси, 10 смн за километр. Бесплатной доставки нет — деньги за дорогу получает водитель.
export const TARIFF = {
  perKm: 10,        // смн за километр — как у такси
  minFee: 10,       // смн — минимум, даже если ехать меньше километра
  maxKm: 15,        // дальше магазин не возит
  roadFactor: 1.3,  // дорога длиннее прямой линии: по городу примерно на треть
  minPerKm: 3,      // минут в пути на километр
  pickupMin: 5,     // минут, чтобы водитель забрал заказ
};

const R = 6371;
const rad = d => d * Math.PI / 180;
/** Расстояние по прямой между двумя точками на карте, км (формула гаверсинуса). */
export function straightKm(a, b) {
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
// без метки на карте берём центр города и честно помечаем расчёт как примерный
const point = (x, city) => x?.lat != null && x?.lng != null ? { lat: x.lat, lng: x.lng, exact: true }
  : { ...(CITIES.find(c => c.name === city) || CITIES[0]), exact: false };

/** Путь курьера от магазина до адреса: км по дороге, минуты, точный ли расчёт, возит ли магазин так далеко. */
export function route(shop, addr = C.addr) {
  const from = point(shop, shop.city), to = point(addr, addr?.city || shop.city);
  const km = Math.max(0.3, Math.round(straightKm(from, to) * TARIFF.roadFactor * 10) / 10);
  return { km, min: Math.round(TARIFF.pickupMin + km * TARIFF.minPerKm), exact: from.exact && to.exact && !!addr, ok: km <= TARIFF.maxKm };
}
/** Цена доставки: километры × цена километра, не меньше минимума. Округляем до целого сомони вверх. */
export function feeFor(shop, addr = C.addr) {
  return Math.max(TARIFF.minFee, Math.ceil(route(shop, addr).km * TARIFF.perKm));
}
export const kmText = km => `${km.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} км`;
