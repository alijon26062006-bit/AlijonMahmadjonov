import { render } from '../app.js';
import { COMPLAINT_REASONS, REPLY_TEMPLATES, REVIEW_BAD, REVIEW_GOOD } from '../config.js';
import { isBad, needsReply, rating, stars, tagStats } from '../domain/reviews.js';
import { esc, plural, uid, whenText } from '../lib/format.js';
import { S, save, ui } from '../state.js';
import { closeSheet, openSheet, toast } from '../ui/dom.js';

// Отзывы
const FILTERS = [['all', 'Все'], ['bad', 'Плохие'], ['noreply', 'Без ответа'], ['text', 'С текстом']];
const pass = { all: () => true, bad: isBad, noreply: needsReply, text: r => !!r.text };

export function vReviews() {
  const R = rating(), all = S.reviews, f = ui.revTab || 'all';
  const list = all.filter(pass[f]).sort((a, b) => b.ts - a.ts);
  const dist = [5, 4, 3, 2, 1].map(n => [n, all.filter(r => r.rating === n).length]);
  const max = Math.max(1, ...dist.map(d => d[1]));
  const good = tagStats(all.filter(r => r.rating >= 4)).filter(([t]) => REVIEW_GOOD.includes(t)).slice(0, 4);
  const bad = tagStats(all.filter(isBad)).filter(([t]) => REVIEW_BAD.includes(t)).slice(0, 4);
  const cnt = k => all.filter(pass[k]).length;
  return `
    <div class="head"><div><div class="eyebrow">${esc(S.shop.name)}</div><h1>Отзывы</h1></div>
      <div class="row"><button class="btn" data-act="testreview">Тестовый отзыв</button></div></div>
    <section class="panel rating-box">
      <div class="rating-big">${R.isNew ? '<b>Новый</b><span class="small muted">магазин</span>' : `<b class="num">${R.value.toLocaleString('ru-RU', { minimumFractionDigits: 1 })}</b><span class="stars">${stars(R.value)}</span>`}
        <span class="small muted">${R.count} ${plural(R.count, 'оценка', 'оценки', 'оценок')} за 3 месяца</span></div>
      <div class="dist">${dist.map(([n, c]) => `<div><span class="num">${n}</span><span class="bar"><i style="width:${c / max * 100}%"></i></span><span class="num muted">${c}</span></div>`).join('')}</div>
    </section>
    ${R.isNew ? `<p class="small muted" style="margin:0">Пока оценок меньше 10, покупатели видят метку «Новый магазин». Рейтинг появится после 10 оценок.</p>` : ''}
    ${good.length || bad.length ? `<div class="grid2">
      ${good.length ? `<section class="panel col" style="gap:8px"><h2>Хвалят за</h2><div class="chips wrap">${good.map(([t, c]) => `<span class="pill">${esc(t)} · ${c}</span>`).join('')}</div></section>` : ''}
      ${bad.length ? `<section class="panel col" style="gap:8px"><h2>Жалуются на</h2><div class="chips wrap">${bad.map(([t, c]) => `<span class="pill bad">${esc(t)} · ${c}</span>`).join('')}</div></section>` : ''}</div>` : ''}
    <div class="seg" role="group" aria-label="Фильтр">${FILTERS.map(([k, t]) => `<button class="chip" data-revtab="${k}" aria-pressed="${f === k}">${t} <b class="num">${cnt(k)}</b></button>`).join('')}</div>
    ${list.length ? `<div class="reviews">${list.slice(0, 60).map(card).join('')}</div>` : `<div class="empty panel"><b>${all.length ? 'Таких отзывов нет' : 'Отзывов пока нет'}</b><span>Покупатель может оценить магазин после того, как получил заказ. Нажмите «Тестовый отзыв», чтобы посмотреть, как это выглядит.</span></div>`}`;
}

function card(r) {
  return `<article class="review ${isBad(r) ? 'is-bad' : ''}">
    <div class="row between"><span><span class="stars">${stars(r.rating)}</span> <b>${esc(r.name)}</b></span><span class="small muted">${whenText(r.ts)} · заказ № ${r.orderNo}</span></div>
    ${r.tags?.length ? `<div class="chips wrap">${r.tags.map(t => `<span class="pill ${REVIEW_BAD.includes(t) ? 'bad' : ''}">${esc(t)}</span>`).join('')}</div>` : ''}
    ${r.text ? `<p>${esc(r.text)}</p>` : ''}
    ${r.items?.length ? `<div class="small muted">${r.items.map(i => `${i.like === true ? '👍' : i.like === false ? '👎' : '·'} ${esc(i.name)}`).join('&nbsp;&nbsp; ')}</div>` : ''}
    ${r.reply ? `<div class="reply"><b>Ваш ответ</b><span>${esc(r.reply)}</span></div>` : ''}
    <div class="row">${r.complaint ? `<span class="pill warn">Жалоба на проверке: ${esc(r.complaint.reason)}</span>` : ''}
      <button class="btn sm ${needsReply(r) ? 'primary' : ''}" data-reply="${r.id}">${r.reply ? 'Изменить ответ' : 'Ответить'}</button>
      ${r.complaint ? '' : `<button class="btn sm" data-complain="${r.id}">Пожаловаться</button>`}</div>
  </article>`;
}

export function sheetReply(id) {
  const r = S.reviews.find(x => x.id === id); if (!r) return;
  const tpl = REPLY_TEMPLATES.filter((_, i) => isBad(r) ? i >= 2 : i < 2);
  openSheet('Ответ на отзыв', `
    <p style="margin:0"><span class="stars">${stars(r.rating)}</span> ${esc(r.name)}${r.text ? ': «' + esc(r.text) + '»' : ''}</p>
    <span class="lbl">Готовые ответы</span>
    <div class="col" style="gap:8px">${tpl.map((t, i) => `<button class="tpl" data-tpl="${i}">${esc(t)}</button>`).join('')}</div>
    <div class="field"><label for="replyText">Ваш ответ</label><textarea class="input" id="replyText" maxlength="500" placeholder="Ответ увидят все покупатели">${esc(r.reply || '')}</textarea></div>
    <span class="small muted">Отвечайте вежливо, даже если покупатель неправ. Другие покупатели читают ответы и выбирают магазин по ним.</span>`,
    `<span></span><div class="row"><button class="btn" data-act="close">Отмена</button><button class="btn primary" data-savereply="${r.id}">Опубликовать</button></div>`);
  document.querySelectorAll('[data-tpl]').forEach(b => b.addEventListener('click', () => { const ta = document.querySelector('#replyText'); ta.value = tpl[+b.dataset.tpl]; ta.focus(); }));
}
export function saveReply(id) {
  const r = S.reviews.find(x => x.id === id), text = document.querySelector('#replyText').value.trim();
  if (!text) return toast('Напишите ответ или выберите готовый');
  r.reply = text; r.replyTs = Date.now(); save(); closeSheet(); render(); toast('Ответ опубликован');
}
export function sheetComplain(id) {
  openSheet('Пожаловаться на отзыв', `
    <p style="margin:0">Отзыв проверит модератор. Если он нарушает правила, его скроют, и он не будет влиять на рейтинг.</p>
    <div class="col">${COMPLAINT_REASONS.map((t, i) => `<label class="check"><input type="radio" name="creason" value="${esc(t)}" ${i ? '' : 'checked'}> ${esc(t)}</label>`).join('')}</div>`,
    `<span></span><div class="row"><button class="btn" data-act="close">Отмена</button><button class="btn primary" data-sendcomplaint="${id}">Отправить</button></div>`);
}
export function sendComplaint(id) {
  const r = S.reviews.find(x => x.id === id);
  r.complaint = { reason: document.querySelector('input[name="creason"]:checked').value, ts: Date.now(), status: 'review' };
  save(); closeSheet(); render(); toast('Жалоба отправлена на проверку');
}

// тестовый отзыв к последнему выполненному заказу из приложения
export function testReview() {
  const o = [...S.orders].reverse().find(x => x.source === 'app' && x.status === 'done' && !S.reviews.some(r => r.orderId === x.id))
    || [...S.orders].reverse().find(x => x.source === 'app');
  if (!o) return toast('Нужен хотя бы один заказ из приложения. Создайте тестовый заказ');
  const bad = Math.random() < 0.4, rate = bad ? 1 + Math.floor(Math.random() * 3) : 4 + Math.round(Math.random());
  const pool = bad ? REVIEW_BAD : REVIEW_GOOD;
  S.reviews.push({ id: uid(), orderId: o.id, orderNo: o.no, ts: Date.now(), name: o.customer?.name || 'Покупатель', rating: rate,
    tags: pool.filter(() => Math.random() < 0.35).slice(0, 2), text: bad ? 'Привезли не совсем то, что заказывала. Надеюсь, исправитесь.' : 'Всё отлично, спасибо!',
    items: o.items.map(i => ({ pid: i.pid, name: i.name, like: !bad || Math.random() < 0.5 })) });
  ui.revTab = 'all'; save(); render(); toast(bad ? 'Пришёл плохой отзыв — ответьте покупателю' : 'Пришёл новый отзыв');
}
