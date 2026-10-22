import { render } from '../app.js';
import { CUR, LABELS, LOW, UNITS } from '../config.js';
import { prodSales, ZERO } from '../domain/analytics.js';
import { addDays, esc, money, num, today, uid } from '../lib/format.js';
import { S, save, ui } from '../state.js';
import { $, closeSheet, onSheetClose, ICON, openSheet, plusI, showErrors, stockPill, thumb, toast } from '../ui/dom.js';

// Товары
export function filtered(sales) {
  const q = ui.q.trim().toLowerCase();
  const by = { sales: (a, b) => (sales[b.id] || ZERO).qty - (sales[a.id] || ZERO).qty, new: (a, b) => b.created - a.created, cheap: (a, b) => a.price - b.price, stock: (a, b) => a.stock - b.stock }[ui.psort];
  return S.products.filter(p =>
    (ui.cat === 'Все' || p.cat === ui.cat) && (!q || p.name.toLowerCase().includes(q)) &&
    (ui.stock === 'all' || (ui.stock === 'low' && p.active && p.stock <= LOW) || (ui.stock === 'hidden' && !p.active) || (ui.stock === 'nophoto' && !p.imgs.length) || (ui.stock === 'sale' && p.oldPrice))
  ).sort(by);
}
export function vCatalog() {
  const sales = prodSales(addDays(today(), -29), today());
  const list = filtered(sales);
  const cats = ['Все', ...S.cats.filter(c => S.products.some(p => p.cat === c))];
  const cnt = f => S.products.filter(f).length;
  const rows = list.map(p => {
    const from = p.variants.length ? Math.min(...p.variants.map(v => v.price)) : p.price;
    return `<div class="prow">
      <button class="open" data-edit="${p.id}">${thumb(p)}<div style="min-width:0"><div class="pname">${esc(p.name)}</div><div class="pmeta"><span>${esc(p.cat || 'Без категории')}</span><span class="pill ${(sales[p.id] || ZERO).qty ? 'info' : 'off'}">Продано за 30 дн: ${(sales[p.id] || ZERO).qty}</span>${stockPill(p)}${p.oldPrice ? '<span class="pill bad">Скидка</span>' : ''}${p.labels.map(l => `<span class="pill off">${esc(l)}</span>`).join('')}${p.variants.length ? `<span class="pill off">${p.variants.length} вар.</span>` : ''}${p.imgs.length ? '' : '<span class="pill warn">Нет фото</span>'}</div></div></button>
      <div class="stepper" title="Остаток"><button class="iconbtn" data-stock="${p.id}" data-d="-1" aria-label="Уменьшить остаток">−</button><b class="num">${p.stock}</b><button class="iconbtn" data-stock="${p.id}" data-d="1" aria-label="Увеличить остаток">+</button></div>
      <div class="price num">${p.variants.length ? 'от ' : ''}${money(from)}${p.oldPrice ? `<s>${money(p.oldPrice)}</s>` : `<small>за ${esc(p.unit)}</small>`}</div>
    </div>`;
  }).join('');
  const empty = S.products.length === 0
    ? `<div class="empty panel"><b>Пока нет ни одного товара</b><span>Добавьте первый товар или загрузите сразу весь список из Excel.</span><div class="row" style="justify-content:center"><button class="btn primary" data-act="add">${plusI} Добавить товар</button><button class="btn" data-act="import">${ICON.import} Загрузить из Excel</button></div></div>`
    : `<div class="empty panel"><b>Ничего не нашлось</b><span>Измените поиск или фильтр.</span></div>`;
  return `
    <div class="head"><div><div class="eyebrow">${esc(S.shop.name)}</div><h1>Товары <span class="num" style="color:var(--muted);font-weight:500">${S.products.length}</span></h1></div>
      <div class="row"><button class="btn" data-act="import">${ICON.import} Из Excel</button><button class="btn" data-act="export">Копировать список</button><button class="btn primary" data-act="add">${plusI} Добавить товар</button></div></div>
    <div class="toolbar">
      <div class="search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input class="input" id="q" type="search" placeholder="Поиск по названию" value="${esc(ui.q)}" aria-label="Поиск"></div>
      <select class="input" id="stockFilter" style="width:auto" aria-label="Фильтр">
        <option value="all">Все товары</option>
        <option value="low" ${ui.stock === 'low' ? 'selected' : ''}>Заканчиваются (${cnt(p => p.active && p.stock <= LOW)})</option>
        <option value="nophoto" ${ui.stock === 'nophoto' ? 'selected' : ''}>Без фото (${cnt(p => !p.imgs.length)})</option>
        <option value="sale" ${ui.stock === 'sale' ? 'selected' : ''}>Со скидкой (${cnt(p => p.oldPrice)})</option>
        <option value="hidden" ${ui.stock === 'hidden' ? 'selected' : ''}>Скрытые (${cnt(p => !p.active)})</option>
      </select>
      <select class="input" id="psort" style="width:auto" aria-label="Сортировка">
        <option value="sales" ${ui.psort === 'sales' ? 'selected' : ''}>Сначала самые продаваемые</option>
        <option value="new" ${ui.psort === 'new' ? 'selected' : ''}>Сначала новые</option>
        <option value="cheap" ${ui.psort === 'cheap' ? 'selected' : ''}>Сначала дешёвые</option>
        <option value="stock" ${ui.psort === 'stock' ? 'selected' : ''}>Меньше всего на складе</option>
      </select>
    </div>
    ${cats.length > 2 ? `<div class="chips" role="group" aria-label="Категории">${cats.map(c => `<button class="chip" data-cat="${esc(c)}" aria-pressed="${ui.cat === c}">${esc(c)}</button>`).join('')}</div>` : ''}
    ${list.length ? `<div class="plist">${rows}</div>` : empty}`;
}

// ----- карточка товара -----
export let editing = null;
onSheetClose(() => { editing = null; });
export function openProduct(id, copyFrom) {
  const src = copyFrom || (id ? S.products.find(x => x.id === id) : null);
  const base = { id: uid(), name: '', cat: S.cats[0] || '', price: null, oldPrice: null, cost: null, stock: 10, unit: 'шт', desc: '', imgs: [], active: true, labels: [], prep: null, variants: [], created: Date.now() };
  const draft = src ? JSON.parse(JSON.stringify(src)) : base;
  if (copyFrom) { draft.id = uid(); draft.name = src.name + ' (копия)'; draft.created = Date.now(); draft.variants.forEach(v => { v.id = uid(); }); }
  editing = { isNew: !id || !!copyFrom, draft };
  drawProduct();
}
export function drawProduct() {
  const d = editing.draft;
  const ph = d.imgs.map((src, i) => `<div class="ph"><img src="${src}" alt="Фото ${i + 1}">${i === 0 ? '<span class="main">главное</span>' : `<button type="button" class="mk" data-mainph="${i}" title="Сделать главным" aria-label="Сделать главным">${ICON.star}</button>`}<button type="button" data-rmph="${i}" aria-label="Удалить фото">${ICON.close}</button></div>`).join('');
  openSheet(editing.isNew ? 'Новый товар' : 'Изменить товар', `
    <div class="field"><span class="lbl">Фото, до 4 штук</span><div class="photos">${ph}${d.imgs.length < 4 ? `<label class="ph" for="pFile">+ Добавить фото</label>` : ''}</div><input type="file" id="pFile" accept="image/*" multiple hidden>
      ${d.imgs.length ? '' : '<span class="small muted">Товары с фото покупают в несколько раз чаще. Снимайте при дневном свете на светлом фоне.</span>'}</div>
    <form id="pForm" class="col" novalidate style="gap:16px">
      <div class="field"><label for="p_name">Название *</label><input class="input" id="p_name" name="name" value="${esc(d.name)}" maxlength="80" placeholder="Например, Букет из 15 роз"></div>
      <div class="grid2">
        <div class="field"><label for="p_cat">Категория</label><select class="input" id="p_cat" name="cat">${S.cats.map(c => `<option ${c === d.cat ? 'selected' : ''}>${esc(c)}</option>`).join('')}<option value="__new">+ Новая категория…</option></select>
          <input class="input" id="p_newcat" name="newcat" placeholder="Название категории" hidden maxlength="30"></div>
        <div class="field"><label for="p_stock">Остаток</label><div style="display:flex;gap:6px"><input class="input num" id="p_stock" name="stock" inputmode="numeric" value="${d.stock}" style="min-width:0"><select class="input" name="unit" aria-label="Единица" style="width:auto;padding-inline:8px">${UNITS.map(u => `<option ${u === d.unit ? 'selected' : ''}>${u}</option>`).join('')}</select></div></div>
      </div>
      <div class="grid3">
        <div class="field"><label for="p_price">Цена продажи *</label><div class="suffix"><input class="input num" id="p_price" name="price" inputmode="decimal" value="${d.price ?? ''}" placeholder="0"><span>${CUR}</span></div></div>
        <div class="field"><label for="p_cost">Закупочная цена</label><div class="suffix"><input class="input num" id="p_cost" name="cost" inputmode="decimal" value="${d.cost ?? ''}" placeholder="0"><span>${CUR}</span></div></div>
        <div class="field"><label for="p_old">Цена до скидки</label><div class="suffix"><input class="input num" id="p_old" name="oldPrice" inputmode="decimal" value="${d.oldPrice ?? ''}" placeholder="—"><span>${CUR}</span></div></div>
      </div>
      <div class="hintline" id="marginLine"></div>
      <div class="field"><label for="p_desc">Описание</label><textarea class="input" id="p_desc" name="desc" maxlength="400" placeholder="Состав, размер, срок свежести: что важно знать покупателю">${esc(d.desc)}</textarea></div>
      <div class="field"><span class="lbl">Метки на карточке</span><div class="chips wrap">${LABELS.map(l => `<label class="chip" style="cursor:pointer"><input type="checkbox" name="label" value="${esc(l)}" ${d.labels.includes(l) ? 'checked' : ''} style="accent-color:var(--accent);margin:0 6px 0 0;vertical-align:-2px">${esc(l)}</label>`).join('')}</div></div>
      <details class="more" ${d.variants.length ? 'open' : ''}><summary>Варианты товара ${d.variants.length ? `(${d.variants.length})` : ''}</summary>
        <div class="col">
          <span class="small muted">Например, букет из 15, 25 или 51 розы, или размер S/M/L. У каждого варианта своя цена. Если варианты есть, покупатель выбирает один из них.</span>
          <div class="variants" id="variants">${d.variants.map(v => variantRow(v)).join('')}</div>
          <div><button type="button" class="btn sm" data-act="addvar">${plusI} Добавить вариант</button></div>
        </div></details>
      <details class="more" ${d.prep ? 'open' : ''}><summary>Время сборки</summary>
        <div class="field"><label for="p_prep">Сколько минут собирать этот товар</label><div class="suffix"><input class="input num" id="p_prep" name="prep" inputmode="numeric" value="${d.prep ?? ''}" placeholder="${S.shop.prep} (как у магазина)"><span>мин</span></div></div></details>
      <label class="switch" for="p_active"><span><b style="font-weight:600">Показывать покупателям</b><br><span class="small muted">Выключите, чтобы временно скрыть товар</span></span><input type="checkbox" id="p_active" name="active" ${d.active ? 'checked' : ''}></label>
      <button type="submit" hidden></button>
    </form>`,
    `<div class="row">${editing.isNew ? '' : `<button class="btn danger" data-act="delete">Удалить</button><button class="btn" data-act="dup">Копия</button>`}</div>
     <div class="row"><button class="btn" data-act="close">Отмена</button><button class="btn primary" data-act="saveP">${editing.isNew ? 'Добавить товар' : 'Сохранить'}</button></div>`);
  updateMargin();
}
export const variantRow = v => `<div class="variant" data-vid="${v.id}"><input class="input vn" placeholder="Название, напр. 25 роз" value="${esc(v.name)}" aria-label="Название варианта"><div class="suffix"><input class="input num vp" inputmode="decimal" placeholder="Цена" value="${v.price ?? ''}" aria-label="Цена варианта"><span>${CUR}</span></div><div class="suffix"><input class="input num vc" inputmode="decimal" placeholder="Закупка" value="${v.cost ?? ''}" aria-label="Закупочная цена варианта"><span>${CUR}</span></div><button type="button" class="iconbtn" data-rmvar="${v.id}" aria-label="Удалить вариант">${ICON.close}</button></div>`;
export function readVariants() {
  return [...document.querySelectorAll('#variants .variant')].map(el => ({ id: el.dataset.vid, name: el.querySelector('.vn').value.trim(), price: num(el.querySelector('.vp').value), cost: el.querySelector('.vc').value.trim() === '' ? null : num(el.querySelector('.vc').value) }));
}
export function syncDraft() {
  // сохраняем введённое перед перерисовкой (добавили фото или вариант)
  const f = $('#pForm'); if (!f || !editing) return;
  const fd = new FormData(f), d = editing.draft;
  d.name = fd.get('name'); d.cat = fd.get('cat') === '__new' ? d.cat : fd.get('cat'); d.stock = num(fd.get('stock')) ?? d.stock; d.unit = fd.get('unit');
  d.price = num(fd.get('price')); d.cost = num(fd.get('cost')); d.oldPrice = num(fd.get('oldPrice')); d.desc = fd.get('desc');
  d.labels = fd.getAll('label'); d.prep = num(fd.get('prep')); d.active = !!fd.get('active'); d.variants = readVariants();
}
export function updateMargin() {
  const el = $('#marginLine'); if (!el) return;
  const pr = num($('#p_price').value), co = num($('#p_cost').value), old = num($('#p_old').value);
  const parts = [];
  if (pr != null && co != null && pr > 0) { const m = pr - co; parts.push(`Прибыль с одной продажи: <b class="num ${m < 0 ? 'neg' : ''}">${money(m)}</b> (${Math.round(m / pr * 100)}% от цены)`); }
  else parts.push('Укажите закупочную цену, и статистика покажет настоящую прибыль.');
  if (old != null && pr != null && old > pr) parts.push(`Скидка для покупателя: <b class="num">−${Math.round((1 - pr / old) * 100)}%</b>`);
  el.innerHTML = parts.join('<br>');
}
export function saveProduct() {
  const f = $('#pForm'), fd = new FormData(f), errs = {};
  const price = num(fd.get('price')), costRaw = fd.get('cost').trim(), cost = costRaw === '' ? null : num(costRaw), oldRaw = fd.get('oldPrice').trim(), old = oldRaw === '' ? null : num(oldRaw), stock = num(fd.get('stock')), prepRaw = fd.get('prep').trim(), prep = prepRaw === '' ? null : num(prepRaw);
  if (!fd.get('name').trim()) errs.name = 'Введите название';
  if (price == null || price <= 0) errs.price = 'Цена больше нуля';
  if (costRaw && (cost == null || cost < 0)) errs.cost = 'Число от нуля';
  if (oldRaw && (old == null || price == null || old <= price)) errs.oldPrice = 'Должна быть больше цены';
  if (stock == null || stock < 0 || !Number.isInteger(stock)) errs.stock = 'Целое число от 0';
  if (prepRaw && (prep == null || prep <= 0 || prep > 600)) errs.prep = 'От 1 до 600 минут';
  let cat = fd.get('cat');
  if (cat === '__new') { cat = (fd.get('newcat') || '').trim(); if (!cat) errs.newcat = 'Введите категорию'; }
  const variants = readVariants();
  let vErr = '';
  variants.forEach((v, i) => { const el = document.querySelectorAll('#variants .variant')[i]; el.querySelectorAll('.input').forEach(x => x.classList.remove('invalid'));
    if (!v.name) { el.querySelector('.vn').classList.add('invalid'); vErr = 'У каждого варианта нужны название и цена'; }
    if (v.price == null || v.price <= 0) { el.querySelector('.vp').classList.add('invalid'); vErr = 'У каждого варианта нужны название и цена'; } });
  const ok = showErrors(f, errs);
  f.querySelector('#varErr')?.remove();
  if (vErr) { $('#variants').insertAdjacentHTML('afterend', `<span class="err" id="varErr">${vErr}</span>`); f.querySelector('details.more').open = true; }
  if (!ok || vErr) return;
  if (!S.cats.includes(cat)) S.cats.push(cat);
  const d = editing.draft;
  Object.assign(d, { name: fd.get('name').trim(), cat, price, cost, oldPrice: old, stock, unit: fd.get('unit'), desc: fd.get('desc').trim(), labels: fd.getAll('label'), prep, active: !!fd.get('active'), variants });
  // если есть варианты, цена товара = самая низкая цена варианта
  if (variants.length) { const min = variants.reduce((a, b) => a.price <= b.price ? a : b); d.price = min.price; if (min.cost != null) d.cost = min.cost; }
  const i = S.products.findIndex(p => p.id === d.id);
  if (i < 0) S.products.push(d); else S.products[i] = d;
  const wasNew = editing.isNew; save(); closeSheet(); render(); toast(wasNew ? 'Товар добавлен' : 'Изменения сохранены');
}

// фото: уменьшаем, чтобы не раздувать хранилище
export function readImage(file, size) {
  return new Promise((res, rej) => {
    if (!file || !file.type.startsWith('image/')) return rej(new Error('Это не картинка'));
    const r = new FileReader();
    r.onload = () => { const img = new Image(); img.onload = () => {
      const k = Math.min(1, size / Math.max(img.width, img.height));
      const c = document.createElement('canvas'); c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height); res(c.toDataURL('image/jpeg', 0.8));
    }; img.onerror = () => rej(new Error('Не удалось открыть картинку')); img.src = r.result; };
    r.onerror = () => rej(new Error('Не удалось прочитать файл')); r.readAsDataURL(file);
  });
}

// ----- импорт из Excel -----
export function sheetImport() {
  openSheet('Загрузить товары из Excel', `
    <p style="margin:0">Скопируйте строки из Excel или Google Таблиц и вставьте сюда. Столбцы по порядку:</p>
    <div class="tablewrap panel tight"><table><thead><tr><th>Название</th><th class="r">Цена</th><th class="r">Закупка</th><th class="r">Остаток</th><th>Категория</th></tr></thead>
    <tbody><tr><td>Роза белая</td><td class="r">15</td><td class="r">8</td><td class="r">50</td><td>Розы</td></tr></tbody></table></div>
    <span class="small muted">Обязательны только название и цена. Строку с заголовками можно не убирать.</span>
    <textarea class="input" id="impText" style="min-height:180px;font-variant-numeric:tabular-nums" placeholder="Вставьте строки сюда"></textarea>
    <div id="impPreview" class="small"></div>`,
    `<span></span><div class="row"><button class="btn" data-act="close">Отмена</button><button class="btn primary" data-act="doimport" disabled>Добавить</button></div>`);
}
export function parseImport(text) {
  const ok = [], bad = [];
  text.split(/\r?\n/).forEach((line, i) => {
    if (!line.trim()) return;
    const c = line.includes('\t') ? line.split('\t') : line.split(/;|,(?=\s*\d)/);
    const name = (c[0] || '').trim(), price = num(c[1]);
    if (i === 0 && price == null && /назв|name|товар/i.test(name)) return;
    if (!name || price == null || price <= 0) { bad.push(i + 1); return; }
    const stock = num(c[3]);
    ok.push({ name, price, cost: num(c[2]), stock: stock != null && stock >= 0 ? Math.round(stock) : 0, cat: (c[4] || '').trim() || 'Основное' });
  });
  return { ok, bad };
}
export function previewImport() {
  const { ok, bad } = parseImport($('#impText').value);
  $('#impPreview').innerHTML = (ok.length ? `<span style="color:var(--accent);font-weight:600">Готово к добавлению: ${ok.length}</span>` : '') + (bad.length ? `<br><span class="err">Не поняли строки: ${bad.slice(0, 12).join(', ')}${bad.length > 12 ? '…' : ''}. Проверьте, что во втором столбце цена.</span>` : '');
  document.querySelector('[data-act="doimport"]').disabled = !ok.length;
}
export function doImport() {
  const { ok } = parseImport($('#impText').value);
  for (const r of ok) {
    if (!S.cats.includes(r.cat)) S.cats.push(r.cat);
    S.products.push({ id: uid(), name: r.name, cat: r.cat, price: r.price, oldPrice: null, cost: r.cost, stock: r.stock, unit: 'шт', desc: '', imgs: [], active: true, labels: [], prep: null, variants: [], created: Date.now() });
  }
  save(); closeSheet(); ui.stock = 'all'; ui.cat = 'Все'; render(); toast(`Добавлено товаров: ${ok.length}. Теперь добавьте к ним фото`);
}
export async function copyText(text, msg) {
  try { await navigator.clipboard.writeText(text); toast(msg); }
  catch { openSheet('Скопируйте текст', `<textarea class="input" id="copyBox" style="min-height:260px">${esc(text)}</textarea><span class="small muted">Выделите всё и скопируйте, затем вставьте в Excel.</span>`, ''); setTimeout(() => $('#copyBox')?.select(), 50); }
}
