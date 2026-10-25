// Связь админ-панели с базой. Вход — почта и пароль админа (не номер телефона: тестовый вход по номеру без SMS
// открыл бы панель любому, кто знает номер). Ключ ниже — тот же публичный ключ, что у приложений:
// сам по себе он ничего не открывает, каждая функция admin_* в базе сама проверяет, что вызвал админ.

export const CLOUD = {
  url: 'https://taetdqqsktrcxsmmwfas.supabase.co',
  key: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRhZXRkcXFza3RyY3hzbW13ZmFzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI2Njk0MDksImV4cCI6MjEwODI0NTQwOX0.lfL3KHsaWNzkIfJsQBWQieD0GZZ-XJR96i2ii3Qwfuw',
};
const STORAGE_KEY = 'zud-admin-auth';   // свой ключ: вход в панель не путается со входом продавца, покупателя и курьера

let sb = null;
/** Клиент базы или null, если библиотека не загрузилась. */
export function db() {
  if (sb) return sb;
  const lib = window.__SUPABASE_MOCK__ || window.supabase;
  if (!lib?.createClient) return null;
  sb = lib.createClient(CLOUD.url, CLOUD.key, { auth: { storageKey: STORAGE_KEY, persistSession: true, autoRefreshToken: true, detectSessionInUrl: false } });
  return sb;
}

const isNet = m => /fetch|network|load failed|timed? ?out|abort/i.test(m);
/** Понятный текст ошибки. */
export function explain(e) {
  const m = e?.message || String(e || '');
  if (isNet(m)) return 'Нет связи с сервером. Проверьте интернет';
  if (/invalid login credentials/i.test(m)) return 'Неверная почта или пароль';
  if (/email not confirmed/i.test(m)) return 'Почта не подтверждена. В Supabase у пользователя нажмите «Confirm» или создайте его с «Auto Confirm User»';
  if (/schema cache|does not exist|Could not find the (table|function)|PGRST20[0-9]/i.test(m)) return 'База ещё не обновлена для админ-панели: примените миграцию 20261026000001_admin.sql';
  if (/JWT|token/i.test(m)) return 'Вход устарел. Войдите ещё раз';
  if (!/[а-яё]/i.test(m)) return 'Сервер ответил ошибкой: ' + m.slice(0, 120);
  return m;
}

const withTimeout = (p, sec = 20) => Promise.race([p, new Promise((_, no) => setTimeout(() => no(new Error('timed out')), sec * 1000))]);

/** Вызвать функцию базы. Ошибка — исключение с понятным текстом. */
export async function rpc(fn, args = {}) {
  const c = db(); if (!c) throw new Error('Нет связи с сервером');
  let r;
  try { r = await withTimeout(c.rpc(fn, args)); } catch (e) { throw new Error(explain(e)); }
  if (r.error) throw new Error(explain(r.error));
  return r.data;
}

/** Кто вошёл: { id, email, admin } или null. */
export async function whoami() {
  const c = db(); if (!c) return null;
  const s = (await c.auth.getSession()).data.session;
  if (!s) return null;
  return rpc('admin_me');
}
export async function signIn(email, password) {
  const c = db(); if (!c) throw new Error('Нет связи с сервером');
  const r = await withTimeout(c.auth.signInWithPassword({ email: email.trim().toLowerCase(), password }));
  if (r.error) throw new Error(explain(r.error));
  return rpc('admin_me');
}
export async function signOut() { try { await db()?.auth.signOut(); } catch { /* уже вышли */ } }

// ---------- чтение ----------
export const overview = () => rpc('admin_overview');
export const users = (q = '', role = '') => rpc('admin_users', { p_q: q, p_role: role });
export const user = id => rpc('admin_user', { p_id: id });
export const shops = (q = '') => rpc('admin_shops', { p_q: q });
export const shop = id => rpc('admin_shop', { p_id: id });
export const products = (q = '', filter = '') => rpc('admin_products', { p_q: q, p_filter: filter });
export const orders = ({ status = '', q = '', shop = null, person = null, from = null, to = null } = {}) =>
  rpc('admin_orders', { p_status: status, p_q: q, p_shop: shop || null, p_person: person || null, p_from: from || null, p_to: to || null });
export const order = id => rpc('admin_order', { p_id: id });
export const couriers = () => rpc('admin_couriers');
export const map = () => rpc('admin_map');
export const reviews = (filter = '') => rpc('admin_reviews', { p_filter: filter });
export const checks = () => rpc('admin_checks');
export const log = (limit = 300) => rpc('admin_log', { p_limit: limit });
export const system = () => rpc('admin_system');

// ---------- действия (каждое база записывает в журнал) ----------
export const blockShop = (id, on, reason = '') => rpc('admin_shop_block', { p_shop: id, p_on: on, p_reason: reason });
export const blockProduct = (id, on, reason = '') => rpc('admin_product_block', { p_product: id, p_on: on, p_reason: reason });
export const blockCourier = (id, on, reason = '') => rpc('admin_courier_block', { p_courier: id, p_on: on, p_reason: reason });
export const blockUser = (id, on, reason = '') => rpc('admin_user_block', { p_user: id, p_on: on, p_reason: reason });
export const cancelOrder = (id, reason) => rpc('admin_order_cancel', { p_order: id, p_reason: reason });
export const releaseOrder = (id, reason = '') => rpc('admin_order_release', { p_order: id, p_reason: reason });
export const deliveredOrder = (id, reason) => rpc('admin_order_delivered', { p_order: id, p_reason: reason });
export const resolveOrder = (id, note) => rpc('admin_order_resolve', { p_order: id, p_note: note });
export const decideReview = (id, hide, note = '') => rpc('admin_review_decide', { p_review: id, p_hide: hide, p_note: note });
export const setAdmin = (id, on, note = '') => rpc('admin_set_admin', { p_user: id, p_on: on, p_note: note });
