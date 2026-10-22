import { render } from '../app.js';
import { CANCEL_REASONS, STATUS, WEIGHT_UNITS } from '../config.js';
import { changeStockForOrder, orderedTotal, orderTotal } from '../domain/orders.js';
import { sheetAssemble } from './assemble.js';
import { esc, hhmm, minsAgo, money, parseKey, today, uid, whenText } from '../lib/format.js';
import { S, save, ui } from '../state.js';
import { MELODIES } from '../services/alerts.js';
import { closeSheet, fmtQty, ICON, onSale, onSheetClose, openSheet, plusI, thumb, toast } from '../ui/dom.js';

// Заказы
export function vOrders() {
  const groups = { new: ['new'], work: ['accepted', 'ready'], done: ['done'], cancelled: ['cancelled'] };
  const cnt = k => S.orders.filter(o => groups[k].includes(o.status)).length;
  const oq = ui.oq.trim().replace(/^№\s*/, '').toLowerCase();
  let list = (oq ? S.orders.filter(o => String(o.no).includes(oq) || (o.customer && (o.customer.name.toLowerCase().includes(oq) || o.customer.phone.replace(/\D/g, '').includes(oq.replace(/\D/g, '') || '§'))))
                 : S.orders.filter(o => groups[ui.ordTab].includes(o.status))).sort((a, b) => b.ts - a.ts);
  const more = list.length > 40; list = list.slice(0, 40);
  const tab = (k, l) => `<button class="chip" data-otab="${k}" aria-pressed="${ui.ordTab === k}">${l} <b class="num">${cnt(k)}</b></button>`;
  return `
    <div class="head"><div><div class="eyebrow">${esc(S.shop.name)}</div><h1>Заказы</h1></div>
      <div class="row"><button class="btn" data-act="testorder">Тестовый заказ</button><button class="btn primary" data-act="sale">${plusI} Продажа в магазине</button></div></div>
    <div class="search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input class="input" id="oq" type="search" inputmode="search" placeholder="Найти заказ по номеру, имени или телефону" value="${esc(ui.oq)}" aria-label="Поиск заказа"></div>
    ${oq ? `<span class="small muted">Найдено: ${list.length}</span>` : ''}
    <div class="seg" role="group" aria-label="Статус" ${oq ? 'hidden' : ''}>${tab('new', 'Новые')}${tab('work', 'В работе')}${tab('done', 'Выполненные')}${tab('cancelled', 'Отменённые')}</div>
    ${list.length ? `<div class="orders">${list.map(orderCard).join('')}</div>${more ? '<p class="muted small" style="margin:0">Показаны последние 40 заказов. Все продажи по дням есть в «Статистике».</p>' : ''}` : `<div class="empty panel"><b>${ui.ordTab === 'new' ? 'Новых заказов нет' : 'Здесь пока пусто'}</b><span>${ui.ordTab === 'new' ? 'Когда покупатель оформит заказ, он появится здесь, а на телефон придёт уведомление со звуком. Нажмите «Тестовый заказ», чтобы посмотреть, как это выглядит.' : ''}</span></div>`}
    <section class="col" style="gap:10px;margin-top:8px"><h2>Настройки приёма</h2>
    <label class="switch" for="pauseSw"><span><b style="font-weight:600">Принимаю заказы</b><br><span class="small muted">Выключите, если закрылись раньше или не успеваете. Покупатели увидят «Временно не работает».</span></span><input type="checkbox" id="pauseSw" ${S.shop.paused ? '' : 'checked'}></label>
    <div class="grid2">
      <label class="switch" for="soundSw"><span><b style="font-weight:600">Звук о новых заказах</b><br><span class="small muted">Звонит, пока вы не ответите</span></span><input type="checkbox" id="soundSw" ${S.shop.sound !== false ? 'checked' : ''}></label>
      <label class="switch" for="awakeSw"><span><b style="font-weight:600">Не гасить экран</b><br><span class="small muted">Пока открыт кабинет, телефон не уснёт</span></span><input type="checkbox" id="awakeSw" ${S.shop.awake !== false ? 'checked' : ''}></label>
      <label class="switch" for="autoSw"><span><b style="font-weight:600">Принимать автоматически</b><br><span class="small muted">Со временем сборки ${S.shop.prep} мин</span></span><input type="checkbox" id="autoSw" ${S.shop.autoAccept ? 'checked' : ''}></label>
    </div>
    <div class="panel col" style="gap:10px"><span class="lbl">Мелодия нового заказа</span>
      <div class="chips wrap" role="radiogroup" aria-label="Мелодия">${MELODIES.map(([id, t]) => `<button class="chip" data-melody="${id}" aria-pressed="${(S.shop.melody || 'bell') === id}">${t}</button>`).join('')}</div>
      <div><button class="btn" data-act="testsound">Проверить звук</button></div>
      <span class="small muted">Сделайте громкость телефона на максимум и выключите беззвучный режим. Когда кабинет закрыт, сайт звонить не может — для этого нужно приложение с уведомлениями.</span></div>
    </section>`;
}
const itemLine = i => {
  const name = `${esc(i.name)}${i.variant ? ', ' + esc(i.variant) : ''}`;
  const opts = i.opts?.length ? `<br><small class="muted">${i.opts.map(x => esc(x.name) + (x.price ? ` +${money(x.price)}` : '')).join(', ')}</small>` : '';
  const sub = i.sub ? `<li class="subline"><span>→ замена: ${esc(i.sub.name)} × ${fmtQty(i.sub.qty)} <small class="pill ${i.sub.status === 'ok' ? '' : i.sub.status === 'no' ? 'bad' : 'warn'}">${{ wait: 'ждём ответа', ok: 'согласен', no: 'отказался' }[i.sub.status]}</small></span><span class="num">${i.sub.status === 'ok' ? money(i.sub.qty * i.sub.price) : ''}</span></li>` : '';
  if (i.missing) return `<li class="missing"><span><s>${name} × ${fmtQty(i.qty)}</s> <small class="pill bad">нет в наличии</small>${opts}</span><span class="num"><s>${money(i.qty * i.price)}</s></span></li>${sub}`;
  const q = i.actual ?? i.qty;
  return `<li><span>${name} × ${i.actual != null && i.actual !== i.qty ? `<s class="muted">${fmtQty(i.qty)}</s> ${fmtQty(q)}` : fmtQty(q)}${i.picked ? ' <small class="pill">собрано</small>' : ''}${opts}</span><span class="num">${money(q * i.price)}</span></li>`;
};
export function orderCard(o) {
  const total = orderTotal(o);
  const src = o.source === 'shop' ? '<span class="pill off">В магазине</span>' : o.delivery === 'pickup' ? '<span class="pill info">Самовывоз</span>' : '<span class="pill info">Доставка</span>';
  let acts = '';
  if (o.status === 'new') acts = `<button class="btn primary sm" data-oact="accept" data-id="${o.id}">Принять</button><button class="btn sm" data-oact="cancel" data-id="${o.id}">Отклонить</button>`;
  if (o.status === 'accepted') acts = `<button class="btn primary sm" data-oact="pick" data-id="${o.id}">Собрать заказ</button><button class="btn sm" data-oact="ready" data-id="${o.id}">Готов</button><button class="btn sm" data-oact="cancel" data-id="${o.id}">Отменить</button>`;
  if (o.status === 'ready') acts = `<button class="btn primary sm" data-oact="done" data-id="${o.id}">${o.delivery === 'pickup' ? 'Выдан покупателю' : 'Передан курьеру'}</button>`;
  const statusLine = o.status === 'new' ? `<span class="pill bad">Ждёт ответа · ${minsAgo(o.ts)} мин</span>` : o.status === 'accepted' ? `<span class="pill warn">${STATUS.accepted}${o.readyIn ? ' · к ' + hhmm((o.acceptedAt || o.ts) + o.readyIn * 60000) : ''}</span>` : o.status === 'ready' ? `<span class="pill info">${STATUS.ready}</span>` : o.status === 'cancelled' ? `<span class="pill bad">Отменён${o.cancelReason ? ': ' + esc(o.cancelReason) : ''}</span>` : `<span class="pill">${STATUS.done}</span>`;
  return `<article class="order s-${o.status}">
    <div class="row between"><b class="onum num">№ ${o.no}</b><span class="small muted">${whenText(o.ts)}</span></div>
    <div class="row">${statusLine}${src}</div>
    <ul>${o.items.map(itemLine).join('')}</ul>
    <div class="total"><span>Итого</span><span class="num">${total !== orderedTotal(o) ? `<s class="muted">${money(orderedTotal(o))}</s> ` : ''}${money(total)}</span></div>
    ${o.comment ? `<div class="ocomment small">${ICON.note}<span>${esc(o.comment)}</span></div>` : ''}
    ${o.receivedAt ? `<span class="pill">Покупатель получил заказ — деньги ваши</span>` : ''}
    ${o.problem ? `<div class="alert bad small"><span><b>Покупатель сообщил о проблеме:</b> ${esc(o.problem.reason)}${o.problem.text ? ' — ' + esc(o.problem.text) : ''}</span></div>` : ''}
    ${o.customer ? `<div class="who">${esc(o.customer.name)} · ${esc(o.customer.phone)}${o.delivery === 'courier' ? '<br>' + esc(o.customer.address) : ''}</div>` : ''}
    ${acts ? `<div class="acts">${acts}</div>` : ''}
  </article>`;
}
export function orderAction(act, id) {
  const o = S.orders.find(x => x.id === id); if (!o) return;
  if (act === 'accept') return sheetAccept(o);
  if (act === 'cancel') return sheetCancel(o);
  if (act === 'pick') return sheetAssemble(o.id);
  if (act === 'ready') { o.status = 'ready'; toast(`Заказ № ${o.no} готов, курьер уже едет`); }
  if (act === 'done') { o.status = 'done'; toast(`Заказ № ${o.no} выполнен`); }
  save(); render();
}
export function sheetAccept(o) {
  openSheet(`Принять заказ № ${o.no}`, `
    <p style="margin:0">Через сколько минут заказ будет готов? Мы скажем покупателю и вызовем курьера к этому времени.</p>
    <div class="chips wrap">${[10, 15, 20, 30, 45, 60].map(m => `<button class="chip" data-accmin="${m}" data-id="${o.id}" aria-pressed="${m === S.shop.prep}">${m} мин</button>`).join('')}</div>`, '');
}
export function sheetCancel(o) {
  openSheet(`Отменить заказ № ${o.no}`, `
    <p style="margin:0">Укажите причину. Покупатель её увидит, а частые отмены снижают рейтинг магазина.</p>
    <div class="col">${CANCEL_REASONS.map((r, i) => `<label class="check"><input type="radio" name="reason" value="${esc(r)}" ${i === 0 ? 'checked' : ''}> ${esc(r)}</label>`).join('')}</div>`,
    `<span></span><div class="row"><button class="btn" data-act="close">Назад</button><button class="btn danger" data-act="docancel" data-id="${o.id}">Отменить заказ</button></div>`);
}
export function testOrder() {
  const avail = S.products.filter(onSale);
  if (!avail.length) return toast('Нет товаров в наличии для тестового заказа');
  const pick = [...avail].sort(() => Math.random() - 0.5).slice(0, 1 + Math.floor(Math.random() * 3));
  const items = pick.map(p => {
    const v = p.variants[0], opts = (p.options || []).filter(() => Math.random() < 0.5).slice(0, 2);
    return { pid: p.id, name: p.name, unit: p.unit, variant: v ? v.name : '', qty: WEIGHT_UNITS.includes(p.unit) ? 1.5 : 1, opts,
      price: (v ? v.price : p.price) + opts.reduce((s, x) => s + x.price, 0), cost: v ? v.cost : p.cost };
  });
  const o = { id: uid(), no: S.nextNo++, ts: Date.now(), source: 'app', status: 'new', items, customer: { name: 'Тестовый покупатель', phone: '+992 00 000 00 00', address: 'Душанбе, ул. Примерная 1' }, delivery: 'courier', comment: 'Это тестовый заказ', cancelReason: '', pay: 'Наличные', test: true };
  changeStockForOrder(o, -1); S.orders.push(o); ui.ordTab = 'new'; save(); render(); toast('Пришёл новый заказ');
}

// Продажа в магазине
export let cart = null;
onSheetClose(() => { cart = null; });
export function sheetSale() {
  cart = { items: {}, pay: 'Наличные', date: today() };
  drawSale();
}
export function drawSale() {
  const avail = S.products.filter(p => p.active).sort((a, b) => a.name.localeCompare(b.name, 'ru'));
  const lines = [];
  for (const p of avail) {
    const opts = p.variants.length ? p.variants : [null];
    for (const v of opts) {
      const key = p.id + '|' + (v ? v.id : ''), q = cart.items[key] || 0, price = v ? v.price : p.price;
      lines.push(`<div class="sale-line">${thumb(p)}<div style="min-width:0"><div class="pname">${esc(p.name)}${v ? ', ' + esc(v.name) : ''}</div><div class="small muted num">${money(price)} · ост. ${p.stock}</div></div>
        <div class="stepper"><button class="iconbtn" data-cart="${key}" data-d="-1" ${q ? '' : 'disabled'} aria-label="Меньше">−</button><b class="num">${q}</b><button class="iconbtn" data-cart="${key}" data-d="1" aria-label="Больше">+</button></div></div>`);
    }
  }
  const total = cartTotal();
  openSheet('Продажа в магазине', `
    <p class="small muted" style="margin:0">Отметьте, что продали покупателю в магазине. Продажа попадёт в статистику, а остаток уменьшится.</p>
    <div class="grid2"><div class="field"><label for="saleDate">Дата</label><input class="input" type="date" id="saleDate" value="${cart.date}" max="${today()}"></div>
    <div class="field"><label for="salePay">Оплата</label><select class="input" id="salePay">${['Наличные', 'Карта', 'Перевод'].map(x => `<option ${x === cart.pay ? 'selected' : ''}>${x}</option>`).join('')}</select></div></div>
    <div>${lines.join('') || '<div class="muted">Нет активных товаров.</div>'}</div>`,
    `<b class="num" style="font-size:17px">Итого: ${money(total)}</b><div class="row"><button class="btn" data-act="close">Отмена</button><button class="btn primary" data-act="savesale" ${total ? '' : 'disabled'}>Записать продажу</button></div>`, true);
}
export function cartTotal() {
  let s = 0; for (const [key, q] of Object.entries(cart.items)) { const it = cartItem(key, q); if (it) s += it.price * q; } return s;
}
export function cartItem(key, qty) {
  const [pid, vid] = key.split('|'); const p = S.products.find(x => x.id === pid); if (!p) return null;
  const v = vid ? p.variants.find(x => x.id === vid) : null;
  return { pid, name: p.name, variant: v ? v.name : '', qty, price: v ? v.price : p.price, cost: v ? v.cost : p.cost };
}
export function saveSale() {
  const items = Object.entries(cart.items).filter(([, q]) => q > 0).map(([k, q]) => cartItem(k, q)).filter(Boolean);
  if (!items.length) return;
  const ts = cart.date === today() ? Date.now() : parseKey(cart.date).setHours(12, 0);
  const o = { id: uid(), no: S.nextNo++, ts, source: 'shop', status: 'done', items, customer: null, delivery: 'shop', comment: '', cancelReason: '', pay: cart.pay };
  changeStockForOrder(o, -1); S.orders.push(o); save(); closeSheet(); render(); toast(`Продажа на ${money(orderTotal(o))} записана`);
}
