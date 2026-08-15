/** API-клиент: авторизация (Mini App / браузер), запросы с Bearer, фото-URL. */
import { inTelegram, tg } from '../telegram/tg';
import type { UserOut } from './types';

export const API = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

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
  token = t; currentUser = u;
  if (!inTelegram) localStorage.setItem('session', JSON.stringify({ t, u }));
  notify();
}

export function logout() {
  token = null; currentUser = null;
  localStorage.removeItem('session');
  notify();
}

/** Вход: в Telegram — по initData автоматически; в браузере — из localStorage. */
export async function bootstrapAuth(): Promise<string | null> {
  if (inTelegram && tg) {
    try {
      const r = await fetch(`${API}/api/auth/telegram`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ init_data: tg.initData }),
      });
      if (r.ok) {
        const js = await r.json();
        setSession(js.access_token, js.user);
        return js.start_param ?? null;
      }
    } catch { /* оффлайн — работаем как гость */ }
    return null;
  }
  const saved = localStorage.getItem('session');
  if (saved) {
    try {
      const { t, u } = JSON.parse(saved);
      token = t; currentUser = u; notify();
      // проверим, что токен ещё жив
      const r = await fetch(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${t}` } });
      if (!r.ok) logout();
    } catch { logout(); }
  }
  return null;
}

/** Браузерный вход через подтверждение в боте. */
export async function requestLoginCode(): Promise<{ code: string; link: string }> {
  const r = await fetch(`${API}/api/auth/login-code`, { method: 'POST' });
  return r.json();
}

export async function pollLoginCode(code: string): Promise<boolean> {
  const r = await fetch(`${API}/api/auth/login-code/${code}`);
  if (r.status === 410) throw new Error('expired');
  const js = await r.json();
  if (js.status === 'confirmed') {
    setSession(js.access_token, js.user);
    return true;
  }
  return false;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (init?.body && !(init.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) headers.Authorization = `Bearer ${token}`;

  let r = await fetch(`${API}${path}`, { ...init, headers });

  // 401 в Telegram: переавторизуемся по initData и повторим один раз
  if (r.status === 401 && inTelegram && tg) {
    token = null;
    await bootstrapAuth();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
      r = await fetch(`${API}${path}`, { ...init, headers });
    }
  }
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw Object.assign(new Error(detail.detail || r.statusText), { status: r.status });
  }
  return r.json();
}

export function photoUrl(path: string): string {
  return path.startsWith('http') ? path : `${API}${path}`;
}

export function fmtPrice(price: number, currency: string): string {
  const sign = currency === 'USD' ? '$' : 'смн';
  return `${Math.round(price).toLocaleString('ru-RU')} ${sign}`;
}

export function fmtDate(iso?: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}
