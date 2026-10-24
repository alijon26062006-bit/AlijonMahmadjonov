// Связь с базой Supabase. Библиотека лежит в проекте (js/vendor/supabase.js) — чужие сайты не нужны.
// Ключ ниже — публичный ключ для приложений: он виден всем и ничего не открывает сам по себе,
// доступ к данным решают правила базы (магазин видит только своё, покупатель — только свои заказы).
//
// ТЕСТОВЫЙ ВХОД: по номеру телефона без SMS. Номер превращается в служебную почту и пароль,
// поэтому с любого телефона под тем же номером открывается тот же магазин.
// Перед запуском для людей вход заменим на код из SMS — тогда войти под чужим номером будет нельзя.

export const CLOUD = {
  url: 'https://taetdqqsktrcxsmmwfas.supabase.co',
  key: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRhZXRkcXFza3RyY3hzbW13ZmFzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI2Njk0MDksImV4cCI6MjEwODI0NTQwOX0.lfL3KHsaWNzkIfJsQBWQieD0GZZ-XJR96i2ii3Qwfuw',
};
const STORAGE_KEY = 'zud-seller-auth';   // у покупателя свой ключ: на одном телефоне можно быть и продавцом, и покупателем

let sb = null;
/** Клиент базы или null, если библиотека не загрузилась. */
export function db() {
  if (sb) return sb;
  const lib = window.__SUPABASE_MOCK__ || window.supabase;
  if (!lib?.createClient) return null;
  sb = lib.createClient(CLOUD.url, CLOUD.key, { auth: { storageKey: STORAGE_KEY, persistSession: true, autoRefreshToken: true, detectSessionInUrl: false } });
  return sb;
}
const mail = phone => `992${phone}@zud.tj`;
const word = phone => `zud-test-${phone}`;

/** Понятный текст ошибки для продавца. */
export function explain(e) {
  const m = e?.message || String(e || '');
  if (/fetch|network|load failed|timed? ?out/i.test(m)) return 'Нет связи с сервером';
  if (/confirm/i.test(m)) return 'Сервер просит подтвердить почту — в Supabase выключите «Confirm email»';
  return m;
}
export const isNetErr = e => /fetch|network|load failed|timed? ?out/i.test(e?.message || String(e || ''));

/** Вход по номеру (тестовый): если такого номера ещё нет — создаём учётную запись. */
export async function signInPhone(phone) {
  const c = db(); if (!c) throw new Error('Нет связи с сервером');
  const cur = (await c.auth.getSession()).data.session;
  if (cur?.user?.email === mail(phone)) return cur.user;
  let r = await c.auth.signInWithPassword({ email: mail(phone), password: word(phone) });
  if (r.error && /invalid login credentials/i.test(r.error.message)) r = await c.auth.signUp({ email: mail(phone), password: word(phone) });
  if (r.error) throw r.error;
  if (!r.data.session) throw new Error('confirm email');
  return r.data.user;
}
export async function signOut() { try { await db()?.auth.signOut(); } catch { /* уже вышли */ } }
