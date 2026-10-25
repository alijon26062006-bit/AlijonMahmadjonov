// Форматы и подписи: деньги, даты, номера, роли, этапы заказа. Чистые функции — без DOM.

export const CUR = 'смн';
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = v => Number(v) || 0;
export const money = v => `${num(v).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${CUR}`;
export const count = v => num(v).toLocaleString('ru-RU');

/** 900000010 → +992 90 000 00 10 (неразрывные пробелы: номер не переносится по частям); уже с кодом или с пробелами — тоже понимает. */
export function phone(p) {
  const d = String(p || '').replace(/\D/g, '').replace(/^992(?=\d{9}$)/, '');
  if (d.length !== 9) return String(p || '');
  return ['+992', d.slice(0, 2), d.slice(2, 5), d.slice(5, 7), d.slice(7)].join(' ');
}
export const tel = p => { const d = String(p || '').replace(/\D/g, '').replace(/^992(?=\d{9}$)/, ''); return d.length === 9 ? `tel:+992${d}` : `tel:${d}`; };

const pad = n => String(n).padStart(2, '0');
/** «сегодня 14:05», «вчера 09:30», «12.10 18:00», «12.10.2025». */
export function when(ts) {
  if (!ts) return '—';
  const d = new Date(ts); if (Number.isNaN(+d)) return '—';
  const now = new Date(), day = 864e5, t = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const d0 = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (+d >= d0) return `сегодня ${t}`;
  if (+d >= d0 - day) return `вчера ${t}`;
  if (d.getFullYear() === now.getFullYear()) return `${pad(d.getDate())}.${pad(d.getMonth() + 1)} ${t}`;
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
}
/** «5 мин назад», «3 ч назад», «2 дн назад». */
export function ago(ts) {
  if (!ts) return 'никогда';
  const s = (Date.now() - Date.parse(ts)) / 1000;
  if (!Number.isFinite(s)) return '—';
  if (s < 60) return 'только что';
  if (s < 3600) return `${Math.floor(s / 60)} мин назад`;
  if (s < 86400) return `${Math.floor(s / 3600)} ч назад`;
  return `${Math.floor(s / 86400)} дн назад`;
}
/** Сколько минут между двумя моментами: «12 мин». */
export const span = (a, b) => a && b ? `${Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / 60000))} мин` : '';

// ---------- роли ----------
export const ROLES = {
  admin: { name: 'Админ', tone: 'dark', hint: 'Видит всё, блокирует и снимает блокировку, решает проблемы и жалобы. Входит по почте и паролю' },
  seller: { name: 'Продавец', tone: 'blue', hint: 'Владелец магазина: товары, цены, заказы, деньги, сотрудники' },
  staff: { name: 'Сотрудник', tone: 'violet', hint: 'Работает в магазине по номеру из списка владельца: управляющий, кассир или сборщик' },
  courier: { name: 'Курьер', tone: 'amber', hint: 'Берёт собранные заказы и везёт покупателю; закрывает доставку кодом из 4 цифр' },
  buyer: { name: 'Покупатель', tone: 'green', hint: 'Заказывает в приложении, видит курьера на карте, оценивает магазин и курьера' },
};
export const STAFF_ROLES = { manager: 'Управляющий', cashier: 'Кассир', picker: 'Сборщик' };
export const roleChip = r => ROLES[r] ? `<span class="chip ${ROLES[r].tone}">${ROLES[r].name}</span>` : '';
export const roleChips = list => (list && list.length ? list.map(roleChip).join('') : '<span class="chip">Без роли</span>');

export const KINDS = { grocery: 'Продукты', perfume: 'Парфюмерия', tech: 'Электроника', food: 'Еда' };

// ---------- заказ: этап одной фразой и цвет ----------
/** @param {{ status: string, step?: string|null, source?: string, delivery?: string, received_at?: string|null, courier_id?: string|null }} o */
export function stage(o) {
  if (o.status === 'cancelled') return { text: 'Отменён', tone: 'bad' };
  if (o.received_at || o.step === 'delivered') return { text: o.source === 'shop' ? 'Продажа в магазине' : 'Получен', tone: 'ok' };
  if (o.step === 'returned') return { text: 'Вернули в магазин', tone: 'bad' };
  if (o.step === 'at_client') return { text: 'Курьер у двери', tone: 'info' };
  if (o.step === 'picked') return { text: 'Курьер везёт', tone: 'info' };
  if (o.step === 'at_shop') return { text: 'Курьер в магазине', tone: 'info' };
  if (o.step === 'going') return { text: 'Курьер едет в магазин', tone: 'info' };
  if (o.source === 'shop') return { text: 'Продажа в магазине', tone: 'ok' };
  if (o.status === 'new') return { text: 'Ждёт ответа магазина', tone: 'warn' };
  if (o.status === 'accepted') return { text: 'Собирают', tone: 'warn' };
  if (o.status === 'ready') return { text: o.delivery === 'courier' && !o.courier_id ? 'Собран, ждёт курьера' : 'Собран', tone: 'warn' };
  return { text: 'Выдан', tone: 'ok' };
}
export const stageChip = o => { const s = stage(o); return `<span class="chip ${s.tone}">${s.text}</span>`; };
export const PAY = { cash: 'Наличные', card: 'Онлайн' };

// ---------- журнал ----------
export const ACTIONS = {
  shop_block: 'Заблокировал магазин', shop_unblock: 'Разблокировал магазин',
  product_block: 'Скрыл товар', product_unblock: 'Вернул товар',
  courier_block: 'Заблокировал курьера', courier_unblock: 'Разблокировал курьера',
  user_block: 'Заблокировал человека', user_unblock: 'Разблокировал человека',
  order_cancel: 'Отменил заказ', order_release: 'Снял курьера с заказа', order_delivered: 'Закрыл заказ как полученный', order_resolve: 'Решил проблему',
  review_hide: 'Скрыл отзыв', review_keep: 'Оставил отзыв',
  admin_add: 'Дал права админа', admin_remove: 'Забрал права админа',
};
