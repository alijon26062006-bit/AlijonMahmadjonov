import { render } from '../app.js';
import { SHOP_TYPES } from '../config.js';
import { esc, fmtPhone } from '../lib/format.js';
import { auth } from '../services/storage.js';
import { flow } from '../state.js';
import { $, app, showErrors } from '../ui/dom.js';
import { lang, LANGS } from '../i18n.js';

export const langSwitch = () => `<div class="seg2" role="radiogroup" aria-label="Язык">${LANGS.map(([k, t]) => `<button role="radio" aria-checked="${lang === k}" data-lang="${k}" translate="no">${t}</button>`).join('')}</div>`;

// картинка 3D лежит в img/intro-N.webp; пока её нет, видна запасная линейная иконка
export const SLIDES = [
  { img: 'intro-1', t: 'Ваш магазин в приложении', d: 'Добавьте товары с фото и ценой. Покупатели в вашем городе увидят их сразу.', art: '<path d="M3 7l9-4 9 4-9 4-9-4zM3 7v10l9 4 9-4V7M12 11v10"/>' },
  { img: 'intro-2', t: 'Новый заказ — сразу сигнал', d: 'Телефон звонит, пока вы не ответите. Принять заказ можно одной кнопкой или включить автоприём.', art: '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 21h4"/>' },
  { img: 'intro-3', t: 'Соберите — курьер заберёт', d: 'Сложите заказ в пакет и отметьте «Готов». Курьер приедет к вам и отвезёт покупателю.', art: '<path d="M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2"/>' },
  { img: 'intro-4', t: 'Деньги — на ваш счёт', d: 'Покупатель платит онлайн. Когда он получил заказ, деньги поступают вам. Всё видно в разделе «Деньги».', art: '<path d="M3 7h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM3 7l12-4v4M16 13.5h2"/>' },
];
const back = to => `<button class="iconbtn" data-auth="${to}" aria-label="Назад"><svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg></button>`;

export function renderAuth() {
  const f = flow;
  let html = '';
  if (f.step === 'intro') { const s = SLIDES[f.slide], last = f.slide === SLIDES.length - 1; html = `
    <div class="screen intro">
      <div class="screen-top">${f.slide ? back('prev') : langSwitch()}${last ? '' : '<button class="linkbtn" data-auth="skip">Пропустить</button>'}</div>
      <div class="intro-art" aria-hidden="true">
        <svg viewBox="0 0 24 24">${s.art}</svg>
        <img src="img/${s.img}.webp" alt="" onerror="this.hidden=true">
      </div>
      <div class="intro-text"><h1>${s.t}</h1><p>${s.d}</p></div>
      <div class="screen-foot">
        <div class="dots" aria-label="Слайд ${f.slide + 1} из ${SLIDES.length}">${SLIDES.map((_, i) => `<i class="${i === f.slide ? 'on' : ''}"></i>`).join('')}</div>
        <button class="btn primary big" data-auth="next">${last ? 'Начать' : 'Далее'}</button>
      </div>
    </div>`; }
  if (f.step === 'phone') html = `
    <form class="screen" id="phoneForm" novalidate>
      <div class="screen-top">${back('intro')}<span></span></div>
      <div class="screen-body">
        <h1>Вход для продавцов</h1>
        <p>Введите номер телефона — пришлём SMS с кодом.</p>
        <div class="phone big"><span>+992</span><input id="phoneIn" type="tel" inputmode="numeric" autocomplete="tel-national" placeholder="90 123 45 67" value="${fmtPhone(f.phone)}" aria-label="Номер телефона" aria-describedby="phoneErr"></div>
        <span class="err" id="phoneErr">${esc(f.err)}</span>
      </div>
      <div class="screen-foot">
        <label class="agree"><input type="checkbox" id="agIn" ${f.agree ?? auth.agreed ? 'checked' : ''}> <span>Принимаю <button type="button" class="linkbtn" data-auth="terms">условия работы</button> и даю согласие на <button type="button" class="linkbtn" data-auth="privacy">обработку персональных данных</button></span></label>
        <button class="btn primary big" type="submit" id="agreeBtn" ${f.agree ?? auth.agreed ? '' : 'disabled'}>Получить код</button>
      </div>
    </form>`;
  if (f.step === 'code') { const left = Math.max(0, 60 - Math.round((Date.now() - f.sent) / 1000)); html = `
    <form class="screen" id="codeForm" novalidate>
      <div class="screen-top">${back('chphone')}<span></span></div>
      <div class="screen-body">
        <h1>Код из SMS</h1>
        <p>Отправили на <b class="num" style="color:var(--ink)">+992 ${fmtPhone(f.phone)}</b></p>
        <input class="input code" id="codeIn" inputmode="numeric" autocomplete="one-time-code" maxlength="4" placeholder="····" aria-label="Код из SMS" aria-describedby="codeErr">
        <span class="err" id="codeErr">${esc(f.err)}</span>
        <div class="testnote">Тестовый режим: SMS не отправляется. Ваш код: <b class="num">${f.code}</b></div>
      </div>
      <div class="screen-foot">
        <button type="button" class="linkbtn" data-auth="resend" id="resendBtn" ${left ? 'disabled' : ''}>${left ? `Отправить код ещё раз через ${left} с` : 'Отправить код ещё раз'}</button>
        <button class="btn primary big" type="submit">Войти</button>
      </div>
    </form>`; }
  app.innerHTML = html;
  const focus = { code: '#codeIn' }[f.step]; if (focus) $(focus).focus();
}

export const TERMS = `
  <p class="small muted">Редакция от 22 октября 2026 года</p>
  <h3>1. Общие положения</h3><p>Настоящие условия регулируют отношения между сервисом доставки (далее — Сервис) и продавцом: магазином, рестораном или индивидуальным предпринимателем (далее — Продавец), который размещает свои товары в приложении Сервиса. Отмечая согласие при входе, Продавец подтверждает, что ознакомился с условиями и принимает их полностью.</p>
  <h3>2. Предмет</h3><p>Сервис размещает товары Продавца в приложении, принимает заказы и оплату от покупателей, организует доставку и передаёт Продавцу информацию о заказах. Продавец продаёт товары от своего имени и отвечает за их качество.</p>
  <h3>3. Товары и цены</h3><p>Продавец самостоятельно добавляет товары и указывает достоверные названия, фотографии, цены, состав и остатки. Цена в приложении не должна быть выше цены в магазине Продавца. Сервис вправе скрыть товар, если сведения о нём недостоверны или нарушают закон.</p>
  <h3>4. Заказы</h3><p>Продавец принимает или отклоняет заказ без задержки и собирает его к указанному времени. Если товара нет в наличии, Продавец отклоняет заказ с указанием причины. Систематические отказы и опоздания снижают позицию магазина в приложении.</p>
  <h3>5. Оплата и расчёты</h3><p>Покупатель оплачивает заказ через платёжного партнёра Сервиса. Оплата резервируется до получения заказа покупателем и после этого перечисляется на счёт Продавца за вычетом вознаграждения Сервиса. Размер вознаграждения определяется тарифом, который Сервис согласует с Продавцом при подключении. Продажи, которые Продавец отмечает сам в магазине, вознаграждением не облагаются.</p>
  <h3>6. Отмены и возвраты</h3><p>Если заказ отменён до получения, покупателю возвращается полная сумма, вознаграждение Сервиса не удерживается. Претензии покупателя к качеству товара Продавец рассматривает в соответствии с законодательством Республики Таджикистан.</p>
  <h3>7. Персональные данные</h3><p>Сервис обрабатывает номер телефона и данные магазина Продавца, чтобы обеспечить вход в кабинет и расчёты. Продавец использует данные покупателей только для выполнения заказа и не передаёт их третьим лицам.</p>
  <h3>8. Изменение условий</h3><p>Сервис вправе изменять условия, уведомив Продавца в кабинете не позднее чем за 7 дней. Продолжая работу после вступления изменений в силу, Продавец соглашается с новой редакцией.</p>`;
export const PRIVACY = `
  <p>Чтобы вы могли входить в кабинет и получать деньги за заказы, Сервис хранит и обрабатывает:</p>
  <ul><li>номер телефона;</li><li>название, адрес и часы работы магазина;</li><li>номер терминала для выплат;</li><li>историю заказов и продаж.</li></ul>
  <p>Данные хранятся на защищённых серверах и передаются только платёжному партнёру и курьеру — в объёме, нужном для заказа. Отозвать согласие и удалить кабинет можно, написав в поддержку.</p>`;

// листание слайдов пальцем
let x0 = null;
document.addEventListener('touchstart', e => { x0 = flow.step === 'intro' && !auth.phone ? e.touches[0].clientX : null; }, { passive: true });
document.addEventListener('touchend', e => {
  if (x0 === null) return;
  const dx = e.changedTouches[0].clientX - x0; x0 = null;
  if (Math.abs(dx) < 50) return;
  if (dx < 0 && flow.slide < SLIDES.length - 1) flow.slide++;
  else if (dx > 0 && flow.slide > 0) flow.slide--;
  else return;
  render();
});
export function sendCode() { flow.code = String(Math.floor(1000 + Math.random() * 9000)); flow.sent = Date.now(); flow.err = ''; flow.step = 'code'; render(); }
setInterval(() => {
  if (flow.step !== 'code' || auth.phone) return;
  const b = $('#resendBtn'); if (!b) return;
  const left = Math.max(0, 60 - Math.round((Date.now() - flow.sent) / 1000));
  b.disabled = !!left; b.textContent = left ? `Отправить код ещё раз через ${left} с` : 'Отправить код ещё раз';
}, 1000);

export function shopFields(s) {
  return `
    <div class="field"><label for="s_name">Название магазина *</label><input class="input" id="s_name" name="name" value="${esc(s.name)}" placeholder="Например, Бозори Сабз" maxlength="60"></div>
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
