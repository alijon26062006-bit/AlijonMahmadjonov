import { db, explain, isNetErr, signInPhone, signOut } from './cloud.js';

// Все запросы курьера к базе. Каждое действие — функция в базе: она сама проверяет,
// что заказ свободен, что шаг правильный и что код покупателя верный.

const withTimeout = (p, sec = 15) => Promise.race([p, new Promise((_, no) => setTimeout(() => no(new Error('timeout')), sec * 1000))]);
/** Ошибка с понятным текстом; net — нет связи. */
function fail(e) { const err = new Error(explain(e)); err.net = isNetErr(e) || /timeout/.test(e?.message || ''); return err; }

async function rpc(fn, args = {}) {
  const c = db(); if (!c) throw Object.assign(new Error('Нет связи с сервером'), { net: true });
  let r;
  try { r = await withTimeout(c.rpc(fn, args)); } catch (e) { throw fail(e); }
  if (r.error) throw fail(r.error);
  return r.data;
}
const n = v => v == null ? null : Number(v);
const ms = v => v ? Date.parse(v) : null;

/** Заказ из базы → удобный вид для экранов. */
export const fromJob = j => ({
  ...j, no: n(j.no), earn: n(j.earn) || 0, total: n(j.total), sum: n(j.sum), fee: n(j.fee), km: n(j.km), cash_taken: n(j.cash_taken),
  created: ms(j.created_at), taken: ms(j.taken_at), picked: ms(j.picked_at), delivered: ms(j.delivered_at) || ms(j.received_at), readyAt: ms(j.ready_at),
  items: (j.items || []).map(i => ({ ...i, qty: n(i.qty), actual: n(i.actual) })),
  shop: { ...j.shop, lat: n(j.shop?.lat), lng: n(j.shop?.lng) }, client: { ...j.client, lat: n(j.client?.lat), lng: n(j.client?.lng) },
});
export const fromOffer = o => ({ ...o, no: n(o.no), earn: n(o.earn) || 0, km: n(o.km), to_shop: n(o.to_shop), cash: n(o.cash), items: n(o.items),
  readyAt: ms(o.ready_at), created: ms(o.created_at), shop_lat: n(o.shop_lat), shop_lng: n(o.shop_lng) });

export const login = phone => withTimeout(signInPhone(phone)).catch(e => { throw fail(e); });
export const logout = signOut;

/** Анкета курьера или null, если ещё не заполнял. */
export async function me() {
  const c = db(); if (!c) throw Object.assign(new Error('Нет связи с сервером'), { net: true });
  const uid = (await c.auth.getSession()).data.session?.user?.id; if (!uid) return null;
  const r = await withTimeout(c.from('couriers').select('*').eq('id', uid).maybeSingle()).catch(e => { throw fail(e); });
  if (r.error) throw fail(r.error);
  return r.data;
}
export const register = ({ name, phone, car, plate }) => rpc('courier_register', { p_name: name, p_phone: phone, p_car: car, p_plate: plate, p_photo: '' });
export const setOnline = (on, pos) => rpc('courier_online', { p_on: on, p_lat: pos?.lat ?? null, p_lng: pos?.lng ?? null });
export const ping = pos => rpc('courier_ping', { p_lat: pos.lat, p_lng: pos.lng });
export const feed = async () => (await rpc('courier_feed') || []).map(fromOffer);
export const take = async id => fromJob(await rpc('courier_take', { p_order: id }));
export const jobs = async (days = 0) => (await rpc('courier_jobs', { p_days: days }) || []).map(fromJob);
export const step = async (id, s, code = null) => fromJob(await rpc('courier_step', { p_order: id, p_step: s, p_code: code }));
export const release = id => rpc('courier_release', { p_order: id });
export const giveBack = async (id, reason) => fromJob(await rpc('courier_return', { p_order: id, p_reason: reason }));

/** Живые изменения своих заказов (магазин собрал, покупатель отменил или сам нажал «Получил»). */
export function listen(uid, cb) {
  const c = db(); if (!c || !uid) return () => {};
  const ch = c.channel('courier-' + uid)
    .on('postgres_changes', { event: '*', schema: 'public', table: 'orders', filter: `courier_id=eq.${uid}` }, () => cb())
    .subscribe();
  return () => ch.unsubscribe();
}
