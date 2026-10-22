import { REVIEW_BAD, REVIEW_GOOD, PROBLEMS, WEIGHT_UNITS } from '../config.js';
import { add, clear } from '../model/cart.js';
import { productIn, shopById } from '../model/catalog.js';
import { addrLine, answerSub, cancel, received, reportProblem, sendReview, STAGES, view } from '../model/orders.js';
import { esc, hhmm, money, qtyLabel, whenText } from '../lib/format.js';
import { C } from '../state.js';
import { $, closeSheet, ico, openSheet, starFill, toast, twice } from '../ui/dom.js';
import { backBar, logo } from './parts.js';

// Отслеживание заказа, получение, оценка, история
const TITLES = ['Магазин получил заказ', 'Собираем ваш заказ', 'Передаём курьеру', 'Курьер в пути', 'Заказ доставлен'];
const q = (n, unit) => WEIGHT_UNITS.includes(unit) ? qtyLabel(n, unit) : `${n} ${unit || 'шт'}`;
const find = id => C.orders.find(o => o.id === id);

export function vOrder(id) {
  const o = find(id);
  if (!o) return `${backBar('Заказ')}<div class="empty"><p>Заказ не найден.</p><button class="btn primary" data-go="#/orders">Мои заказы</button></div>`;
  const v = view(o), shop = v.shop || { name: o.shopName, kind: o.kind, color: '#f5f4f2', logo: '' };
  const sub = v.stage < 0 ? (v.reason || 'Заказ отменён') : v.stage === 4 ? `Доставлен ${whenText(o.receivedAt)}`
    : o.when && o.when.at > Date.now() + 15 * 60000 && v.stage < 2 ? `Привезём ${o.when.label.toLowerCase()}` : `Привезём примерно к ${hhmm(v.eta)}`;
  return `${backBar(`Заказ № ${o.no}`, v.stage >= 3 ? `<button class="round" data-a="problem" data-id="${o.id}" aria-label="Сообщить о проблеме">${ico('help')}</button>` : '', '#/orders')}
    <section class="status-hero">
      <div class="col" style="gap:6px"><h1>${v.stage < 0 ? 'Заказ отменён' : TITLES[v.stage]}</h1><span class="muted">${esc(sub)}</span></div>
      ${v.stage >= 0 ? `<div class="steps" aria-label="Этап ${v.stage + 1} из 5: ${STAGES[v.stage]}">${STAGES.map((_, i) => `<i class="${i < v.stage || v.stage === 4 ? 'on' : i === v.stage ? 'now' : ''}"></i>`).join('')}</div>` : ''}
      ${v.stage === 3 ? `<button class="btn primary block" data-a="received" data-id="${o.id}">${ico('check')} Заказ получил</button><span class="tiny muted">После этого деньги уйдут магазину. Если что-то не так — нажмите «?» вверху.</span>` : ''}
      ${v.stage === 0 ? `<button class="btn block" data-a="cancelOrder" data-id="${o.id}">Отменить заказ</button>` : ''}
    </section>
    ${v.subs.filter(x => x.i.sub.status === 'wait').map(({ i, n }) => `<section class="sub-ask"><b>В магазине нет «${esc(i.name)}»</b>
      <span>Предлагают замену: <b>${esc(i.sub.name)}</b> × ${q(i.sub.qty, i.sub.unit)} — ${money(i.sub.qty * i.sub.price)}${i.sub.price > i.price ? ' (дороже)' : ''}</span>
      <div class="grid2"><button class="btn" data-a="subNo" data-id="${o.id}" data-n="${n}">Не надо</button><button class="btn dark" data-a="subYes" data-id="${o.id}" data-n="${n}">Согласен</button></div></section>`).join('')}
    ${v.diff > 0.009 && v.stage >= 2 ? `<div class="notice ok">${ico('check', 'sm')}<span>После сборки сумма меньше на <b>${money(v.diff)}</b>. ${o.pay === 'cash' ? 'Курьеру платите новую сумму.' : 'Разницу вернём на карту.'}</span></div>` : ''}
    ${v.stage === 4 && !o.review ? `<section class="status-hero" style="background:var(--accent-soft)"><h3>Как вам заказ?</h3><div class="stars-pick">${[1, 2, 3, 4, 5].map(s => `<button data-a="rate" data-id="${o.id}" data-v="${s}" aria-label="${s} из 5">${starFill}</button>`).join('')}</div></section>` : ''}
    ${o.review ? `<div class="notice info">${ico('star', 'sm')}<span>Ваша оценка: <b>${'★'.repeat(o.review.rating)}</b>${o.review.text ? ' — ' + esc(o.review.text) : ''}. Спасибо!</span></div>` : ''}
    ${o.problem ? `<div class="notice">${ico('alert', 'sm')}<span>Обращение отправлено: ${esc(o.problem.reason)}. Поддержка свяжется с вами.</span></div>` : ''}
    <section class="section">
      <div class="li list" style="border-radius:var(--r)">${logo(shop)}<span class="grow"><b>${esc(o.shopName)}</b><small>${esc(shop.address || '')}</small></span>${o.phone ? `<a class="round" href="tel:${o.phone.replace(/\s/g, '')}" aria-label="Позвонить в магазин" style="color:inherit">${ico('phone')}</a>` : ''}</div>
      <div>${v.rows.map(r => {
        const opts = r.opts?.length ? `<small>${r.opts.map(x => esc(x.name)).join(', ')}</small>` : '';
        if (r.missing) return `<div class="item-line"><span><s>${esc(r.name)} × ${q(r.qty, r.unit)}</s><small>нет в наличии${r.sub ? ` · замена: ${esc(r.sub.name)} — ${{ wait: 'ждём ответа', ok: 'согласовано', no: 'отказались' }[r.sub.status]}` : ''}</small></span><span class="num">${r.sub?.status === 'ok' ? money(r.sub.qty * r.sub.price) : '<s class="muted">' + money(r.qty * r.price) + '</s>'}</span></div>`;
        return `<div class="item-line"><span>${esc(r.name)}${r.variant ? ', ' + esc(r.variant) : ''} × ${r.changed ? `<s>${q(r.qty, r.unit)}</s> ${q(r.q, r.unit)}` : q(r.q, r.unit)}${opts}</span><span class="num">${money(r.q * r.price)}</span></div>`;
      }).join('')}</div>
      <div class="sum-table num"><div><span>Товары</span><span>${money(v.sum)}</span></div><div><span>Доставка</span><span>${v.fee ? money(v.fee) : 'бесплатно'}</span></div><div class="total"><span>${o.pay === 'cash' ? 'Наличными курьеру' : 'Оплачено картой'}</span><span>${money(v.total)}</span></div></div>
    </section>
    <section class="section"><h3>Доставка</h3><div class="li list" style="border-radius:var(--r)">${ico('pin')}<span class="grow"><b>${esc(addrLine(o.addr))}</b><small>${esc([o.addr.entrance && 'подъезд ' + o.addr.entrance, o.addr.floor && 'этаж ' + o.addr.floor, o.addr.landmark].filter(Boolean).join(', '))}</small></span></div>
      ${o.comment ? `<span class="small muted">Комментарий: ${esc(o.comment)}</span>` : ''}</section>
    ${v.stage === 4 || v.stage < 0 ? `<button class="btn block" data-a="repeat" data-id="${o.id}">${ico('repeat')} Повторить заказ</button>` : ''}`;
}

export function vOrders() {
  const list = C.orders.map(view);
  if (!list.length) return `<h1>Заказы</h1><div class="empty"><img src="img/kind-food.webp" alt="" width="120" height="120"><h2>Заказов пока нет</h2><p>Здесь будут все ваши заказы и их статус.</p><button class="btn primary" data-go="#/">Выбрать магазин</button></div>`;
  const active = list.filter(v => v.stage >= 0 && v.stage < 4), past = list.filter(v => !(v.stage >= 0 && v.stage < 4));
  const row = v => `<button class="li" data-go="#/order/${v.o.id}">${logo(v.shop || { name: v.o.shopName, logo: '' })}<span class="grow"><b>${esc(v.o.shopName)}</b><small>№ ${v.o.no} · ${whenText(v.o.ts)} · ${money(v.total)}</small><small style="color:${v.stage < 0 ? 'var(--bad)' : v.stage === 4 ? 'var(--muted)' : 'var(--ok)'}">${v.stage < 0 ? 'Отменён' : STAGES[v.stage]}${v.waiting ? ' · нужен ваш ответ' : ''}</small></span>${ico('right', 'chev')}</button>`;
  return `<h1>Заказы</h1>
    ${active.length ? `<section class="section"><h3>Сейчас</h3><div class="list">${active.map(row).join('')}</div></section>` : ''}
    ${past.length ? `<section class="section"><h3>Раньше</h3><div class="list">${past.map(row).join('')}</div></section>` : ''}`;
}

// ----- оценка -----
let R = null;
function drawRate() {
  const o = find(R.id), good = R.rating >= 4, tags = good ? REVIEW_GOOD : REVIEW_BAD;
  openSheet(`<h2>${good ? 'Что понравилось?' : 'Что пошло не так?'}</h2>
    <div class="stars-pick">${[1, 2, 3, 4, 5].map(s => `<button class="${s <= R.rating ? 'on' : ''}" data-a="rateSet" data-v="${s}" aria-label="${s} из 5">${starFill}</button>`).join('')}</div>
    <div class="chips wrap">${tags.map(t => `<button class="chip" data-a="rateTag" data-v="${t}" aria-pressed="${R.tags.includes(t)}">${t}</button>`).join('')}</div>
    <div class="col" style="gap:10px"><span class="lbl">Оцените товары</span>${o.items.map(i => `<div class="like-row"><span class="grow">${esc(i.name)}</span>
      <button class="thumbbtn" data-a="like" data-pid="${i.pid}" data-v="1" aria-pressed="${R.likes[i.pid] === true}" aria-label="Понравилось">${ico('up', 'sm')}</button>
      <button class="thumbbtn" data-a="like" data-pid="${i.pid}" data-v="0" aria-pressed="${R.likes[i.pid] === false}" aria-label="Не понравилось">${ico('thumbdown', 'sm')}</button></div>`).join('')}</div>
    <div class="field"><label for="rText">Комментарий</label><textarea class="input" id="rText" maxlength="500" placeholder="${good ? 'Что особенно понравилось' : 'Расскажите, что исправить'}">${esc(R.text)}</textarea></div>`,
  { label: 'Оценка заказа', keepScroll: true, foot: `<button class="btn primary" data-a="rateSend">Отправить отзыв</button>`, onClose: () => { R = null; } });
}
const keepText = () => { if (R && $('#rText')) R.text = $('#rText').value; };

export const orderActions = {
  received: el => { received(find(el.dataset.id)); toast('Спасибо! Деньги ушли магазину'); },
  cancelOrder: el => { if (!twice(el, 'Нажмите ещё раз, чтобы отменить')) return false; cancel(find(el.dataset.id)); toast('Заказ отменён'); },
  subYes: el => { answerSub(find(el.dataset.id), +el.dataset.n, true); toast('Замену согласовали'); },
  subNo: el => { answerSub(find(el.dataset.id), +el.dataset.n, false); toast('Позицию уберут из заказа'); },
  rate: el => { R = { id: el.dataset.id, rating: +el.dataset.v, tags: [], likes: {}, text: '' }; drawRate(); return false; },
  rateSet: el => { keepText(); R.rating = +el.dataset.v; R.tags = []; drawRate(); return false; },
  rateTag: el => { keepText(); const t = el.dataset.v; R.tags = R.tags.includes(t) ? R.tags.filter(x => x !== t) : [...R.tags, t]; drawRate(); return false; },
  like: el => { keepText(); const v = el.dataset.v === '1'; R.likes[el.dataset.pid] = R.likes[el.dataset.pid] === v ? undefined : v; drawRate(); return false; },
  rateSend: () => { keepText(); sendReview(find(R.id), { rating: R.rating, tags: R.tags, text: R.text.trim(), likes: R.likes }); closeSheet(); toast('Спасибо за отзыв!'); },
  problem: el => {
    openSheet(`<h2>Что случилось?</h2><div class="col" style="gap:8px">${PROBLEMS.map((t, i) => `<label class="opt"><input type="radio" name="prob" value="${t}" ${i ? '' : 'checked'}><span class="grow">${t}</span></label>`).join('')}</div>
      <div class="field"><label for="pText">Подробнее</label><textarea class="input" id="pText" maxlength="500" placeholder="Например: не положили хлеб"></textarea></div>`,
    { label: 'Проблема с заказом', foot: `<button class="btn primary" data-a="problemSend" data-id="${el.dataset.id}">Отправить в поддержку</button>` });
    return false;
  },
  problemSend: el => { reportProblem(find(el.dataset.id), document.querySelector('input[name="prob"]:checked').value, $('#pText').value.trim()); closeSheet(); toast('Отправили. Поддержка свяжется с вами'); },
  repeat: (el, go) => {
    const o = find(el.dataset.id), s = shopById(o.shopId); if (!s) return toast('Магазин больше не работает'), false;
    if (C.cart.items.length && C.cart.shopId !== s.id) clear();
    let added = 0;
    for (const i of o.items) {
      const p = productIn(s, i.pid); if (!p) continue;
      const vid = p.variants.find(v => v.name === i.variant)?.id || '';
      const opts = p.options.filter(x => i.opts?.some(y => y.name === x.name)).map(x => x.id);
      add(s, p, { vid, opts, qty: Math.min(i.qty, p.stock) }, true); added++;
    }
    toast(added === o.items.length ? 'Товары в корзине' : added ? 'Часть товаров закончилась — остальные в корзине' : 'Этих товаров сейчас нет');
    if (added) go('#/cart');
    return false;
  },
};
