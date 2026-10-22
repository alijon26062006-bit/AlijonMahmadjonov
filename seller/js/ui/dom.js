import { LOW } from '../config.js';
import { esc } from '../lib/format.js';

// общие куски интерфейса
export const $ = sel => document.querySelector(sel);
export const app = $('#app');
export let toastTimer;
export function toast(msg) { const t = $('#toast'); t.textContent = msg; t.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 2600); }
export const ICON = {
  pin: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s7-6.5 7-12a7 7 0 0 0-14 0c0 5.5 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/></svg>',
  close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7"/></svg>',
  note: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"/></svg>',
  star: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5l2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 16.9l-5.3 2.7 1-5.8-4.2-4.1 5.9-.9z"/></svg>',
  image: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="9" cy="10" r="1.8"/><path d="M21 16l-5-5-8 8"/></svg>',
  home: '<svg viewBox="0 0 24 24"><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>',
  orders: '<svg viewBox="0 0 24 24"><path d="M6 3h12l1 4H5zM5 7h14v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1zM9 11h6M9 15h4"/></svg>',
  catalog: '<svg viewBox="0 0 24 24"><path d="M3 7l9-4 9 4-9 4-9-4zM3 7v10l9 4 9-4V7M12 11v10"/></svg>',
  stats: '<svg viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-7M21 20H3"/></svg>',
  expenses: '<svg viewBox="0 0 24 24"><path d="M3 6h18v12H3zM3 10h18M7 15h3"/></svg>',
  preview: '<svg viewBox="0 0 24 24"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
  shop: '<svg viewBox="0 0 24 24"><path d="M4 10v10h16V10M3 10l2-6h14l2 6M3 10h18M9 20v-6h6v6"/></svg>',
  more: '<svg viewBox="0 0 24 24"><path d="M5 12h.01M12 12h.01M19 12h.01"/></svg>',
  finance: '<svg viewBox="0 0 24 24"><path d="M4 7h15a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a2 2 0 0 1 2-2h11v3M16 13.5h.01"/></svg>',
  logout: '<svg viewBox="0 0 24 24"><path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10"/></svg>',
  import: '<svg viewBox="0 0 24 24"><path d="M12 3v12M7 10l5 5 5-5M4 21h16"/></svg>',
};
export const pic = p => p.imgs && p.imgs[0] ? `<img src="${p.imgs[0]}" alt="">` : `<span class="noimg" title="Нет фото">${ICON.image}</span>`;
export const thumb = p => `<div class="thumb">${pic(p)}</div>`;
export const plusI = '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>';
export const NAV = [['home', 'Главная'], ['orders', 'Заказы'], ['catalog', 'Товары'], ['stats', 'Статистика'], ['finance', 'Деньги'], ['expenses', 'Расходы'], ['preview', 'Витрина'], ['shop', 'Магазин']];
export const TABS = [['home', 'Главная'], ['orders', 'Заказы'], ['catalog', 'Товары'], ['stats', 'Статистика'], ['more', 'Ещё']];
// товар на стопе до конца дня: «Закончилось на сегодня»
export const isStopped = p => !!p.stopUntil && p.stopUntil > Date.now();
export const fmtQty = n => (+n).toLocaleString('ru-RU', { maximumFractionDigits: 3 });
export function stockPill(p) {
  if (!p.active) return '<span class="pill off">Скрыт</span>';
  if (isStopped(p)) return '<span class="pill bad">Закончилось на сегодня</span>';
  if (p.stock <= 0) return '<span class="pill bad">Нет в наличии</span>';
  if (p.stock <= LOW) return `<span class="pill warn">Осталось ${fmtQty(p.stock)} ${esc(p.unit)}</span>`;
  return `<span class="pill">В наличии ${fmtQty(p.stock)} ${esc(p.unit)}</span>`;
}
export function showErrors(form, errs) {
  form.querySelectorAll('.err').forEach(e => e.remove());
  form.querySelectorAll('.invalid').forEach(e => e.classList.remove('invalid'));
  let first = null;
  for (const [k, m] of Object.entries(errs)) {
    const el = form.querySelector(`[name="${k}"]`); if (!el) continue;
    el.classList.add('invalid'); (el.closest('.suffix') || el).insertAdjacentHTML('afterend', `<span class="err">${m}</span>`); first = first || el;
  }
  if (first) first.focus();
  return !first;
}
// боковая панель
export function openSheet(title, body, foot, keepScroll) {
  const sheet = $('#sheet'), prev = keepScroll ? sheet.querySelector('.sheet-body')?.scrollTop : 0;
  sheet.innerHTML = `<div class="sheet-head"><h2 id="sheetTitle">${esc(title)}</h2><button class="btn ghost" data-act="close" aria-label="Закрыть">${ICON.close}</button></div><div class="sheet-body">${body}</div>${foot ? `<div class="sheet-foot">${foot}</div>` : ''}`;
  sheet.hidden = false; $('#sheetBg').hidden = false;
  if (prev) sheet.querySelector('.sheet-body').scrollTop = prev;
}
const closeHandlers = [];
/** Модуль с черновиком в боковой панели регистрирует здесь его сброс. */
export const onSheetClose = fn => closeHandlers.push(fn);
export function closeSheet() { $('#sheet').hidden = true; $('#sheetBg').hidden = true; closeHandlers.forEach(fn => fn()); }

// события
export let armed = null;
export function confirmTwice(t, label) {
  if (armed === t) { armed = null; return true; }
  if (armed) { armed.classList.remove('armed'); armed.textContent = armed.dataset.label; }
  armed = t; t.dataset.label = t.textContent; t.textContent = label; t.classList.add('armed');
  setTimeout(() => { if (armed === t) { t.classList.remove('armed'); t.textContent = t.dataset.label; armed = null; } }, 3500);
  return false;
}
