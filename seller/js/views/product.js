import { render } from '../app.js';
import { ATTRS, CUR, kindOf, LABELS, NO_EXPIRY_CATS, PERFUME_BRANDS, WEIGHT_STEPS, WEIGHT_UNITS } from '../config.js';
import { esc, money, num, today, uid } from '../lib/format.js';
import { S, save } from '../state.js';
import { $, closeSheet, ICON, onSheetClose, openSheet, pic, plusI, toast } from '../ui/dom.js';
import { stepLabel } from './catalog.js';

// Карточка товара: четыре шага, как у продавцов на маркетплейсах.
// Черновик живёт в editing.draft, каждый шаг дописывает в него свои поля (syncDraft).
const LAST = 3;
const stepNames = kind => ['Фото и название', kind.id === 'food' ? 'Состав и порция' : 'Характеристики', 'Цена и наличие', kind.expiry ? 'Срок и проверка' : 'Проверка'];
const CONFIRM = {
  grocery: 'Подтверждаю: название, цена, фото и срок годности указаны верно, товар свежий и хранится по правилам',
  perfume: 'Подтверждаю: товар оригинальный, не подделка, бренд, объём, цена и фото указаны верно',
  food: 'Подтверждаю: название, состав, цена и фото указаны верно',
};
const GENDER_BY_CAT = { 'Женская парфюмерия': 'Женский', 'Мужская парфюмерия': 'Мужской', 'Унисекс': 'Унисекс' };

export let editing = null;
onSheetClose(() => { editing = null; });

export function openProduct(id, copyFrom) {
  const src = copyFrom || (id ? S.products.find(x => x.id === id) : null);
  const base = { id: uid(), name: '', cat: S.cats[0] || '', price: null, oldPrice: null, cost: null, stock: 10, unit: kindOf(S.shop).units[0], minStep: 0.5, desc: '', imgs: [], active: true, labels: [], prep: null, variants: [], attrs: {}, expiry: '', created: Date.now() };
  const draft = src ? JSON.parse(JSON.stringify(src)) : base;
  draft.attrs ||= {};
  if (copyFrom) { draft.id = uid(); draft.name = src.name + ' (копия)'; draft.created = Date.now(); draft.variants.forEach(v => { v.id = uid(); }); }
  const isNew = !id || !!copyFrom;
  editing = { isNew, draft, step: 0, reached: isNew ? 0 : LAST, err: {}, bad: new Set(), ok: false, newcat: '' };
  drawProduct();
}

/** «Lattafa · 100 мл · Парфюмерная вода» — строка под названием товара. */
export function attrLine(p) {
  const a = p.attrs || {};
  return [a.brand, a.volume && `${a.volume} мл`, a.ptype, a.pack, a.portion && `${a.portion} г`, a.origin === 'Тестер' || a.origin === 'Разлив' ? a.origin : '', a.gender].filter(Boolean).join(' · ');
}

const field = (k, label, inner, hint = '') => `<div class="field" data-f="${k}"><label for="p_${k}">${label}</label>${inner}${hint ? `<span class="small muted">${hint}</span>` : ''}</div>`;
const money3 = (k, label, v, ph = '0') => field(k, label, `<div class="suffix"><input class="input num" id="p_${k}" name="${k}" inputmode="decimal" value="${v ?? ''}" placeholder="${ph}"><span>${CUR}</span></div>`);

function stepPhoto(d, kind) {
  const ph = d.imgs.map((src, i) => `<div class="ph"><img src="${src}" alt="Фото ${i + 1}">${i === 0 ? '<span class="main">главное</span>' : `<button type="button" class="mk" data-mainph="${i}" title="Сделать главным" aria-label="Сделать главным">${ICON.star}</button>`}<button type="button" data-rmph="${i}" aria-label="Удалить фото">${ICON.close}</button></div>`).join('');
  const ex = { grocery: 'Например, Молоко Шароб 3,2% 1 л', perfume: 'Например, Lattafa Khamrah', food: 'Например, Плов праздничный' }[kind.id];
  return `
    <div class="field"><span class="lbl">Фото товара, до 4 штук</span><div class="photos">${ph}${d.imgs.length < 4 ? `<label class="ph" for="pFile">+ Добавить фото</label>` : ''}</div><input type="file" id="pFile" accept="image/*" multiple hidden>
      <span class="small muted">${d.imgs.length ? 'Первое фото — главное, его видно в каталоге.' : 'Снимайте при дневном свете на светлом фоне: товар целиком, потом упаковку и этикетку.'}</span></div>
    ${field('name', 'Название *', `<input class="input" id="p_name" name="name" value="${esc(d.name)}" maxlength="80" placeholder="${ex}">`, 'Как товар называется на упаковке, без слов «акция» и «лучший».')}
    <div class="field" data-f="newcat"><label for="p_cat">Категория</label><select class="input" id="p_cat" name="cat">${S.cats.map(c => `<option ${c === d.cat ? 'selected' : ''}>${esc(c)}</option>`).join('')}<option value="__new" ${d.cat === '__new' ? 'selected' : ''}>+ Новая категория…</option></select>
      <input class="input" id="p_newcat" name="newcat" placeholder="Название категории" ${d.cat === '__new' ? '' : 'hidden'} maxlength="30" value="${esc(editing.newcat)}"></div>`;
}

function stepAttrs(d, kind) {
  const brands = [...new Set([...(kind.id === 'perfume' ? PERFUME_BRANDS : []), ...S.products.map(p => p.attrs?.brand).filter(Boolean)])].sort((a, b) => a.localeCompare(b));
  const rows = (ATTRS[kind.id] || []).map(a => {
    const v = d.attrs[a.k] || '', label = a.label + (a.req ? ' *' : '');
    if (a.opts) return `<div class="field" data-f="a_${a.k}"><span class="lbl">${label}</span><div class="chips wrap" role="radiogroup" aria-label="${a.label}">${a.opts.map(o => `<label class="chip unit-chip"><input type="radio" name="a_${a.k}" value="${o}" ${o === v ? 'checked' : ''}>${o}</label>`).join('')}</div></div>`;
    const chips = a.chips ? `<div class="chips wrap">${a.chips.map(c => `<button type="button" class="chip" data-pfill="p_a_${a.k}" data-v="${c}">${c}</button>`).join('')}</div>` : '';
    return field(`a_${a.k}`, label, `<input class="input" id="p_a_${a.k}" name="a_${a.k}" value="${esc(v)}" placeholder="${a.ph || ''}" ${a.numeric ? 'inputmode="numeric"' : ''} ${a.list ? 'list="brandList" autocomplete="off"' : ''} maxlength="60">${chips}`);
  }).join('');
  const descPh = { grocery: 'Состав, жирность, условия хранения', perfume: 'Ноты аромата: верхние, сердце, база. Стойкость, сезон', food: 'Состав блюда, с чем подаётся' }[kind.id];
  return `${rows}
    <datalist id="brandList">${brands.map(b => `<option value="${esc(b)}">`).join('')}</datalist>
    ${field('desc', 'Описание', `<textarea class="input" id="p_desc" name="desc" maxlength="600" placeholder="${descPh}">${esc(d.desc)}</textarea>`)}`;
}

function stepPrice(d, kind) {
  const units = [...new Set([...kind.units, d.unit])];
  const weight = WEIGHT_UNITS.includes(d.unit);
  return `
    <div class="field"><span class="lbl">Продаю в</span><div class="chips wrap" role="radiogroup" aria-label="Единица">${units.map(u => `<label class="chip unit-chip"><input type="radio" name="unit" value="${u}" ${u === d.unit ? 'checked' : ''}>${u}</label>`).join('')}</div></div>
    ${weight ? `<div class="field"><span class="lbl">Покупатель может взять от</span><div class="chips wrap" role="radiogroup" aria-label="Минимальное количество">${WEIGHT_STEPS.map(s => `<label class="chip unit-chip"><input type="radio" name="minStep" value="${s}" ${s === (d.minStep ?? 0.5) ? 'checked' : ''}>${stepLabel(s, d.unit)}</label>`).join('')}</div></div>` : ''}
    <div class="grid3">
      ${money3('price', weight ? `Цена за 1 ${esc(d.unit)} *` : `Цена${d.unit === 'мл' ? ' за 1 мл' : ''} *`, d.price)}
      ${money3('cost', 'Закупочная цена', d.cost)}
      ${money3('oldPrice', 'Цена до скидки', d.oldPrice, '—')}
    </div>
    <div class="hintline" id="marginLine"></div>
    ${field('stock', 'Сколько есть сейчас', `<div class="suffix"><input class="input num" id="p_stock" name="stock" inputmode="${weight ? 'decimal' : 'numeric'}" value="${d.stock ?? ''}"><span>${esc(d.unit)}</span></div>`)}
    <details class="more" ${d.variants.length ? 'open' : ''} data-f="variants"><summary>Варианты товара ${d.variants.length ? `(${d.variants.length})` : ''}</summary>
      <div class="col">
        <span class="small muted">${kind.id === 'perfume' ? 'Например, один аромат в объёмах 30, 50 и 100 мл.' : 'Например, яйца по 10 или 30 штук, плов на одного или на компанию.'} У каждого варианта своя цена.</span>
        <div class="variants" id="variants">${d.variants.map(v => variantRow(v)).join('')}</div>
        <div><button type="button" class="btn sm" data-act="addvar">${plusI} Добавить вариант</button></div>
      </div></details>
    <div class="field"><span class="lbl">Метки на карточке</span><div class="chips wrap">${LABELS.map(l => `<label class="chip" style="cursor:pointer"><input type="checkbox" name="label" value="${esc(l)}" ${d.labels.includes(l) ? 'checked' : ''} style="accent-color:var(--accent);margin:0 6px 0 0;vertical-align:-2px">${esc(l)}</label>`).join('')}</div></div>`;
}

function stepCheck(d, kind) {
  const need = kind.expiry === 'required' && !NO_EXPIRY_CATS.includes(d.cat);
  const exp = kind.expiry ? field('expiry', `Годен до${need ? ' *' : ''}`, `<input class="input num" id="p_expiry" name="expiry" type="date" min="${today()}" value="${d.expiry || ''}">`,
    need ? 'Дата с упаковки ближайшей партии. Когда срок истечёт, товар сам скроется из продажи.' : kind.expiry === 'required' ? 'Для свежих овощей и фруктов можно не указывать.' : 'Если на упаковке есть срок, укажите его.') : '';
  const tips = [!d.imgs.length && 'Нет фото — такие товары покупают в разы реже', !d.desc.trim() && 'Нет описания — покупателю сложнее выбрать', d.cost == null && 'Нет закупочной цены — статистика не посчитает прибыль'].filter(Boolean);
  const from = d.variants.length ? Math.min(...d.variants.map(v => v.price || Infinity)) : d.price;
  const card = `<article class="card"><div class="pic">${pic(d)}${d.oldPrice && d.price ? `<div class="tags"><span class="sale">−${Math.round((1 - d.price / d.oldPrice) * 100)}%</span></div>` : ''}</div><div class="body"><div class="t">${esc(d.name || 'Без названия')}</div>${attrLine(d) ? `<div class="d">${esc(attrLine(d))}</div>` : ''}<div class="pr"><div><b class="num">${d.variants.length ? 'от ' : ''}${money(from || 0)}</b>${d.oldPrice ? `<s class="num">${money(d.oldPrice)}</s>` : ''}</div><span class="add" aria-hidden="true">+</span></div></div></article>`;
  return `${exp}
    <div class="field"><span class="lbl">Так товар увидит покупатель</span><div class="cards preview-one">${card}</div></div>
    ${tips.length ? `<ul class="tips">${tips.map(t => `<li>${t}</li>`).join('')}</ul>` : ''}
    <details class="more" ${d.prep ? 'open' : ''}><summary>Время сборки</summary>
      ${field('prep', 'Сколько минут собирать этот товар', `<div class="suffix"><input class="input num" id="p_prep" name="prep" inputmode="numeric" value="${d.prep ?? ''}" placeholder="${S.shop.prep} (как у магазина)"><span>мин</span></div>`)}</details>
    <label class="switch" for="p_active"><span><b style="font-weight:600">Показывать покупателям</b><br><span class="small muted">Выключите, чтобы временно скрыть товар</span></span><input type="checkbox" id="p_active" name="active" ${d.active ? 'checked' : ''}></label>
    <div data-f="confirm"><label class="agree confirm"><input type="checkbox" id="p_ok" name="confirm" ${editing.ok ? 'checked' : ''}> <span>${CONFIRM[kind.id]}</span></label></div>`;
}

export function drawProduct() {
  const { draft: d, step, isNew } = editing, kind = kindOf(S.shop), names = stepNames(kind);
  const body = [stepPhoto, stepAttrs, stepPrice, stepCheck][step](d, kind);
  const tabs = `<div class="wiz-prog" aria-hidden="true">${names.map((_, i) => `<i class="${i <= step ? 'on' : ''}"></i>`).join('')}</div>
    <div class="ptabs" role="tablist" aria-label="Шаги">${names.map((t, i) => `<button type="button" role="tab" class="ptab" data-pstep="${i}" aria-selected="${i === step}" ${i > editing.reached ? 'disabled' : ''}><b>${i + 1}</b> ${t}</button>`).join('')}</div>`;
  const back = step ? '<button class="btn" data-pnav="-1">Назад</button>' : '<button class="btn" data-act="close">Отмена</button>';
  const fwd = step < LAST ? `<button class="btn ${isNew ? 'primary' : ''}" data-pnav="1">Далее</button>` : '';
  const saveBtn = step === LAST || !isNew ? `<button class="btn primary" data-act="saveP">${isNew ? 'Добавить товар' : 'Сохранить'}</button>` : '';
  openSheet(isNew ? 'Новый товар' : 'Изменить товар', `${tabs}<form id="pForm" class="col" novalidate style="gap:16px">${body}<button type="submit" hidden></button></form>`,
    `<div class="row">${isNew ? '' : `<button class="btn danger" data-act="delete">Удалить</button><button class="btn" data-act="dup">Копия</button>`}</div><div class="row">${back}${fwd}${saveBtn}</div>`);
  markErrors(editing.err);
  if (step === 2) updateMargin();
}

function markErrors(errs) {
  for (const [k, m] of Object.entries(errs)) {
    const box = document.querySelector(`#pForm [data-f="${k}"]`); if (!box) continue;
    box.querySelectorAll('.input').forEach(el => el.classList.add('invalid'));
    box.insertAdjacentHTML('beforeend', `<span class="err">${m}</span>`);
    if (box.tagName === 'DETAILS') box.open = true;
  }
  const first = document.querySelector('#pForm .invalid, #pForm .err');
  if (first) { first.scrollIntoView({ block: 'center' }); if (first.matches('.input')) first.focus(); }
}

export const variantRow = v => `<div class="variant" data-vid="${v.id}"><input class="input vn" placeholder="${kindOf(S.shop).id === 'perfume' ? 'Например, 50 мл' : 'Название, напр. 30 шт'}" value="${esc(v.name)}" aria-label="Название варианта"><div class="suffix"><input class="input num vp" inputmode="decimal" placeholder="Цена" value="${v.price ?? ''}" aria-label="Цена варианта"><span>${CUR}</span></div><div class="suffix"><input class="input num vc" inputmode="decimal" placeholder="Закупка" value="${v.cost ?? ''}" aria-label="Закупочная цена варианта"><span>${CUR}</span></div><button type="button" class="iconbtn" data-rmvar="${v.id}" aria-label="Удалить вариант">${ICON.close}</button></div>`;
export function readVariants() {
  return [...document.querySelectorAll('#variants .variant')].map(el => ({ id: el.dataset.vid, name: el.querySelector('.vn').value.trim(), price: num(el.querySelector('.vp').value), cost: el.querySelector('.vc').value.trim() === '' ? null : num(el.querySelector('.vc').value) }));
}

/** Переносит поля текущего шага в черновик (перед перерисовкой, переходом или сохранением). */
export function syncDraft() {
  const f = $('#pForm'); if (!f || !editing) return;
  const d = editing.draft, el = f.elements, has = k => el[k] != null, val = k => (el[k].value ?? '').trim();
  const number = k => { const raw = val(k), n = num(raw); editing.bad[raw && n == null ? 'add' : 'delete'](k); return raw === '' ? null : n; };
  if (has('name')) d.name = val('name');
  if (has('cat')) { d.cat = val('cat'); editing.newcat = val('newcat'); }
  for (const a of ATTRS[kindOf(S.shop).id] || []) if (has('a_' + a.k)) d.attrs[a.k] = val('a_' + a.k);
  if (has('desc')) d.desc = val('desc');
  if (has('unit')) d.unit = val('unit') || d.unit;
  if (has('minStep')) d.minStep = num(val('minStep')) ?? d.minStep;
  if (has('price')) { d.price = number('price'); d.cost = number('cost'); d.oldPrice = number('oldPrice'); d.stock = number('stock'); }
  if (has('label')) d.labels = [...f.querySelectorAll('[name="label"]:checked')].map(x => x.value);
  if ($('#variants')) d.variants = readVariants();
  if (has('expiry')) d.expiry = val('expiry');
  if (has('prep')) d.prep = number('prep');
  if (has('active')) d.active = el.active.checked;
  if (has('confirm')) editing.ok = el.confirm.checked;
}

function check(step) {
  const d = editing.draft, kind = kindOf(S.shop), e = {}, bad = k => editing.bad.has(k);
  if (step === 0) {
    if (!d.name) e.name = 'Введите название';
    if (d.cat === '__new' && !editing.newcat) e.newcat = 'Введите категорию';
  }
  if (step === 1) for (const a of ATTRS[kind.id] || []) {
    const v = d.attrs[a.k] || '';
    if (a.req && !v) e['a_' + a.k] = a.opts ? 'Выберите вариант' : 'Заполните поле';
    else if (a.numeric && v && !(num(v) > 0)) e['a_' + a.k] = 'Только число';
  }
  if (step === 2) {
    if (d.price == null || d.price <= 0) e.price = 'Цена больше нуля';
    if (bad('cost') || (d.cost != null && d.cost < 0)) e.cost = 'Число от нуля';
    if (bad('oldPrice') || (d.oldPrice != null && (d.price == null || d.oldPrice <= d.price))) e.oldPrice = 'Должна быть больше цены';
    const w = WEIGHT_UNITS.includes(d.unit);
    if (d.stock == null || d.stock < 0 || (!w && !Number.isInteger(d.stock))) e.stock = w ? 'Число от 0, например 12,5' : 'Целое число от 0';
    if (d.variants.some(v => !v.name || v.price == null || v.price <= 0)) e.variants = 'У каждого варианта нужны название и цена';
  }
  if (step === 3) {
    const cat = d.cat === '__new' ? editing.newcat : d.cat;
    if (kind.expiry === 'required' && !d.expiry && !NO_EXPIRY_CATS.includes(cat)) e.expiry = 'Укажите срок годности с упаковки';
    if (d.expiry && d.expiry < today()) e.expiry = 'Срок уже истёк — такой товар продавать нельзя';
    if (bad('prep') || (d.prep != null && (d.prep <= 0 || d.prep > 600))) e.prep = 'От 1 до 600 минут';
    if (!editing.ok) e.confirm = 'Отметьте, что всё указано верно';
  }
  return e;
}

// подсказки при переходе дальше: бренд из названия, пол из категории, разлив — в миллилитрах
function autofill() {
  const d = editing.draft, kind = kindOf(S.shop), a = d.attrs;
  if (!a.brand && kind.id !== 'food') {
    const known = [...PERFUME_BRANDS, ...S.products.map(p => p.attrs?.brand).filter(Boolean)].sort((x, y) => y.length - x.length);
    const hit = known.find(b => d.name.toLowerCase().startsWith(b.toLowerCase() + ' ') || d.name.toLowerCase() === b.toLowerCase());
    if (hit) a.brand = hit;
  }
  if (kind.id === 'perfume') {
    if (!a.gender && GENDER_BY_CAT[d.cat]) a.gender = GENDER_BY_CAT[d.cat];
    if (!a.origin && d.cat === 'Парфюм на разлив') a.origin = 'Разлив';
    if (editing.isNew && a.origin === 'Разлив' && d.unit === 'шт') d.unit = 'мл';
  }
}

function goStep(to) {
  syncDraft();
  // вперёд можно, только если текущий шаг заполнен
  for (let s = editing.step; s < to; s++) { const e = check(s); if (Object.keys(e).length) { editing.step = s; editing.err = e; return drawProduct(); } }
  if (to > editing.step) autofill();
  editing.step = to; editing.reached = Math.max(editing.reached, to); editing.err = {};
  drawProduct(); document.querySelector('.sheet-body').scrollTop = 0;
}

export function submitProduct() { return editing.step < LAST ? goStep(editing.step + 1) : saveProduct(); }

export function saveProduct() {
  syncDraft();
  for (let s = 0; s <= LAST; s++) {
    const e = check(s);
    if (Object.keys(e).length) { editing.step = s; editing.reached = Math.max(editing.reached, s); editing.err = e; return drawProduct(); }
  }
  const d = editing.draft, kind = kindOf(S.shop);
  if (d.cat === '__new') { d.cat = editing.newcat; if (!S.cats.includes(d.cat)) S.cats.push(d.cat); }
  if (WEIGHT_UNITS.includes(d.unit)) d.stock = Math.round(d.stock * 1000) / 1000; else d.minStep = 1;
  if (!kind.expiry) d.expiry = '';
  d.checkedAt = Date.now();
  // если есть варианты, цена товара = самая низкая цена варианта
  if (d.variants.length) { const min = d.variants.reduce((a, b) => a.price <= b.price ? a : b); d.price = min.price; if (min.cost != null) d.cost = min.cost; }
  const i = S.products.findIndex(p => p.id === d.id);
  if (i < 0) S.products.push(d); else S.products[i] = d;
  const wasNew = editing.isNew; save(); closeSheet(); render(); toast(wasNew ? 'Товар добавлен' : 'Изменения сохранены');
}

export function updateMargin() {
  const el = $('#marginLine'); if (!el) return;
  const pr = num($('#p_price').value), co = num($('#p_cost').value), old = num($('#p_oldPrice').value);
  const parts = [];
  if (pr != null && co != null && pr > 0) { const m = pr - co; parts.push(`Прибыль с одной продажи: <b class="num ${m < 0 ? 'neg' : ''}">${money(m)}</b> (${Math.round(m / pr * 100)}% от цены)`); }
  else parts.push('Укажите закупочную цену, и статистика покажет настоящую прибыль.');
  if (old != null && pr != null && old > pr) parts.push(`Скидка для покупателя: <b class="num">−${Math.round((1 - pr / old) * 100)}%</b>`);
  el.innerHTML = parts.join('<br>');
}

document.addEventListener('click', e => {
  const t = e.target.closest('[data-pstep],[data-pnav],[data-pfill]'); if (!t || !editing || t.disabled) return;
  if (t.dataset.pstep) return goStep(+t.dataset.pstep);
  if (t.dataset.pnav) return goStep(editing.step + +t.dataset.pnav);
  const inp = $('#' + t.dataset.pfill); if (inp) { inp.value = t.dataset.v; inp.focus(); }
});
// исправил поле — подсветка ошибки уходит сразу
for (const type of ['input', 'change']) document.addEventListener(type, e => {
  const box = editing && e.target.closest('#pForm [data-f]'); if (!box) return;
  box.querySelectorAll('.invalid').forEach(el => el.classList.remove('invalid'));
  box.querySelectorAll(':scope > .err').forEach(el => el.remove());
  delete editing.err[box.dataset.f];
});
