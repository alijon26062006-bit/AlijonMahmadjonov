import { CUR } from '../config.js';

export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const r2 = n => Math.round(n * 100) / 100;
export const money = n => r2(n).toLocaleString('ru-RU', { maximumFractionDigits: 2 }) + ' ' + CUR;
export const num = v => { const n = parseFloat(String(v ?? '').replace(',', '.').replace(/\s/g, '')); return Number.isFinite(n) ? n : null; };
export const fmtQty = n => (+n).toLocaleString('ru-RU', { maximumFractionDigits: 3 });
export const pad = n => String(n).padStart(2, '0');
export const hhmm = ts => { const d = new Date(ts); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
export const dkey = d => { d = new Date(d); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
export const today = () => dkey(Date.now());
export const plural = (n, a, b, c) => { const m = n % 10, h = n % 100; return m === 1 && h !== 11 ? a : m >= 2 && m <= 4 && (h < 12 || h > 14) ? b : c; };
export const fmtPhone = d => String(d || '').replace(/^(\d{2})(\d{0,3})(\d{0,2})(\d{0,2}).*/, (m, a, b, c, e) => [a, b, c, e].filter(Boolean).join(' '));
export function whenText(ts) {
  const k = dkey(ts), t = today(), y = dkey(Date.now() - 864e5);
  if (k === t) return 'сегодня в ' + hhmm(ts);
  if (k === y) return 'вчера в ' + hhmm(ts);
  return new Date(ts).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }) + ' в ' + hhmm(ts);
}
// «0,5 кг» → «500 г»
export const qtyLabel = (q, unit) => unit === 'кг' && q < 1 ? `${Math.round(q * 1000)} г` : unit === 'л' && q < 1 ? `${Math.round(q * 1000)} мл` : `${fmtQty(q)} ${unit}`;
