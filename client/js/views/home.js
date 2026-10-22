import { KINDS } from '../config.js';
import { eta, kindName, openState, shopById, shops } from '../model/catalog.js';
import { STAGES, view } from '../model/orders.js';
import { esc } from '../lib/format.js';
import { C, ui } from '../state.js';
import { pic } from '../ui/art.js';
import { ico } from '../ui/dom.js';
import { backBar, kindImg, productCard, shopCard } from './parts.js';

const FILTERS = [['all', 'Все'], ['open', 'Открыты сейчас'], ['fast', 'Быстрая доставка'], ['top', 'Рейтинг 4,7+']];
const pass = { all: () => true, open: s => openState(s).open, fast: s => s.prep <= 20, top: s => !s.isNew && s.rating >= 4.7 };

export function addrShort() {
  const a = C.addr; if (!a) return '';
  return [a.street, a.house].filter(Boolean).join(', ') || a.city;
}

export function vHome() {
  const all = shops(), list = all.filter(pass[ui.filter] || pass.all);
  const live = C.orders.map(view).find(v => v.stage >= 0 && v.stage < 4);
  const sales = all.map(s => ({ s, off: Math.max(0, ...s.products.filter(p => p.oldPrice > p.price).map(p => Math.round((1 - p.price / p.oldPrice) * 100))) })).filter(x => x.off);
  const past = C.orders.filter(o => o.receivedAt && shopById(o.shopId)).slice(0, 4);
  return `
    <div class="topbar">
      <button class="addr-btn" data-a="address">${ico('pin')}<span class="grow"><small>Доставка${C.addr ? ' · ' + esc(C.addr.city) : ''}</small><b>${esc(addrShort()) || 'Укажите адрес доставки'}</b></span>${ico('down', 'sm')}</button>
      <button class="round" data-go="#/profile" aria-label="Профиль">${ico('user')}</button>
    </div>
    <button class="search" data-go="#/search">${ico('search')}<span>Найти товар или магазин</span></button>
    ${live ? `<button class="notice ok" data-go="#/order/${live.o.id}" style="border:0;text-align:left;width:100%">${ico('bike')}<span class="grow"><b>Заказ № ${live.o.no}: ${STAGES[live.stage].toLowerCase()}</b><br><span class="small">${esc(live.o.shopName)}${live.waiting ? ' · нужен ваш ответ по замене' : ''}</span></span>${ico('right', 'chev')}</button>` : ''}
    <div class="kinds">${KINDS.map(k => `<button class="kind" data-go="#/kind/${k.id}"><img src="img/kind-${k.id}.webp" alt="" width="110" height="110"><b>${k.name}</b></button>`).join('')}</div>
    ${sales.length ? `<section class="section"><div class="strip">${sales.map(({ s, off }) => `<button class="promo" style="background:${s.color}" data-go="#/shop/${s.id}"><b>Скидки до ${off}% в «${esc(s.name)}»</b><span>${esc(kindName(s.kind))} · доставка ${eta(s)}</span>${kindImg(s.kind, '')}</button>`).join('')}</div></section>` : ''}
    ${past.length ? `<section class="section"><div class="section-head"><h2>Заказать снова</h2></div><div class="strip">${past.map(o => {
      const s = shopById(o.shopId);
      return `<button class="again" data-a="repeat" data-id="${o.id}"><span class="thumbs">${o.items.slice(0, 3).map(i => `<span>${pic(s.products.find(p => p.id === i.pid) || { cat: '', name: i.name })}</span>`).join('')}</span><b class="small">${esc(o.shopName)}</b><span class="tiny muted">${o.items.length} ${o.items.length === 1 ? 'товар' : 'товара'}</span></button>`;
    }).join('')}</div></section>` : ''}
    <section class="section">
      <div class="section-head"><h2>Все магазины</h2></div>
      <div class="chips">${FILTERS.map(([k, t]) => `<button class="chip" data-a="filter" data-v="${k}" aria-pressed="${(ui.filter || 'all') === k}">${t}</button>`).join('')}</div>
      ${list.length ? `<div class="shops">${list.map(shopCard).join('')}</div>` : '<div class="empty"><p>Таких магазинов пока нет. Попробуйте другой фильтр.</p></div>'}
    </section>`;
}

export function vKind(id) {
  const k = KINDS.find(x => x.id === id); if (!k) return vHome();
  const list = shops().filter(s => s.kind === id);
  const hits = list.flatMap(s => s.products.filter(p => p.labels.includes('Хит') || p.oldPrice).map(p => [s, p])).slice(0, 10);
  return `${backBar(k.name)}
    <div class="shops">${list.map(shopCard).join('') || '<div class="empty"><p>В вашем городе пока нет таких магазинов.</p></div>'}</div>
    ${hits.length ? `<section class="section"><h2>Популярное</h2><div class="grid">${hits.map(([s, p]) => productCard(s, p)).join('')}</div></section>` : ''}`;
}
