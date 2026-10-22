import { render } from '../app.js';
import { FEE, SHOP_TYPES } from '../config.js';
import { esc, fmtPhone } from '../lib/format.js';
import { auth } from '../services/storage.js';
import { flow } from '../state.js';
import { $, app, showErrors } from '../ui/dom.js';

export const SLIDES = [
  { t: 'Добавьте свои товары', d: 'Фото, цена и остаток. Если товаров много, загрузите весь список из Excel за минуту.', art: '<svg viewBox="0 0 24 24"><path d="M3 7l9-4 9 4-9 4-9-4zM3 7v10l9 4 9-4V7M12 11v10"/></svg>' },
  { t: 'Принимайте заказы', d: 'Покупатель заказывает в приложении, вам приходит уведомление. Примите заказ, соберите и передайте курьеру.', art: '<svg viewBox="0 0 24 24"><path d="M6 3h12l1 4H5zM5 7h14v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1zM9 11h6M9 15h4"/></svg>' },
  { t: 'Получайте деньги', d: `Покупатель платит онлайн. Сервис удерживает ${FEE * 100}%, остальное Alif переводит прямо на ваш счёт, когда покупатель получил заказ.`, art: '<svg viewBox="0 0 24 24"><path d="M3 6h18v12H3zM3 10h18M7 15h3"/></svg>', big: `${100 - FEE * 100}%` },
];
export function renderAuth() {
  const f = flow;
  let body = '';
  if (f.step === 'terms') body = `
    <div class="eyebrow">Шаг 1 из 3 · Соглашение</div>
    <h1>Условия работы для продавцов</h1>
    <div class="terms" tabindex="0" aria-label="Текст соглашения">
      <p class="small muted">Тестовая версия. Окончательный текст оферты согласуем с юристом до запуска.</p>
      <h3>1. Что мы делаем</h3><p>Сервис размещает ваши товары в приложении доставки, принимает от покупателей заказы и оплату и передаёт заказы вам.</p>
      <h3>2. Комиссия</h3><p>С каждого выполненного заказа из приложения сервис удерживает ${FEE * 100}% от суммы товаров. Продажи, которые вы отмечаете сами в магазине, комиссией не облагаются.</p>
      <h3>3. Выплаты</h3><p>Оплата покупателя замораживается в Alif до получения заказа. После получения Alif сам переводит сумму за вычетом комиссии на ваш терминал Alif, а оттуда она поступает на ваш счёт. Для этого магазин должен быть подключён к Alif и привязан к сервису.</p>
      <h3>4. Ваши обязанности</h3><p>Указывать настоящие цены, остатки и фото товаров. Принимать или отклонять заказ без задержки, собирать его к обещанному времени, отвечать за качество товара.</p>
      <h3>5. Отмены и возвраты</h3><p>Если заказ отменён по вине продавца, покупателю возвращаются деньги, комиссия не удерживается. Частые отмены снижают позицию магазина в приложении.</p>
      <h3>6. Персональные данные</h3><p>Мы храним ваш номер телефона и данные магазина, чтобы вы могли войти и получать выплаты. Данные покупателей можно использовать только для выполнения заказа.</p>
    </div>
    <form id="termsForm" class="col" style="gap:14px">
      <label class="agree"><input type="checkbox" id="ag1"> <span>Я прочитал(а) и принимаю условия работы для продавцов</span></label>
      <label class="agree"><input type="checkbox" id="ag2"> <span>Согласен(на) на обработку персональных данных</span></label>
      <button class="btn primary" type="submit" id="agreeBtn" disabled>Принять и продолжить</button>
    </form>`;
  if (f.step === 'intro') { const s = SLIDES[f.slide]; body = `
    <div class="row between"><div class="eyebrow">Шаг 2 из 3 · Как это работает</div><button class="linkbtn" data-auth="skip">Пропустить</button></div>
    <div class="slide-art" aria-hidden="true">${s.art}${s.big ? `<span class="big">${s.big}</span>` : ''}</div>
    <div class="col" style="gap:8px"><h1>${s.t}</h1><p>${s.d}</p></div>
    <div class="dots" aria-label="Слайд ${f.slide + 1} из 3">${SLIDES.map((_, i) => `<i class="${i === f.slide ? 'on' : ''}"></i>`).join('')}</div>
    <div class="row between">${f.slide ? '<button class="btn" data-auth="prev">Назад</button>' : '<span></span>'}<button class="btn primary" data-auth="next">${f.slide < 2 ? 'Далее' : 'Понятно, войти'}</button></div>`; }
  if (f.step === 'phone') body = `
    <div class="eyebrow">Шаг 3 из 3 · Вход</div>
    <h1>Ваш номер телефона</h1>
    <p>Пришлём SMS с кодом. По этому номеру вы будете входить в кабинет.</p>
    <form id="phoneForm" class="col" novalidate style="gap:12px">
      <label class="lbl" for="phoneIn">Номер телефона</label>
      <div class="phone"><span>+992</span><input id="phoneIn" type="tel" inputmode="numeric" autocomplete="tel-national" placeholder="90 123 45 67" value="${fmtPhone(f.phone)}" aria-describedby="phoneErr"></div>
      <span class="err" id="phoneErr">${esc(f.err)}</span>
      <button class="btn primary" type="submit">Получить код</button>
    </form>`;
  if (f.step === 'code') { const left = Math.max(0, 60 - Math.round((Date.now() - f.sent) / 1000)); body = `
    <div class="eyebrow">Шаг 3 из 3 · Вход</div>
    <h1>Введите код из SMS</h1>
    <p>Отправили на номер <b style="color:var(--ink)" class="num">+992 ${fmtPhone(f.phone)}</b>. <button class="linkbtn" data-auth="chphone">Изменить</button></p>
    <div class="testnote">Тестовый режим: SMS не отправляется. Ваш код: <b class="num">${f.code}</b></div>
    <form id="codeForm" class="col" novalidate style="gap:12px">
      <input class="input code" id="codeIn" inputmode="numeric" autocomplete="one-time-code" maxlength="4" placeholder="····" aria-label="Код из SMS" aria-describedby="codeErr">
      <span class="err" id="codeErr">${esc(f.err)}</span>
      <button class="btn primary" type="submit">Войти</button>
      <button type="button" class="linkbtn" data-auth="resend" id="resendBtn" ${left ? 'disabled' : ''}>${left ? `Отправить код ещё раз через ${left} с` : 'Отправить код ещё раз'}</button>
    </form>`; }
  app.innerHTML = `<div class="auth"><div class="auth-card">${body}</div></div>`;
  const focus = { phone: '#phoneIn', code: '#codeIn' }[f.step]; if (focus) $(focus).focus();
}
export function sendCode() { flow.code = String(Math.floor(1000 + Math.random() * 9000)); flow.sent = Date.now(); flow.err = ''; flow.step = 'code'; render(); }
setInterval(() => {
  if (flow.step !== 'code' || auth.phone) return;
  const b = $('#resendBtn'); if (!b) return;
  const left = Math.max(0, 60 - Math.round((Date.now() - flow.sent) / 1000));
  b.disabled = !!left; b.textContent = left ? `Отправить код ещё раз через ${left} с` : 'Отправить код ещё раз';
}, 1000);

export function renderWelcome() {
  app.innerHTML = `
  <div class="welcome"><div class="welcome-card">
    <div class="eyebrow">Кабинет продавца</div>
    <h1>Добавьте свой магазин и товары до запуска</h1>
    <p>Покупатели увидят ваш каталог в приложении доставки в день старта рекламы. Заполните его заранее, тогда первые заказы придут сразу.</p>
    <ol class="steps"><li>Укажите название, адрес и телефон магазина</li><li>Добавьте товары с фото и ценой, можно сразу списком из Excel</li><li>Проверьте витрину глазами покупателя</li></ol>
    <form class="panel col" id="shopForm" novalidate>
      ${shopFields({ name: '', type: '', phone: '+992 ' + fmtPhone(auth.phone || ''), address: '', about: '' })}
      <button class="btn primary" type="submit">Создать магазин</button>
    </form>
    <button class="btn ghost" data-act="demo">Сначала посмотреть пример магазина цветов</button>
  </div></div>`;
}

export function shopFields(s) {
  return `
    <div class="field"><label for="s_name">Название магазина *</label><input class="input" id="s_name" name="name" value="${esc(s.name)}" placeholder="Например, Гулистон" maxlength="60"></div>
    <div class="grid2">
      <div class="field"><label for="s_type">Что продаёте *</label><select class="input" id="s_type" name="type"><option value="">Выберите</option>${SHOP_TYPES.map(t => `<option ${t === s.type ? 'selected' : ''}>${t}</option>`).join('')}</select></div>
      <div class="field"><label for="s_phone">Телефон *</label><input class="input" id="s_phone" name="phone" type="tel" value="${esc(s.phone)}" placeholder="+992 __ ___ __ __"></div>
    </div>
    <div class="field"><label for="s_address">Адрес, откуда забирать заказы *</label><input class="input" id="s_address" name="address" value="${esc(s.address)}" placeholder="Город, улица, дом"></div>
    <div class="field"><label for="s_about">Коротко о магазине</label><textarea class="input" id="s_about" name="about" maxlength="200" placeholder="Чем вы отличаетесь от других">${esc(s.about)}</textarea></div>`;
}
export function validateShop(form) {
  const d = Object.fromEntries(new FormData(form)); const errs = {};
  if (!d.name?.trim()) errs.name = 'Введите название';
  if (!d.type) errs.type = 'Выберите, что продаёте';
  if ((d.phone || '').replace(/\D/g, '').length < 9) errs.phone = 'Введите номер полностью';
  if (!d.address?.trim()) errs.address = 'Нужен адрес для курьера';
  if (!showErrors(form, errs)) return null;
  for (const k in d) if (typeof d[k] === 'string') d[k] = d[k].trim();
  return d;
}
