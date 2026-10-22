import { CUR } from '../config.js';

// утилиты
export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const r2 = n => Math.round(n * 100) / 100;
export const money = n => r2(n).toLocaleString('ru-RU', { maximumFractionDigits: 2 }) + ' ' + CUR;
export const moneyShort = n => Math.abs(n) >= 10000 ? (r2(n / 1000)).toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + ' тыс' : Math.round(n).toLocaleString('ru-RU');
export const num = v => { const n = parseFloat(String(v ?? '').replace(',', '.').replace(/\s/g, '')); return Number.isFinite(n) ? n : null; };
export const pad = n => String(n).padStart(2, '0');
export const dkey = d => { d = new Date(d); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
export const today = () => dkey(Date.now());
export const parseKey = k => { const [y, m, d] = k.split('-').map(Number); return new Date(y, m - 1, d); };
export const addDays = (k, n) => { const d = parseKey(k); d.setDate(d.getDate() + n); return dkey(d); };
export const ddmm = k => { const d = parseKey(k); return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}`; };
export const hhmm = ts => { const d = new Date(ts); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
export const whenText = ts => { const k = dkey(ts); if (k === today()) return 'сегодня ' + hhmm(ts); if (k === addDays(today(), -1)) return 'вчера ' + hhmm(ts); return ddmm(k) + ' ' + hhmm(ts); };
export const minsAgo = ts => Math.max(0, Math.round((Date.now() - ts) / 60000));
export const plural = (n, a, b, c) => { const m = n % 10, h = n % 100; return m === 1 && h !== 11 ? a : m >= 2 && m <= 4 && (h < 12 || h > 14) ? b : c; };
export const fmtPhone = d => d.replace(/^(\d{2})(\d{0,3})(\d{0,2})(\d{0,2}).*/, (m, a, b, c, e) => [a, b, c, e].filter(Boolean).join(' '));
