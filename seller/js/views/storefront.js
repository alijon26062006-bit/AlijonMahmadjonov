import { esc, money } from '../lib/format.js';
import { S } from '../state.js';
import { pic } from '../ui/dom.js';

// Витрина
export function vPreview() {
  const vis = S.products.filter(p => p.active && p.stock > 0);
  const cats = S.cats.filter(c => vis.some(p => p.cat === c));
  const sh = S.shop;
  const dow = (new Date().getDay() + 6) % 7, sc = sh.schedule[dow];
  const logo = sh.logo ? `<img src="${sh.logo}" alt="">` : esc((sh.name || '?').trim().charAt(0).toUpperCase());
  const card = p => { const from = p.variants.length ? Math.min(...p.variants.map(v => v.price)) : p.price;
    return `<article class="card"><div class="pic">${pic(p)}<div class="tags">${p.oldPrice ? `<span class="sale">−${Math.round((1 - p.price / p.oldPrice) * 100)}%</span>` : ''}${p.labels.map(l => `<span>${esc(l)}</span>`).join('')}</div></div><div class="body"><div class="t">${esc(p.name)}</div>${p.desc ? `<div class="d">${esc(p.desc)}</div>` : ''}<div class="pr"><div><b class="num">${p.variants.length ? 'от ' : ''}${money(from)}</b>${p.oldPrice ? `<s class="num">${money(p.oldPrice)}</s>` : ''}</div><button class="add" tabindex="-1" aria-hidden="true">+</button></div></div></article>`; };
  return `
    <div class="head"><div><div class="eyebrow">Так покупатели увидят ваш магазин в приложении</div><h1>Витрина</h1></div></div>
    <section class="panel store-hero"><div class="store-logo">${logo}</div><div class="col" style="gap:4px">
      <h2 style="font-family:var(--f-display);font-weight:500;font-size:20px">${esc(sh.name)}</h2>
      <span class="small muted">${sh.paused ? '<b style="color:var(--bad)">Временно не принимает заказы</b>' : sc.open ? `Открыто сегодня ${sc.from}–${sc.to}` : '<b style="color:var(--bad)">Сегодня выходной</b>'} · сборка ~${sh.prep} мин${sh.minOrder ? ' · заказ от ' + money(sh.minOrder) : ''}</span>
      <span class="small muted">${[sh.delivery && 'Доставка', sh.pickup && 'Самовывоз'].filter(Boolean).join(' и ')} · ${esc(sh.address)}</span>
      ${sh.about ? `<span style="font-size:14px">${esc(sh.about)}</span>` : ''}</div></section>
    ${vis.length ? cats.map(c => `<section class="col" style="gap:10px"><h2>${esc(c)}</h2><div class="cards">${vis.filter(p => p.cat === c).map(card).join('')}</div></section>`).join('')
      : '<div class="empty panel"><b>Витрина пустая</b><span>Покупатели видят только товары, которые есть в наличии и не скрыты.</span></div>'}`;
}
