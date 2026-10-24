import { esc } from '../lib/format.js';

export const $ = s => document.querySelector(s);
export const app = $('#app');

// иконки одного набора: линия 2px, скруглённые концы
const P = {
  homeFill: '<path d="M3.5 10.6 12 4l8.5 6.6V20a1 1 0 0 1-1 1H15v-5.5a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1V21H4.5a1 1 0 0 1-1-1z" fill="currentColor" stroke="none"/>',
  basket: '<path d="M3 9h18l-2 10.5a2 2 0 0 1-2 1.5H7a2 2 0 0 1-2-1.5zM8 9l3-5M16 9l-3-5" fill="currentColor" stroke="none"/><path d="M8 9l3-5M16 9l-3-5"/>',
  userFill: '<circle cx="12" cy="7.5" r="4.5" fill="currentColor" stroke="none"/><path d="M3.5 21a8.5 7 0 0 1 17 0z" fill="currentColor" stroke="none"/>',
  thumb: '<path d="M7 10v11H3.5a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1zM7 10l4-7.5a2.3 2.3 0 0 1 2.6 2.6L13 9h6.3a2 2 0 0 1 2 2.4l-1.6 7.8A2.3 2.3 0 0 1 17.4 21H7" fill="currentColor" stroke="none"/>',
  arrowL: '<path d="M20 12H4M10 6l-6 6 6 6"/>',
  starFill: '<path d="M12 3.5l2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 16.9l-5.3 2.7 1-5.8-4.2-4.1 5.9-.9z" fill="currentColor"/>',
  dots: '<circle cx="12" cy="5" r="1.6" fill="currentColor"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/><circle cx="12" cy="19" r="1.6" fill="currentColor"/>',
  tag: '<path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9zM8 8h.01"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  up2: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  home: '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
  cart: '<path d="M3 4h2l2.4 11h9.6l2-8H6"/><circle cx="9" cy="19.5" r="1.4"/><circle cx="17" cy="19.5" r="1.4"/>',
  orders: '<path d="M6 3h12l1 4H5zM5 7h14v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1zM9 11h6M9 15h4"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  pin: '<path d="M12 21s7-6.5 7-12a7 7 0 0 0-14 0c0 5.5 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>',
  down: '<path d="M6 9l6 6 6-6"/>',
  back: '<path d="M15 5l-7 7 7 7"/>',
  right: '<path d="M9 5l7 7-7 7"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  heart: '<path d="M12 20s-8-5-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 9c0 6-8 11-8 11z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  bike: '<circle cx="6" cy="17" r="3"/><circle cx="18" cy="17" r="3"/><path d="M6 17l4-8h5l3 8M9 6h3"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
  star: '<path d="M12 3.5l2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 16.9l-5.3 2.7 1-5.8-4.2-4.1 5.9-.9z"/>',
  up: '<path d="M7 10v10H4V10zM7 10l4-7a2 2 0 0 1 2 2v4h6a2 2 0 0 1 2 2l-2 7a2 2 0 0 1-2 2H7"/>',
  thumbdown: '<path d="M7 14V4H4v10zM7 14l4 7a2 2 0 0 0 2-2v-4h6a2 2 0 0 0 2-2l-2-7a2 2 0 0 0-2-2H7"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  card: '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3 10h18M7 15h3"/>',
  cash: '<rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 9v.01M18 15v.01"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
  moon: '<path d="M20 14A8 8 0 1 1 10 4a6.5 6.5 0 0 0 10 10z"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17h.01"/>',
  store: '<path d="M4 10v10h16V10M3 10l2-6h14l2 6M3 10h18M9 20v-6h6v6"/>',
  locate: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><circle cx="12" cy="12" r="7"/>',
  repeat: '<path d="M4 12a8 8 0 0 1 14-5.3L20 9M20 4v5h-5M20 12a8 8 0 0 1-14 5.3L4 15M4 20v-5h5"/>',
  alert: '<path d="M12 3l10 18H2zM12 10v5M12 18h.01"/>',
  install: '<rect x="6" y="2.5" width="12" height="19" rx="2.5"/><path d="M12 7v7M9 11l3 3 3-3"/>',
  logout: '<path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10"/>',
  // курьер
  nav: '<path d="M3 11l18-8-8 18-2-8z"/>',
  car: '<path d="M5 16V11l2-5h10l2 5v5M3 16h18v3h-3v-3M6 16v3H3M7.5 13h.01M16.5 13h.01M5 11h14"/>',
  power: '<path d="M12 3v8M6.3 7.3a8 8 0 1 0 11.4 0"/>',
  wallet: '<path d="M4 7h15a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1zM4 7l11-3v3M16 13h.01"/>',
  bag: '<path d="M5 8h14l-1 12H6zM9 8V6a3 3 0 0 1 6 0v2"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
  chat: '<path d="M4 20l1.5-4A8 8 0 1 1 8 18.5z"/>',
  timer: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M9 2h6"/>',
  flag: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
  arrowR: '<path d="M4 12h16M14 6l6 6-6 6"/>',
  radar: '<circle cx="12" cy="12" r="2"/><path d="M16.2 7.8a6 6 0 0 1 0 8.4M7.8 16.2a6 6 0 0 1 0-8.4M19 5a10 10 0 0 1 0 14M5 19A10 10 0 0 1 5 5"/>',
  route: '<circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="6" r="2.5"/><path d="M8.5 18H15a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h6.5"/>',
  gift: '<path d="M4 9h16v4H4zM5 13h14v7H5zM12 9v11M12 9c-1-3-5-4-5-1s5 1 5 1zM12 9c1-3 5-4 5-1s-5 1-5 1z"/>',
};
export const ico = (name, cls = '') => `<svg class="ico ${cls}" viewBox="0 0 24 24" aria-hidden="true">${P[name]}</svg>`;
export const starFill = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5l2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 16.9l-5.3 2.7 1-5.8-4.2-4.1 5.9-.9z"/></svg>';

// действия по data-a: модули регистрируют обработчики, app.js вызывает
export const actions = {};
export const on = (name, fn) => { actions[name] = fn; };

let toastTimer;
export function toast(msg) {
  let t = $('#toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; t.setAttribute('role', 'status'); document.body.append(t); }
  t.textContent = msg; t.hidden = false; t.style.animation = 'none'; void t.offsetWidth; t.style.animation = '';
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 3200);
}

// шторка снизу (на компьютере — окно по центру)
let sheetClose = null, lastFocus = null;
export function openSheet(html, { foot = '', label = '', onClose = null, keepScroll = false } = {}) {
  const prev = keepScroll ? $('.sheet-in')?.scrollTop : 0;
  if (!$('#sheet')) lastFocus = document.activeElement;
  closeSheetDom();
  document.body.insertAdjacentHTML('beforeend', `<div class="scrim" id="scrim"></div>
    <div class="sheet" id="sheet" role="dialog" aria-modal="true" aria-label="${esc(label)}"><div class="grab"></div>
      <button class="round sheet-x" data-a="closeSheet" aria-label="Закрыть">${ico('close')}</button>
      <div class="sheet-in">${html}</div>${foot ? `<div class="sheet-foot">${foot}</div>` : ''}</div>`);
  sheetClose = onClose;
  document.body.style.overflow = 'hidden';
  if (prev) $('.sheet-in').scrollTop = prev;
  else $('#sheet').focus?.();
}
function closeSheetDom() { $('#scrim')?.remove(); $('#sheet')?.remove(); }
export function closeSheet() {
  if (!$('#sheet')) return;
  closeSheetDom(); document.body.style.overflow = '';
  const fn = sheetClose; sheetClose = null; fn?.();
  lastFocus?.focus?.();
}
export const sheetOpen = () => !!$('#sheet');
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSheet(); });
document.addEventListener('click', e => { if (e.target.id === 'scrim') closeSheet(); });

/** Кнопка, которая подтверждает опасное действие вторым нажатием. */
export function twice(btn, label) {
  if (btn.dataset.armed) return true;
  btn.dataset.armed = '1'; const old = btn.innerHTML; btn.textContent = label;
  setTimeout(() => { if (btn.isConnected) { delete btn.dataset.armed; btn.innerHTML = old; } }, 3500);
  return false;
}
