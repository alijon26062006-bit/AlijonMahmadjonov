import { DAYS } from './config.js';
import { blankShop, demo } from './demo.js';
import { changeStockForOrder } from './domain/orders.js';
import { esc, fmtPhone, num, today, uid } from './lib/format.js';
import { auth, saveAuth, store } from './services/storage.js';
import { flow, newCount, S, save, setS, ui } from './state.js';
import { $, app, closeSheet, confirmTwice, ICON, NAV, showErrors, TABS, toast } from './ui/dom.js';
import { copyText, doImport, drawProduct, editing, openProduct, previewImport, readImage, saveProduct, sheetImport, syncDraft, updateMargin, variantRow, vCatalog } from './views/catalog.js';
import { saveExpense, sheetExpense, vExpenses } from './views/expenses.js';
import { vFinance } from './views/finance.js';
import { vHome } from './views/home.js';
import { renderAuth, renderWelcome, sendCode, validateShop } from './views/onboarding.js';
import { cart, drawSale, orderAction, saveSale, sheetSale, testOrder, vOrders } from './views/orders.js';
import { vMore, vShop } from './views/shop.js';
import { exportStats, vStats } from './views/stats.js';
import { vPreview } from './views/storefront.js';

let view = 'home';
// рендер
export function render() {
  if (!auth.phone) return renderAuth();
  if (!S) return renderWelcome();
  const nc = newCount();
  const btn = ([k, label]) => `<button class="nav-btn" data-nav="${k}" ${view === k || (k === 'more' && ['finance', 'expenses', 'preview', 'shop', 'more'].includes(view)) ? 'aria-current="page"' : ''}>${ICON[k]}<span>${label}</span>${k === 'orders' && nc ? `<span class="badge">${nc}</span>` : ''}</button>`;
  app.innerHTML = `
  <div class="shell">
    <nav class="rail" aria-label="Разделы">
      <div class="brand"><span class="brand-mark">${ICON.shop}</span>Кабинет продавца</div>
      ${NAV.map(btn).join('')}
      <div class="rail-foot"><span><span class="status-dot ${S.shop.paused ? 'off' : ''}"></span>${S.shop.paused ? 'Приём заказов на паузе' : 'Принимаем заказы'}</span><span>${esc(S.shop.name)} · ${esc(S.shop.type)}</span></div>
    </nav>
    <main class="main"><div class="content" id="page"></div></main>
    <nav class="tabs" aria-label="Разделы">${TABS.map(btn).join('')}</nav>
  </div>`;
  const banner = S.demo ? `<div class="alert"><span>Это <b>пример магазина</b> с выдуманными заказами, чтобы посмотреть, как всё работает.</span><button class="btn sm" data-act="reset">Удалить пример и завести свой магазин</button></div>` : '';
  const V = { finance: vFinance, home: vHome, orders: vOrders, catalog: vCatalog, stats: vStats, expenses: vExpenses, preview: vPreview, shop: vShop, more: vMore };
  $('#page').innerHTML = banner + V[view]();
  if (view === 'catalog' && ui.q) { const q = $('#q'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
}
export function go(v) { view = v; render(); window.scrollTo(0, 0); }

document.addEventListener('click', async e => {
  if (e.target.id === 'sheetBg') return closeSheet();
  const t = e.target.closest('button,[data-nav]'); if (!t || t.disabled) return;
  const ds = t.dataset;
  if (ds.nav) return go(ds.nav);
  if (ds.edit) return openProduct(ds.edit);
  if (ds.cat) { ui.cat = ds.cat; return render(); }
  if (ds.otab) { ui.ordTab = ds.otab; return render(); }
  if (ds.period) { ui.period = ds.period; ui.pickDay = null; return render(); }
  if (ds.day) { ui.pickDay = ui.pickDay === ds.day ? null : ds.day; return render(); }
  if (ds.oact) return orderAction(ds.oact, ds.id);
  if (ds.accmin) { const o = S.orders.find(x => x.id === ds.id); o.status = 'accepted'; o.readyIn = +ds.accmin; o.acceptedAt = Date.now(); save(); closeSheet(); ui.ordTab = 'work'; render(); return toast(`Заказ № ${o.no} принят, будет готов через ${ds.accmin} мин`); }
  if (ds.stock) { const p = S.products.find(x => x.id === ds.stock); p.stock = Math.max(0, p.stock + +ds.d); save(); return render(); }
  if (ds.cart) { cart.items[ds.cart] = Math.max(0, (cart.items[ds.cart] || 0) + +ds.d); return drawSale(); }
  if (ds.delexp) { if (confirmTwice(t, 'Точно?')) { S.expenses = S.expenses.filter(x => x.id !== ds.delexp); save(); render(); } return; }
  if (ds.delcat) { const n = S.products.filter(p => p.cat === ds.delcat).length; if (n) return toast(`Нельзя удалить: в категории ${n} тов.`); S.cats = S.cats.filter(x => x !== ds.delcat); save(); return render(); }
  if (ds.rmph) { syncDraft(); editing.draft.imgs.splice(+ds.rmph, 1); return drawProduct(); }
  if (ds.mainph) { syncDraft(); const im = editing.draft.imgs; im.unshift(im.splice(+ds.mainph, 1)[0]); return drawProduct(); }
  if (ds.rmvar) { t.closest('.variant').remove(); return; }
  if (ds.auth) {
    const a = ds.auth;
    if (a === 'skip' || (a === 'next' && flow.slide === 2)) { auth.onboarded = true; saveAuth(); flow.step = 'phone'; }
    else if (a === 'next') flow.slide++;
    else if (a === 'prev') flow.slide--;
    else if (a === 'chphone') { flow.step = 'phone'; flow.err = ''; }
    else if (a === 'resend') return sendCode();
    return render();
  }
  switch (ds.act) {
    case 'logout': if (confirmTwice(t, 'Нажмите ещё раз, чтобы выйти')) { auth.phone = ''; saveAuth(); flow.step = 'phone'; flow.phone = ''; render(); } return;
    case 'alifedit': S.shop.alif.status = 'none'; save(); return render();
    case 'alifok': S.shop.alif.status = 'connected'; save(); render(); return toast('Магазин подключён к Alif');
    case 'demo': setS(demo()); save(); return go('home');
    case 'reset': if (confirmTwice(t, 'Нажмите ещё раз — пример удалится')) { store.fresh(); setS(null); render(); } return;
    case 'wipe': if (confirmTwice(t, 'Точно удалить всё? Нажмите ещё раз')) { store.fresh(); setS(null); render(); } return;
    case 'add': return openProduct(null);
    case 'dup': { syncDraft(); const src = editing.draft; closeSheet(); openProduct(null, src); return toast('Это копия. Измените и сохраните'); }
    case 'close': return closeSheet();
    case 'saveP': return saveProduct();
    case 'addvar': { const box = $('#variants'); box.insertAdjacentHTML('beforeend', variantRow({ id: uid(), name: '', price: null, cost: null })); box.lastElementChild.querySelector('.vn').focus(); return; }
    case 'delete': if (confirmTwice(t, 'Нажмите ещё раз для удаления')) { S.products = S.products.filter(p => p.id !== editing.draft.id); save(); closeSheet(); render(); toast('Товар удалён'); } return;
    case 'sale': return sheetSale();
    case 'savesale': return saveSale();
    case 'testorder': return testOrder();
    case 'docancel': { const o = S.orders.find(x => x.id === ds.id); o.status = 'cancelled'; o.cancelReason = document.querySelector('input[name="reason"]:checked')?.value || ''; changeStockForOrder(o, 1); save(); closeSheet(); render(); return toast(`Заказ № ${o.no} отменён`); }
    case 'pause': S.shop.paused = false; save(); render(); return toast('Снова принимаем заказы');
    case 'import': return sheetImport();
    case 'doimport': return doImport();
    case 'export': return copyText([['Название', 'Цена', 'Закупка', 'Остаток', 'Категория'].join('\t'), ...S.products.map(p => [p.name, p.price, p.cost ?? '', p.stock, p.cat].join('\t'))].join('\n'), 'Список товаров скопирован. Вставьте его в Excel');
    case 'exportstats': return exportStats();
    case 'addexp': return sheetExpense();
    case 'saveexp': return saveExpense();
  }
});
document.addEventListener('input', e => {
  const id = e.target.id;
  if (id === 'q') { ui.q = e.target.value; render(); }
  if (id === 'oq') { ui.oq = e.target.value; render(); const el = $('#oq'); el.focus(); el.setSelectionRange(el.value.length, el.value.length); }
  if (id === 'p_price' || id === 'p_cost' || id === 'p_old') updateMargin();
  if (id === 'impText') previewImport();
  if (id === 'ag1' || id === 'ag2') $('#agreeBtn').disabled = !($('#ag1').checked && $('#ag2').checked);
  if (id === 'phoneIn') { const d = e.target.value.replace(/\D/g, '').replace(/^992(?=\d{9})/, '').slice(0, 9); flow.phone = d; e.target.value = fmtPhone(d); }
  if (id === 'codeIn') { e.target.value = e.target.value.replace(/\D/g, '').slice(0, 4); if (e.target.value.length === 4) $('#codeForm').requestSubmit(); }
});
document.addEventListener('change', async e => {
  const t = e.target, id = t.id;
  if (id === 'stockFilter') { ui.stock = t.value; render(); }
  if (id === 'psort') { ui.psort = t.value; render(); }
  if (id === 'p_cat') { const n = $('#p_newcat'); n.hidden = t.value !== '__new'; if (!n.hidden) n.focus(); }
  if (id === 'pFile' && t.files.length) {
    syncDraft();
    const room = 4 - editing.draft.imgs.length, files = [...t.files].slice(0, room);
    try { for (const f of files) editing.draft.imgs.push(await readImage(f, 900)); } catch (err) { toast(err.message); }
    if (t.files.length > room) toast('Можно не больше 4 фото');
    drawProduct();
  }
  if (id === 'logoFile' && t.files[0]) { try { S.shop.logo = await readImage(t.files[0], 400); save(); render(); toast('Логотип обновлён'); } catch (err) { toast(err.message); } }
  if (id === 'pauseSw') { S.shop.paused = !t.checked; save(); render(); toast(S.shop.paused ? 'Приём заказов на паузе' : 'Снова принимаем заказы'); }
  if (id === 'fromD') { ui.from = t.value; render(); }
  if (id === 'toD') { ui.to = t.value; render(); }
  if (id === 'saleDate') cart.date = t.value || today();
  if (id === 'salePay') cart.pay = t.value;
  if (id === 'expMonth') { ui.expMonth = t.value; render(); }
  if (id === 'e_cat') $('#stockPurchWrap').hidden = t.value !== 'Закупка товара';
});
document.addEventListener('submit', e => {
  e.preventDefault();
  const f = e.target, id = f.id;
  if (id === 'shopForm') { const d = validateShop(f); if (!d) return; setS({ v: 2, demo: false, shop: blankShop(d), cats: ['Основное'], products: [], orders: [], expenses: [], payouts: [], nextNo: 1001 }); save(); go('catalog'); toast('Магазин создан. Добавьте первый товар'); }
  if (id === 'shopEdit') { const d = validateShop(f); if (!d) return; Object.assign(S.shop, d); save(); render(); toast('Профиль сохранён'); }
  if (id === 'opsForm') {
    const fd = new FormData(f), prep = num(fd.get('prep')), min = fd.get('minOrder').trim() === '' ? 0 : num(fd.get('minOrder'));
    if (!showErrors(f, { ...(prep == null || prep <= 0 ? { prep: 'Больше нуля' } : {}), ...(min == null || min < 0 ? { minOrder: 'Число от нуля' } : {}) })) return;
    if (!fd.get('delivery') && !fd.get('pickup')) return toast('Оставьте хотя бы доставку или самовывоз');
    Object.assign(S.shop, { prep: Math.round(prep), minOrder: min, delivery: !!fd.get('delivery'), pickup: !!fd.get('pickup'), schedule: DAYS.map((_, i) => ({ open: !!fd.get('open' + i), from: fd.get('from' + i) || '09:00', to: fd.get('to' + i) || '21:00' })) });
    save(); render(); toast('Настройки сохранены');
  }
  if (id === 'alifForm') {
    const fd = new FormData(f), t = fd.get('terminal').trim(), h = fd.get('holder').trim(), n = fd.get('tin').trim();
    if (!showErrors(f, { ...(!/^\d{6,}$/.test(t) ? { terminal: 'Только цифры, не меньше 6' } : {}), ...(!h ? { holder: 'Укажите получателя' } : {}) })) return;
    S.shop.alif = { terminal: t, holder: h, tin: n, status: 'pending' }; save(); render(); toast('Отправили на проверку');
  }
  if (id === 'catForm') { const v = $('#newCat').value.trim(); if (!v) return; if (S.cats.includes(v)) return toast('Такая категория уже есть'); S.cats.push(v); save(); render(); }
  if (id === 'pForm') saveProduct();
  if (id === 'expForm') saveExpense();
  if (id === 'termsForm') { if (!$('#ag1').checked || !$('#ag2').checked) return; auth.agreed = true; auth.agreedAt = Date.now(); saveAuth(); flow.step = 'intro'; render(); }
  if (id === 'phoneForm') { if (flow.phone.length !== 9) { flow.err = 'Введите 9 цифр номера после +992'; return render(); } sendCode(); }
  if (id === 'codeForm') {
    if ($('#codeIn').value !== flow.code) { $('#codeErr').textContent = 'Неверный код. Проверьте и введите ещё раз'; $('#codeIn').value = ''; return $('#codeIn').focus(); }
    auth.phone = flow.phone; auth.loginAt = Date.now(); saveAuth(); flow.err = ''; render(); toast('Вы вошли');
  }
});
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('#sheet').hidden) closeSheet(); });
// обновляем «ждёт N мин» у новых заказов
setInterval(() => { if (S && (view === 'orders' || view === 'home') && $('#sheet').hidden && newCount()) render(); }, 60000);

render();
