import { esc, money } from '../lib/format.js';
import { S } from '../state.js';
import { onSale, pic } from '../ui/dom.js';
import { attrLine } from './product.js';
import { rating } from '../domain/reviews.js';

// Витрина
export function vPreview() {
  const vis = S.products.filter(onSale);
  const cats = S.cats.filter(c => vis.some(p => p.cat === c));
  const sh = S.shop;
  const dow = (new Date().getDay() + 6) % 7, sc = sh.schedule[dow];
  const logo = sh.logo ? `<img src="${sh.logo}" alt="">` : esc((sh.name || '?').trim().charAt(0).toUpperCase());
  const card = p => { const from = p.variants.length ? Math.min(...p.variants.map(v => v.price)) : p.price;
    return `<article class="card"><div class="pic">${pic(p)}<div class="tags">${p.oldPrice ? `<span class="sale">−${Math.round((1 - p.price / p.oldPrice) * 100)}%</span>` : ''}${p.labels.map(l => `<span>${esc(l)}</span>`).join('')}</div></div><div class="body"><div class="t" translate="no">${esc(p.name)}</div>${attrLine(p) || p.desc ? `<div class="d" translate="no">${esc(attrLine(p) || p.desc)}</div>` : ''}${p.options?.length ? `<div class="d">Можно выбрать добавки</div>` : ''}<div class="pr"><div><b class="num">${p.variants.length ? 'от ' : ''}${money(from)}</b>${p.oldPrice ? `<s class="num">${money(p.oldPrice)}</s>` : ''}</div><button class="add" tabindex="-1" aria-hidden="true">+</button></div></div></article>`; };
  return `
    <div class="head"><div><div class="eyebrow">Так покупатели увидят ваш магазин в приложении</div><h1>Витрина</h1></div></div>
    <section class="panel store-hero"><div class="store-logo">${logo}</div><div class="col" style="gap:4px">
      <h2 style="font-family:var(--f-display);font-weight:500;font-size:20px"><span translate="no">${esc(sh.name)}</span></h2>
      <span class="small"><b>${(R => R.isNew ? 'Новый магазин' : `★ ${R.value.toLocaleString('ru-RU', { minimumFractionDigits: 1 })}</b> <span class="muted">· ${R.count} оценок</span><b>`)(rating())}</b></span>
      <span class="small muted">${sh.paused ? '<b style="color:var(--bad)">Временно не принимает заказы</b>' : sc.open ? `Открыто сегодня <span class="num">${sc.from}–${sc.to}</span>` : '<b style="color:var(--bad)">Сегодня выходной</b>'} · <span>сборка ~${sh.prep} мин</span>${sh.minOrder ? ' · <span>заказ от ' + money(sh.minOrder) + '</span>' : ''}</span>
      <span class="small muted">${[sh.delivery && 'Доставка', sh.pickup && 'Самовывоз'].filter(Boolean).join(' и ')} · <span translate="no">${esc(sh.address)}</span></span>
      ${sh.about ? `<span style="font-size:14px" translate="no">${esc(sh.about)}</span>` : ''}</div></section>
    ${vis.length ? cats.map(c => `<section class="col" style="gap:10px"><h2>${esc(c)}</h2><div class="cards">${vis.filter(p => p.cat === c).map(card).join('')}</div></section>`).join('')
      : '<div class="empty panel"><b>Витрина пустая</b><span>Покупатели видят только товары, которые есть в наличии и не скрыты.</span></div>'}`;
}
