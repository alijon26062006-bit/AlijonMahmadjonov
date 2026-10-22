// Связь с кабинетом продавца. Пока нет сервера, кабинет хранит магазин в этом же браузере:
// если продавец открыт на этом устройстве, его магазин появляется у покупателя, а заказы уходят в кабинет.
// После подключения Supabase здесь будут запросы к общей базе, остальной код не изменится.
export const SELLER_KEY = 'seller-panel-v2';

export function readSeller() {
  try { const s = JSON.parse(localStorage.getItem(SELLER_KEY)); return s && typeof s === 'object' && s.shop ? s : null; } catch { return null; }
}
/** Меняет данные кабинета: fn получает свежую копию, результат fn возвращается. */
export function updateSeller(fn) {
  const s = readSeller(); if (!s) return null;
  s.orders ||= []; s.reviews ||= [];
  const r = fn(s);
  try { localStorage.setItem(SELLER_KEY, JSON.stringify(s)); } catch { return null; }
  return r;
}
