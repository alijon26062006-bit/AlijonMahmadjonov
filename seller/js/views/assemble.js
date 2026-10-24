import { render } from '../app.js';
import { WEIGHT_UNITS } from '../config.js';
import { orderedTotal, orderTotal } from '../domain/orders.js';
import { esc, money, num, r2 } from '../lib/format.js';
import { S, save } from '../state.js';
import { closeSheet, fmtQty, isStopped, onSheetClose, openSheet, thumb, toast } from '../ui/dom.js';

// Сборка заказа: отметить собранное, указать точный вес, предложить замену, если товара нет.
// Покупатель уже заплатил: вес можно превысить не больше чем на 10 %, разницу вниз вернём ему.
const OVER = 0.10;
let curId = null;         // открытый заказ
const order = () => S.orders.find(o => o.id === curId);
let subFor = null;        // для какой строки выбираем замену
onSheetClose(() => { curId = null; subFor = null; });

const unitOf = i => i.unit || S.products.find(p => p.id === i.pid)?.unit || 'шт';
const isWeight = i => WEIGHT_UNITS.includes(unitOf(i));
const handled = i => i.missing || i.picked;

export function sheetAssemble(id) { curId = id; subFor = null; draw(); }
/** Данные поменялись снаружи (ответ покупателя) — перерисовать открытую сборку. */
export function refreshSheet() { if (curId && subFor == null) draw(); }

function draw(keep = true) {
  const o = order(); if (!o) return;
  if (subFor != null) return drawSubs();
  const done = o.items.filter(handled).length, wait = o.items.some(i => i.sub?.status === 'wait');
  const rows = o.items.map((i, n) => {
    const p = S.products.find(x => x.id === i.pid) || { imgs: [] };
    const sub = i.sub ? `<div class="sub ${i.sub.status}">Замена: <span translate="no">${esc(i.sub.name)}</span> × ${fmtQty(i.sub.qty)} — ${money(i.sub.qty * i.sub.price)}<br><b>${{ wait: 'Ждём ответа покупателя…', ok: 'Покупатель согласился', no: 'Покупатель отказался — позиция убрана' }[i.sub.status]}</b></div>` : '';
    if (i.missing) return `<div class="pick-row is-missing">${thumb(p)}<div><div class="pname" translate="no">${esc(i.name)}${i.variant ? ', ' + esc(i.variant) : ''}</div><div class="small muted">Нет в наличии · −${money(i.qty * i.price)}</div>${sub}</div>
      <button class="btn sm" data-pk="undo" data-n="${n}">Вернуть</button></div>`;
    const w = isWeight(i), q = i.actual ?? i.qty, max = r2(i.qty * (1 + OVER));
    return `<div class="pick-row ${i.picked ? 'is-done' : ''}">${thumb(p)}<div style="min-width:0">
        <div class="pname" translate="no">${esc(i.name)}${i.variant ? ', ' + esc(i.variant) : ''}</div>
        <div class="small muted num">Заказано ${fmtQty(i.qty)} ${esc(unitOf(i))} × ${money(i.price)}${i.opts?.length ? ' · ' + i.opts.map(x => esc(x.name)).join(', ') : ''}</div>
        ${w ? `<div class="weigh"><label class="small" for="w${n}">Взвесили</label><div class="suffix"><input class="input num" id="w${n}" data-weigh="${n}" inputmode="decimal" value="${fmtQty(q)}"><span>${esc(unitOf(i))}</span></div><span class="small num ${q > max ? 'neg' : 'muted'}">${money(q * i.price)}${q > max ? ` · не больше ${fmtQty(max)} ${esc(unitOf(i))}` : ''}</span></div>` : ''}
      </div>
      <div class="col" style="gap:6px;align-items:stretch"><button class="btn sm ${i.picked ? '' : 'primary'}" data-pk="pick" data-n="${n}">${i.picked ? 'Собрано ✓' : 'Собрал'}</button><button class="btn sm" data-pk="miss" data-n="${n}">Нет в наличии</button></div></div>`;
  }).join('');
  const was = orderedTotal(o), now = orderTotal(o);
  openSheet(`Сборка заказа № ${o.no}`, `
    <div class="row between"><span class="small muted">Собрано ${done} из ${o.items.length}</span><div class="bar" style="flex:1;max-width:160px"><i style="width:${done / o.items.length * 100}%"></i></div></div>
    ${o.comment ? `<div class="ocomment small"><span translate="no">${esc(o.comment)}</span></div>` : ''}
    <div class="pick-list">${rows}</div>
    <p class="small muted" style="margin:0">Весовой товар взвесьте и впишите точный вес — сумма пересчитается. Положить больше заказанного можно не более чем на 10 %. Если товара нет, предложите замену: покупатель ответит в приложении.</p>`,
    `<div class="col" style="gap:2px"><span class="small muted">Было ${money(was)}</span><b class="num" style="font-size:17px">Итого ${money(now)}</b></div>
     <div class="row"><button class="btn" data-act="close">Позже</button><button class="btn primary" data-pk="ready" ${done === o.items.length && !wait && now > 0 ? '' : 'disabled'}>${wait ? 'Ждём ответа…' : 'Готов, отдать курьеру'}</button></div>`, keep);
}

function drawSubs() {
  const i = order().items[subFor], base = S.products.find(p => p.id === i.pid);
  const avail = S.products.filter(p => p.active && p.stock > 0 && !isStopped(p) && p.id !== i.pid);
  const same = avail.filter(p => base && p.cat === base.cat), other = avail.filter(p => !base || p.cat !== base.cat);
  const row = p => `<button class="sale-line subpick" data-subpid="${p.id}">${thumb(p)}<div style="min-width:0;text-align:left"><div class="pname" translate="no">${esc(p.name)}</div><div class="small muted num">${money(p.price)} за ${esc(p.unit)} · ост. ${fmtQty(p.stock)}</div></div><span class="small ${p.price > i.price ? 'neg' : 'muted'}">${p.price > i.price ? 'дороже' : p.price < i.price ? 'дешевле' : 'та же цена'}</span></button>`;
  openSheet(`Нет «${i.name}»`, `
    <div class="col" style="gap:8px">
      <button class="btn" data-pk="drop">Просто убрать из заказа (−${money(i.qty * i.price)})</button>
      <span class="lbl" style="margin-top:8px">Или предложить замену</span>
      ${same.length ? `<span class="small muted">Из той же категории</span>${same.map(row).join('')}` : ''}
      ${other.length ? `<details class="more"><summary>Другие товары (${other.length})</summary><div class="col">${other.map(row).join('')}</div></details>` : ''}
      ${avail.length ? '' : '<span class="muted">Нет других товаров в наличии.</span>'}
    </div>`, `<span></span><button class="btn" data-pk="back">Назад к сборке</button>`);
}

function act(t) {
  const o = order(), n = +t.dataset.n, i = o.items[n], k = t.dataset.pk;
  if (k === 'pick') i.picked = !i.picked;
  if (k === 'miss') { subFor = n; return draw(); }
  if (k === 'back') { subFor = null; return draw(false); }
  if (k === 'drop') { Object.assign(o.items[subFor], { missing: true, picked: false, sub: null }); subFor = null; }
  if (k === 'undo') Object.assign(i, { missing: false, sub: null });
  if (k === 'ready') return finish();
  save(); draw(); render();
}
function chooseSub(pid) {
  const i = order().items[subFor], p = S.products.find(x => x.id === pid);
  const qty = WEIGHT_UNITS.includes(p.unit) ? i.qty : Math.max(1, Math.round(i.qty));
  Object.assign(i, { missing: true, picked: false, sub: { pid: p.id, name: p.name, unit: p.unit, qty, price: p.price, cost: p.cost, status: 'wait', ts: Date.now() } });
  subFor = null; save(); draw(false); render(); toast('Замену отправили покупателю');
}
function finish() {
  const o = order();
  for (const i of o.items) {
    const p = S.products.find(x => x.id === i.pid);
    // остаток при заказе уже списан на заказанное количество — поправляем на разницу
    if (p) p.stock = Math.max(0, r2(p.stock + i.qty - (i.missing ? 0 : i.actual ?? i.qty)));
    if (i.sub?.status === 'ok') { const s = S.products.find(x => x.id === i.sub.pid); if (s) s.stock = Math.max(0, r2(s.stock - i.sub.qty)); }
  }
  const diff = orderedTotal(o) - orderTotal(o);
  o.status = 'ready'; o.assembledAt = Date.now(); save(); closeSheet(); render();
  toast(diff > 0.009 ? `Заказ № ${o.no} готов. Покупателю вернём ${money(diff)}` : `Заказ № ${o.no} готов, курьер уже едет`);
}

document.addEventListener('click', e => {
  if (!curId) return;
  const t = e.target.closest('[data-pk],[data-subpid]'); if (!t || t.disabled) return;
  if (t.dataset.subpid) return chooseSub(t.dataset.subpid);
  act(t);
});
document.addEventListener('change', e => {
  const n = e.target.dataset?.weigh; if (!curId || n == null) return;
  const i = order().items[+n], v = num(e.target.value), max = r2(i.qty * (1 + OVER));
  if (v == null || v <= 0) { toast('Введите вес, например 1,05'); return draw(); }
  if (v > max) toast(`Покупатель оплатил ${fmtQty(i.qty)} ${unitOf(i)}. Положите не больше ${fmtQty(max)} ${unitOf(i)}`);
  i.actual = Math.min(r2(v), max); i.picked = true; save(); draw(); render();
});

// тестовый режим: на заказы-примеры покупатель отвечает сам; на заказы из приложения покупателя отвечает он
setInterval(() => {
  if (!S) return;
  let changed = false;
  for (const o of S.orders) if (!o.client) for (const i of o.items) if (i.sub?.status === 'wait' && Date.now() - i.sub.ts > 5000) {
    i.sub.status = Math.random() < 0.8 ? 'ok' : 'no'; i.picked = false; changed = true;
    toast(i.sub.status === 'ok' ? `Покупатель согласен на замену: ${i.sub.name}` : `Покупатель отказался от замены — позиция убрана`);
  }
  if (!changed) return;
  save(); render(); if (curId && subFor == null) draw();
}, 2000);
