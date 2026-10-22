import { shops } from '../data/catalog.js';
import { esc, money } from '../lib/format.js';
import { C, save, ui } from '../state.js';
import { $, ico } from '../ui/dom.js';
import { productCard, shopCard } from './parts.js';

// Общий поиск по всем магазинам: «молоко» — где есть, где дешевле
const norm = s => String(s).toLowerCase().replace(/ё/g, 'е');
const SUGGEST = ['Помидоры', 'Молоко', 'Плов', 'Lattafa', 'Хлеб', 'Бургер'];

export function vSearch() {
  return `<div class="row"><button class="round" data-a="back" aria-label="Назад">${ico('back')}</button>
      <label class="search grow">${ico('search')}<input id="q" type="search" enterkeyhint="search" placeholder="Товар, бренд или магазин" value="${esc(ui.q)}" aria-label="Поиск" autocomplete="off"></label></div>
    <div id="results">${results()}</div>`;
}
export function results() {
  const q = norm(ui.q.trim());
  if (q.length < 2) {
    const recent = C.recent.slice(0, 6);
    return `${recent.length ? `<section class="section"><div class="section-head"><h3>Вы искали</h3><button class="link" data-a="clearRecent">Очистить</button></div><div class="chips wrap">${recent.map(t => `<button class="chip" data-a="searchFor" data-q="${esc(t)}">${ico('repeat', 'sm')} ${esc(t)}</button>`).join('')}</div></section>` : ''}
      <section class="section"><h3>Часто ищут</h3><div class="chips wrap">${SUGGEST.map(t => `<button class="chip" data-a="searchFor" data-q="${t}">${t}</button>`).join('')}</div></section>`;
  }
  const all = shops();
  const sh = all.filter(s => norm(s.name).includes(q) || norm(s.about).includes(q));
  const found = all.flatMap(s => s.products.filter(p => norm(`${p.name} ${p.cat} ${p.attrs?.brand || ''}`).includes(q)).map(p => ({ s, p })));
  found.sort((a, b) => a.p.price - b.p.price);
  if (!sh.length && !found.length) return `<div class="empty"><p>По запросу «${esc(ui.q)}» ничего не нашлось. Проверьте написание или поищите похожее.</p></div>`;
  const cheapest = found.length > 1 ? found[0] : null;
  return `${sh.length ? `<section class="section"><h2>Магазины</h2><div class="shops">${sh.map(shopCard).join('')}</div></section>` : ''}
    ${found.length ? `<section class="section"><div class="section-head"><h2>Товары · ${found.length}</h2>${cheapest ? `<span class="small muted" style="flex-basis:100%">дешевле всего — ${money(cheapest.p.price)} в «${esc(cheapest.s.name)}»</span>` : ''}</div>
      <div class="grid">${found.slice(0, 40).map(({ s, p }) => productCard(s, p).replace('<span class="meta">', `<span class="meta"><b style="color:var(--ink)">${esc(s.name)}</b> · `)).join('')}</div></section>` : ''}`;
}
export function remember(q) {
  q = q.trim(); if (q.length < 2) return;
  C.recent = [q, ...C.recent.filter(x => norm(x) !== norm(q))].slice(0, 8); save();
}
export function refreshResults() { const r = $('#results'); if (r) r.innerHTML = results(); }
