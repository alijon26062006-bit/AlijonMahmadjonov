/** Обращения к API и сессия покупателя.

    Сессия живёт в localStorage: сайт открывают с разных устройств, и
    выкидывать человека при каждом заходе нельзя. Токен долгий (30 дней),
    поэтому «Войти» на сайте нажимают редко.
*/
import type { UserOut } from './types';

export const API = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

const SESSION_KEY = 'stambul.session';

let token: string | null = null;
let currentUser: UserOut | null = null;
const listeners = new Set<() => void>();

export function getUser(): UserOut | null { return currentUser; }
export function isAuthed(): boolean { return Boolean(token); }
export function onAuthChange(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}
function notify() { listeners.forEach((cb) => cb()); }

function setSession(t: string, u: UserOut) {
  token = t;
  currentUser = u;
  localStorage.setItem(SESSION_KEY, JSON.stringify({ t, u }));
  notify();
}

export function applyUser(u: UserOut) {
  currentUser = u;
  if (token) localStorage.setItem(SESSION_KEY, JSON.stringify({ t: token, u }));
  notify();
}

export function logout() {
  token = null;
  currentUser = null;
  localStorage.removeItem(SESSION_KEY);
  notify();
}

/** Поднимает прошлую сессию и проверяет, что токен ещё жив. */
export async function bootstrapAuth(): Promise<void> {
  const saved = localStorage.getItem(SESSION_KEY);
  if (!saved) return;
  try {
    const { t, u } = JSON.parse(saved);
    token = t;
    currentUser = u;
    notify();
  } catch {
    logout();
    return;
  }
  try {
    const r = await fetch(`${API}/api/auth/me`,
                          { headers: { Authorization: `Bearer ${token}` } });
    if (r.ok) applyUser(await r.json());
    else if (r.status === 401 || r.status === 403) logout();
    // прочие коды — сервер прилёг, человека выгонять не за что
  } catch { /* оффлайн: живём на сохранённой сессии */ }
}

// ─────────────────────────── Вход ───────────────────────────

export type PhoneRequest = {
  key: string; phone: string; link: string; expires_in: number;
};

export async function requestPhoneCode(phone: string): Promise<PhoneRequest> {
  return api<PhoneRequest>('/api/auth/phone/request', {
    method: 'POST', body: JSON.stringify({ phone }),
  });
}

/** Ждём, пока человек нажмёт кнопку в боте. true — уже вошли. */
export async function pollPhoneStatus(key: string): Promise<boolean> {
  const r = await fetch(`${API}/api/auth/phone/status?key=${encodeURIComponent(key)}`);
  if (!r.ok) return false;
  const js = await r.json();
  if (js.status === 'confirmed') {
    setSession(js.access_token, js.user);
    return true;
  }
  return false;
}

export async function verifyPhoneCode(key: string, code: string): Promise<void> {
  const js = await api<{ access_token: string; user: UserOut }>(
    '/api/auth/phone/verify',
    { method: 'POST', body: JSON.stringify({ key, code }) });
  setSession(js.access_token, js.user);
}

export async function loginWithGoogle(idToken: string): Promise<void> {
  const js = await api<{ access_token: string; user: UserOut }>(
    '/api/auth/google',
    { method: 'POST', body: JSON.stringify({ id_token: idToken }) });
  setSession(js.access_token, js.user);
}

export async function updateMe(patch: Partial<UserOut> & Record<string, unknown>) {
  const u = await api<UserOut>('/api/auth/me',
                               { method: 'PATCH', body: JSON.stringify(patch) });
  applyUser(u);
  return u;
}

export async function telegramLinkUrl(): Promise<string> {
  const js = await api<{ link: string }>('/api/auth/telegram/link',
                                         { method: 'POST' });
  return js.link;
}

// ─────────────────────────── Запросы ───────────────────────────

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (init?.body && !(init.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) headers.Authorization = `Bearer ${token}`;

  const r = await fetch(`${API}${path}`, { ...init, headers });
  if (r.status === 401 && token) logout();
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw Object.assign(new Error(detail.detail || r.statusText),
                        { status: r.status });
  }
  return r.json();
}

export function photoUrl(path: string): string {
  return path.startsWith('http') ? path : `${API}${path}`;
}

// ─────────────────────────── Мелочи вывода ───────────────────────────

/** Знак валюты приходит с сервера — магазин может переехать в другую страну. */
let sign = '₸';
export function setCurrencySign(value: string): void { sign = value || '₸'; }

export function fmtPrice(price: number): string {
  return `${Math.round(price).toLocaleString('ru-RU')} ${sign}`;
}

export function fmtDate(iso?: string | null): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('ru-RU',
                                          { day: 'numeric', month: 'short' });
}

/** Маска ввода номера: человек печатает цифры, скобки ставим сами.

    Поле всегда начинается с «+7 », поэтому первая цифра строки — это код
    страны, а не начало номера: её отбрасываем всегда. Иначе номер вида
    701… терял бы свою первую семёрку, ведь она совпадает с кодом.
*/
export function maskPhone(raw: string): string {
  const tail = raw.startsWith('+7') ? raw.slice(2) : raw;
  let digits = tail.replace(/\D/g, '');
  // вставили номер целиком, вместе с кодом страны или восьмёркой
  if (digits.length === 11 && (digits[0] === '7' || digits[0] === '8')) {
    digits = digits.slice(1);
  }
  digits = digits.slice(0, 10);

  const parts = [digits.slice(0, 3), digits.slice(3, 6),
                 digits.slice(6, 8), digits.slice(8, 10)].filter(Boolean);
  if (!parts.length) return '+7 ';
  let out = `+7 (${parts[0]}`;
  if (parts.length > 1) out += `) ${parts[1]}`;
  if (parts.length > 2) out += `-${parts[2]}`;
  if (parts.length > 3) out += `-${parts[3]}`;
  return out;
}

export function phoneReady(masked: string): boolean {
  return masked.replace(/\D/g, '').length === 11;
}
