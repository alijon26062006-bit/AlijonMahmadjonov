import { DAYS } from './config.js';
import { blankShop, demo, migrate } from './demo.js';
import { changeStockForOrder } from './domain/orders.js';
import { esc, fmtPhone, num, today, uid } from './lib/format.js';
import { auth, KEY, saveAuth, store } from './services/storage.js';
import { flow, newCount, S, save, setS, ui } from './state.js';
import { $, app, closeSheet, confirmTwice, ICON, isStopped, NAV, openSheet, showErrors, TABS, toast } from './ui/dom.js';
import { copyText, doImport, MEDIA, previewImport, readImageExact, readProductImage, sheetImport, vCatalog } from './views/catalog.js';
import { drawProduct, editing, openProduct, saveProduct, submitProduct, syncDraft, updateMargin, variantRow } from './views/product.js';
import { saveExpense, sheetExpense, vExpenses } from './views/expenses.js';
import { vFinance } from './views/finance.js';
import { vHome } from './views/home.js';
import { PRIVACY, renderAuth, SLIDES, sendCode, TERMS, validateShop } from './views/onboarding.js';
import { renderRegister, sheetPlace } from './views/register.js';
import { ring, testSound } from './services/alerts.js';
import { install } from './services/install.js';
import { cart, drawSale, orderAction, saveSale, sheetSale, testOrder, vOrders } from './views/orders.js';
import { vMore, vShop } from './views/shop.js';
import { exportStats, vStats } from './views/stats.js';
import { vPreview } from './views/storefront.js';
import { refreshSheet } from './views/assemble.js';
import { saveReply, sendComplaint, sheetComplain, sheetReply, testReview, vReviews } from './views/reviews.js';
import { unansweredBad } from './domain/reviews.js';
import { can, me, role } from './domain/staff.js';
import { deleteStaff, saveStaff, sheetStaff, vStaff } from './views/staff.js';
import { ROLES } from './config.js';
import { cloud, connect, deleteShop, disconnect, hooks } from './services/sync.js';
import { setLang, startTranslating, tr } from './i18n.js';
import { applyTheme, isDark, setTheme } from './services/prefs.js';

let view = 'home';
// рендер
export function render() {
  if (!auth.phone) return renderAuth();
  if (!S) return renderRegister();
  if (!S.shop.owner) { S.shop.owner = auth.phone; save(); }
  const who = role();
  if (!who) return renderNoAccess();
  if (!can(view)) view = ROLES[who]?.views[0] || 'home';
  const nc = newCount(), rb = can('reviews') ? unansweredBad() : 0;
  const btn = ([k, label]) => `<button class="nav-btn" data-nav="${k}" ${view === k || (k === 'more' && ['finance', 'expenses', 'preview', 'shop', 'more', 'reviews', 'staff'].includes(view)) ? 'aria-current="page"' : ''}>${ICON[k]}<span>${label}</span>${k === 'orders' && nc ? `<span class="badge">${nc}</span>` : ''}${(k === 'reviews' || k === 'more') && rb ? `<span class="badge">${rb}</span>` : ''}</button>`;
  app.innerHTML = `
  <div class="shell">
    <nav class="rail" aria-label="Разделы">
      <div class="brand"><span class="brand-mark">${ICON.shop}</span>Кабинет продавца</div>
      ${NAV.filter(([k]) => can(k)).map(btn).join('')}
      <div class="rail-foot"><span><span class="status-dot ${S.shop.paused ? 'off' : ''}"></span>${S.shop.paused ? 'Приём заказов на паузе' : 'Принимаем заказы'}</span><span><span translate="no">${esc(S.shop.name)}</span> · ${who === 'owner' ? esc(S.shop.type) : esc(me().name) + ', ' + ROLES[who].name.toLowerCase()}</span></div>
    </nav>
    <main class="main"><div class="content" id="page"></div></main>
    <nav class="tabs" aria-label="Разделы">${TABS.filter(([k]) => can(k)).map(btn).join('')}</nav>
  </div>`;
  const sync = !S.demo && cloud.status !== 'ok' && cloud.status !== 'off' ? `<div class="sync-bar ${cloud.status}"><span class="sync-dot"></span>${cloud.status === 'connecting' ? 'Подключаемся к базе…' : cloud.status === 'offline' ? 'Нет связи с сервером. Всё сохраняется на телефоне и уйдёт в базу, когда появится интернет' : esc('Не удалось сохранить в базу: ' + cloud.error)}</div>` : '';
  const banner = sync + (S.demo ? `<div class="alert"><span>Это <b>пример магазина</b> с выдуманными заказами, чтобы посмотреть, как всё работает.</span><button class="btn sm" data-act="reset">Удалить пример и завести свой магазин</button></div>` : '');
  const V = { finance: vFinance, home: vHome, orders: vOrders, catalog: vCatalog, stats: vStats, expenses: vExpenses, preview: vPreview, shop: vShop, more: vMore, reviews: vReviews, staff: vStaff };
  $('#page').innerHTML = banner + V[view]();
  if (view === 'catalog' && ui.q) { const q = $('#q'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
}
export function go(v) { if (S && !S.shop.owner) S.shop.owner = auth.phone; if (!can(v)) return; const same = view === v; view = v; render(); if (!same) $('#page')?.classList.add('enter'); window.scrollTo(0, 0); }
function renderNoAccess() {
  app.innerHTML = `<div class="screen"><div class="screen-top"></div><div class="screen-body"><h1>Нет доступа</h1>
    <p>Номер +992 ${fmtPhone(auth.phone)} не добавлен в этот магазин. Попросите владельца добавить вас в разделе «Сотрудники» или войдите с другим номером.</p></div>
    <div class="screen-foot"><button class="btn primary big" data-act="logoutnow">Войти с другим номером</button></div></div>`;
}

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
  if (ds.stop) {
    const p = S.products.find(x => x.id === ds.stop);
    if (isStopped(p)) { p.stopUntil = null; toast('Товар снова в продаже'); }
    else { const end = new Date(); end.setHours(24, 0, 0, 0); p.stopUntil = end.getTime(); toast('Скрыт до завтра. Утром вернётся сам'); }
    save(); return render();
  }
  if (ds.melody) { S.shop.melody = ds.melody; save(); render(); ring(ds.melody); return; }
  if (ds.staffedit) return sheetStaff(ds.staffedit);
  if (ds.staffdel) { if (confirmTwice(t, 'Нажмите ещё раз')) deleteStaff(ds.staffdel); return; }
  if (ds.revtab) { ui.revTab = ds.revtab; return render(); }
  if (ds.reply) return sheetReply(ds.reply);
  if (ds.savereply) return saveReply(ds.savereply);
  if (ds.complain) return sheetComplain(ds.complain);
  if (ds.sendcomplaint) return sendComplaint(ds.sendcomplaint);
  if (ds.cart) { cart.items[ds.cart] = Math.max(0, (cart.items[ds.cart] || 0) + +ds.d); return drawSale(); }
  if (ds.delexp) { if (confirmTwice(t, 'Точно?')) { S.expenses = S.expenses.filter(x => x.id !== ds.delexp); save(); render(); } return; }
  if (ds.delcat) { const n = S.products.filter(p => p.cat === ds.delcat).length; if (n) return toast(`Нельзя удалить: в категории ${n} тов.`); S.cats = S.cats.filter(x => x !== ds.delcat); save(); return render(); }
  if (ds.rmph) { syncDraft(); editing.draft.imgs.splice(+ds.rmph, 1); return drawProduct(); }
  if (ds.mainph) { syncDraft(); const im = editing.draft.imgs; im.unshift(im.splice(+ds.mainph, 1)[0]); return drawProduct(); }
  if (ds.rmvar) { t.closest('.variant').remove(); return; }
  if (ds.lang) { setLang(ds.lang); document.title = tr('Кабинет продавца'); return render(); }
  if (ds.auth) {
    const a = ds.auth;
    if (a === 'skip' || (a === 'next' && flow.slide === SLIDES.length - 1)) { auth.onboarded = true; saveAuth(); flow.step = 'phone'; }
    else if (a === 'intro') { flow.step = 'intro'; flow.slide = SLIDES.length - 1; }
    else if (a === 'terms') return openSheet('Условия работы', `<div class="terms">${TERMS}</div>`);
    else if (a === 'privacy') return openSheet('Персональные данные', `<div class="terms">${PRIVACY}</div>`);
    else if (a === 'next') flow.slide++;
    else if (a === 'prev') flow.slide--;
    else if (a === 'chphone') { flow.step = 'phone'; flow.err = ''; }
    else if (a === 'resend') return sendCode();
    return render();
  }
  switch (ds.act) {
    case 'logout': if (confirmTwice(t, 'Нажмите ещё раз, чтобы выйти')) { await disconnect(); setS(null); store.fresh(); auth.phone = ''; saveAuth(); flow.step = 'phone'; flow.phone = ''; view = 'home'; render(); } return;
    case 'alifedit': S.shop.alif.status = 'none'; save(); return render();
    case 'alifok': S.shop.alif.status = 'connected'; save(); render(); return toast('Магазин подключён к Alif');
    case 'demo': setS(demo()); S.shop.owner = auth.phone; save(); return go('home');
    case 'place': return sheetPlace();
    case 'reset': if (confirmTwice(t, 'Нажмите ещё раз — пример удалится')) { store.fresh(); setS(null); render(); } return;
    case 'wipe': if (confirmTwice(t, 'Точно удалить всё? Нажмите ещё раз')) { try { await deleteShop(); } catch (err) { return toast('Не удалось удалить в базе: ' + err.message); } store.fresh(); setS(null); render(); } return;
    case 'add': return openProduct(null);
    case 'dup': { syncDraft(); const src = editing.draft; closeSheet(); openProduct(null, src); return toast('Это копия. Измените и сохраните'); }
    case 'close': return closeSheet();
    case 'saveP': return saveProduct();
    case 'addvar': { const box = $('#variants'); box.insertAdjacentHTML('beforeend', variantRow({ id: uid(), name: '', price: null, cost: null })); box.lastElementChild.querySelector('.vn').focus(); return; }
    case 'delete': if (confirmTwice(t, 'Нажмите ещё раз для удаления')) { S.products = S.products.filter(p => p.id !== editing.draft.id); save(); closeSheet(); render(); toast('Товар удалён'); } return;
    case 'sale': return sheetSale();
    case 'savesale': return saveSale();
    case 'testorder': return testOrder();
    case 'testsound': return testSound();
    case 'delmedia': S.shop[ds.k] = ''; save(); render(); return toast('Убрали');
    case 'themeToggle': setTheme(isDark() ? 'light' : 'dark'); return render();
    case 'themeAuto': setTheme('auto'); return render();
    case 'testreview': return testReview();
    case 'install': return install();
    case 'addstaff': return sheetStaff();
    case 'savestaff': return saveStaff();
    case 'logoutnow': await disconnect(); setS(null); store.fresh(); auth.phone = ''; saveAuth(); flow.step = 'phone'; flow.phone = ''; return render();
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
  if (id === 'p_price' || id === 'p_cost' || id === 'p_oldPrice') updateMargin();
  if (id === 'impText') previewImport();
  if (id === 'agIn') { flow.agree = e.target.checked; $('#agreeBtn').disabled = !flow.agree; }
  if (id === 'phoneIn') { const d = e.target.value.replace(/\D/g, '').replace(/^992(?=\d{9})/, '').slice(0, 9); flow.phone = d; e.target.value = fmtPhone(d); }
  if (id === 'codeIn') { e.target.value = e.target.value.replace(/\D/g, '').slice(0, 4); if (e.target.value.length === 4) $('#codeForm').requestSubmit(); }
});
document.addEventListener('change', async e => {
  const t = e.target, id = t.id;
  if (id === 'stockFilter') { ui.stock = t.value; render(); }
  if (id === 'psort') { ui.psort = t.value; render(); }
  if ((t.name === 'unit' || t.name === 'minStep') && t.closest('#pForm')) { syncDraft(); drawProduct(); return; }
  if (id === 'p_cat') { const n = $('#p_newcat'); n.hidden = t.value !== '__new'; if (!n.hidden) n.focus(); }
  if (id === 'pFile' && t.files.length) {
    syncDraft();
    const room = 4 - editing.draft.imgs.length, files = [...t.files].slice(0, room);
    try { for (const f of files) editing.draft.imgs.push(await readProductImage(f)); } catch (err) { toast(err.message); }
    if (t.files.length > room) toast('Можно не больше 4 фото');
    drawProduct();
  }
  for (const k of ['logo', 'cover', 'banner']) if (id === k + 'File' && t.files[0]) {
    try {
      const m = MEDIA[k], r = await readImageExact(t.files[0], m.w, m.h);
      S.shop[k] = r.src; save(); render();
      toast(r.small ? `Картинка маленькая — лучше ${m.w} × ${m.h}, иначе будет размыто` : r.cropped ? `Края обрезали под ${m.w} × ${m.h}. Проверьте, всё ли видно` : `${m.name} обновлён`);
    } catch (err) { toast(err.message); }
  }
  if (id === 'soundSw') { S.shop.sound = t.checked; save(); toast(t.checked ? 'Звук включён' : 'Звук выключен'); }
  if (id === 'awakeSw') { S.shop.awake = t.checked; save(); toast(t.checked ? 'Экран не будет гаснуть' : 'Экран гаснет как обычно'); }
  if (id === 'autoSw') { S.shop.autoAccept = t.checked; save(); render(); toast(t.checked ? 'Новые заказы будут приниматься сами' : 'Автопринятие выключено'); }
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
  if (id === 'pForm') submitProduct();
  if (id === 'staffForm') saveStaff();
  if (id === 'expForm') saveExpense();
  if (id === 'phoneForm') {
    if (!$('#agIn').checked) return;
    if (flow.phone.length !== 9) { flow.err = 'Введите 9 цифр номера после +992'; return render(); }
    if (!auth.agreed) { auth.agreed = true; auth.agreedAt = Date.now(); saveAuth(); }
    sendCode();
  }
  if (id === 'codeForm') {
    if ($('#codeIn').value !== flow.code) { $('#codeErr').textContent = 'Неверный код. Проверьте и введите ещё раз'; $('#codeIn').value = ''; return $('#codeIn').focus(); }
    auth.phone = flow.phone; auth.loginAt = Date.now(); saveAuth(); flow.err = ''; render(); toast('Вы вошли');
    connect(auth.phone);
  }
});
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('#sheet').hidden) closeSheet(); });
// обновляем «ждёт N мин» у новых заказов
setInterval(() => { if (S && (view === 'orders' || view === 'home') && $('#sheet').hidden && newCount()) render(); }, 60000);

// приложение покупателя на этом устройстве изменило заказы или отзывы — подхватываем сразу
window.addEventListener('storage', e => {
  if (e.key !== KEY) return;
  const next = migrate(store.load()); if (!next || next === 'fresh') return;
  setS(next);
  if ($('#sheet').hidden) render(); else refreshSheet?.();
});

// база: перерисовать экран, когда пришли изменения; о новом заказе — сигнал (звонок крутит alerts.js)
hooks({
  render: () => { if (!auth.phone) return; if ($('#sheet').hidden) render(); else refreshSheet?.(); },
  newOrder: n => toast(n === 1 ? 'Пришёл новый заказ' : `Пришло новых заказов: ${n}`),
});
if (auth.phone) connect(auth.phone);

applyTheme();
startTranslating();
document.title = tr('Кабинет продавца');
render();
