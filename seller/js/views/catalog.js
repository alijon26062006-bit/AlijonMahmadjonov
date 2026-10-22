import { render } from '../app.js';
import { EXPIRY_SOON, kindOf, LOW } from '../config.js';
import { prodSales, ZERO } from '../domain/analytics.js';
import { addDays, esc, money, num, today, uid } from '../lib/format.js';
import { S, save, ui } from '../state.js';
import { $, closeSheet, daysLeft, expiryBlock, expiryPill, fmtQty, ICON, isStopped, openSheet, plusI, stockPill, thumb, toast } from '../ui/dom.js';

// Товары
export function filtered(sales) {
  const q = ui.q.trim().toLowerCase();
  const by = { sales: (a, b) => (sales[b.id] || ZERO).qty - (sales[a.id] || ZERO).qty, new: (a, b) => b.created - a.created, cheap: (a, b) => a.price - b.price, stock: (a, b) => a.stock - b.stock }[ui.psort];
  return S.products.filter(p =>
    (ui.cat === 'Все' || p.cat === ui.cat) && (!q || p.name.toLowerCase().includes(q)) &&
    (ui.stock === 'all' || (ui.stock === 'low' && p.active && p.stock <= LOW) || (ui.stock === 'hidden' && !p.active) || (ui.stock === 'nophoto' && !p.imgs.length) || (ui.stock === 'sale' && p.oldPrice) || (ui.stock === 'stopped' && isStopped(p)) || (ui.stock === 'expiry' && expiringOrBlocked(p)))
  ).sort(by);
}
export const expiringOrBlocked = p => !!expiryBlock(p) || (daysLeft(p) ?? 99) <= EXPIRY_SOON;
export function vCatalog() {
  const sales = prodSales(addDays(today(), -29), today());
  const list = filtered(sales);
  const cats = ['Все', ...S.cats.filter(c => S.products.some(p => p.cat === c))];
  const cnt = f => S.products.filter(f).length;
  const rows = list.map(p => {
    const from = p.variants.length ? Math.min(...p.variants.map(v => v.price)) : p.price;
    return `<div class="prow">
      <button class="open" data-edit="${p.id}">${thumb(p)}<div style="min-width:0"><div class="pname">${esc(p.name)}</div><div class="pmeta"><span>${esc(p.cat || 'Без категории')}</span><span class="pill ${(sales[p.id] || ZERO).qty ? 'info' : 'off'}">Продано за 30 дн: ${(sales[p.id] || ZERO).qty}</span>${stockPill(p)}${expiryPill(p)}${p.oldPrice ? '<span class="pill bad">Скидка</span>' : ''}${p.labels.map(l => `<span class="pill off">${esc(l)}</span>`).join('')}${p.variants.length ? `<span class="pill off">${p.variants.length} вар.</span>` : ''}${p.imgs.length ? '' : '<span class="pill warn">Нет фото</span>'}</div></div></button>
      <div class="stepper" title="Остаток"><button class="iconbtn" data-stock="${p.id}" data-d="-1" aria-label="Уменьшить остаток">−</button><b class="num">${fmtQty(p.stock)}</b><button class="iconbtn" data-stock="${p.id}" data-d="1" aria-label="Увеличить остаток">+</button><button class="tgl" role="switch" aria-checked="${!isStopped(p)}" data-stop="${p.id}" aria-label="${esc(p.name)}: в наличии сегодня" title="${isStopped(p) ? 'Закончилось на сегодня. Включите, чтобы вернуть в продажу' : 'В продаже. Выключите, если закончилось на сегодня'}"></button></div>
      <div class="price num">${p.variants.length ? 'от ' : ''}${money(from)}${p.oldPrice ? `<s>${money(p.oldPrice)}</s>` : `<small>за ${esc(p.unit)}</small>`}</div>
    </div>`;
  }).join('');
  const empty = S.products.length === 0
    ? `<div class="empty panel"><b>Пока нет ни одного товара</b><span>Добавьте первый товар или загрузите сразу весь список из Excel.</span><div class="row" style="justify-content:center"><button class="btn primary" data-act="add">${plusI} Добавить товар</button><button class="btn" data-act="import">${ICON.import} Загрузить из Excel</button></div></div>`
    : `<div class="empty panel"><b>Ничего не нашлось</b><span>Измените поиск или фильтр.</span></div>`;
  return `
    <div class="head"><div><div class="eyebrow">${esc(S.shop.name)}</div><h1>Товары <span class="num" style="color:var(--muted);font-weight:500">${S.products.length}</span></h1></div>
      <div class="row"><button class="btn" data-act="import">${ICON.import} Из Excel</button><button class="btn" data-act="export">Копировать список</button><button class="btn primary hide-m" data-act="add">${plusI} Добавить товар</button></div></div>
    <button class="btn primary fab" data-act="add">${plusI} Добавить товар</button>
    <div class="toolbar">
      <div class="search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input class="input" id="q" type="search" placeholder="Поиск по названию" value="${esc(ui.q)}" aria-label="Поиск"></div>
      <select class="input" id="stockFilter" style="width:auto" aria-label="Фильтр">
        <option value="all">Все товары</option>
        <option value="low" ${ui.stock === 'low' ? 'selected' : ''}>Заканчиваются (${cnt(p => p.active && p.stock <= LOW)})</option>
        <option value="nophoto" ${ui.stock === 'nophoto' ? 'selected' : ''}>Без фото (${cnt(p => !p.imgs.length)})</option>
        <option value="sale" ${ui.stock === 'sale' ? 'selected' : ''}>Со скидкой (${cnt(p => p.oldPrice)})</option>
        ${kindOf(S.shop).expiry ? `<option value="expiry" ${ui.stock === 'expiry' ? 'selected' : ''}>Срок годности (${cnt(expiringOrBlocked)})</option>` : ''}
        <option value="stopped" ${ui.stock === 'stopped' ? 'selected' : ''}>На стопе сегодня (${cnt(isStopped)})</option>
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
    <tbody><tr><td>Помидоры</td><td class="r">12</td><td class="r">8</td><td class="r">40</td><td>Овощи</td></tr></tbody></table></div>
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
  $('#impPreview').innerHTML = (ok.length ? `<span style="color:var(--ok);font-weight:600">Готово к добавлению: ${ok.length}</span>` : '') + (bad.length ? `<br><span class="err">Не поняли строки: ${bad.slice(0, 12).join(', ')}${bad.length > 12 ? '…' : ''}. Проверьте, что во втором столбце цена.</span>` : '');
  document.querySelector('[data-act="doimport"]').disabled = !ok.length;
}
export function doImport() {
  const { ok } = parseImport($('#impText').value);
  for (const r of ok) {
    if (!S.cats.includes(r.cat)) S.cats.push(r.cat);
    S.products.push({ id: uid(), name: r.name, cat: r.cat, price: r.price, oldPrice: null, cost: r.cost, stock: r.stock, unit: kindOf(S.shop).units[0], desc: '', imgs: [], active: true, labels: [], prep: null, variants: [], attrs: {}, expiry: '', created: Date.now() });
  }
  save(); closeSheet(); ui.stock = 'all'; ui.cat = 'Все'; render(); toast(`Добавлено товаров: ${ok.length}. Теперь добавьте к ним фото`);
}
export async function copyText(text, msg) {
  try { await navigator.clipboard.writeText(text); toast(msg); }
  catch { openSheet('Скопируйте текст', `<textarea class="input" id="copyBox" style="min-height:260px">${esc(text)}</textarea><span class="small muted">Выделите всё и скопируйте, затем вставьте в Excel.</span>`, ''); setTimeout(() => $('#copyBox')?.select(), 50); }
}

// 0.5 кг → «500 г», 1 кг → «1 кг», 0.25 л → «250 мл»
export const stepLabel = (s, unit) => s < 1 ? `${s * 1000} ${unit === 'л' ? 'мл' : 'г'}` : `${s} ${unit}`;
