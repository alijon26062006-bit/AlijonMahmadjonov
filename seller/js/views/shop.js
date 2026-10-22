import { CUR, DAYS } from '../config.js';
import { esc, fmtPhone } from '../lib/format.js';
import { auth } from '../services/storage.js';
import { S } from '../state.js';
import { ICON } from '../ui/dom.js';
import { ALIF_STATUS } from './finance.js';
import { shopFields } from './onboarding.js';

// Магазин
export function vShop() {
  const sh = S.shop;
  const logo = sh.logo ? `<img src="${sh.logo}" alt="">` : esc((sh.name || '?').charAt(0).toUpperCase());
  return `
    <div class="head"><div><div class="eyebrow">Настройки</div><h1>Магазин</h1></div></div>
    <form class="panel col" id="shopEdit" novalidate style="gap:14px">
      <h2>Профиль</h2>
      <div class="store-hero"><div class="store-logo">${logo}</div><div class="col" style="gap:6px">
        <label class="btn" for="logoFile">Загрузить логотип</label><input type="file" id="logoFile" accept="image/*" hidden>
        <span class="small muted">Квадратная картинка, JPG или PNG</span></div></div>
      ${shopFields(sh)}
      <div><button class="btn primary" type="submit">Сохранить профиль</button></div>
    </form>
    <form class="panel col" id="opsForm" novalidate style="gap:14px">
      <h2>Работа с заказами</h2>
      <div class="grid3">
        <div class="field"><label for="o_min">Минимальный заказ</label><div class="suffix"><input class="input num" id="o_min" name="minOrder" inputmode="decimal" value="${sh.minOrder || ''}" placeholder="0"><span>${CUR}</span></div></div>
        <div class="field"><label for="o_prep">Обычное время сборки</label><div class="suffix"><input class="input num" id="o_prep" name="prep" inputmode="numeric" value="${sh.prep}"><span>мин</span></div></div>
      </div>
      <div class="row" style="gap:20px"><label class="check"><input type="checkbox" name="delivery" ${sh.delivery ? 'checked' : ''}> Доставка курьером</label><label class="check"><input type="checkbox" name="pickup" ${sh.pickup ? 'checked' : ''}> Самовывоз из магазина</label></div>
      <span class="lbl">График работы</span>
      <div class="sched">${sh.schedule.map((d, i) => `<span>${DAYS[i]}</span><label class="check"><input type="checkbox" name="open${i}" ${d.open ? 'checked' : ''}> Открыто</label><input class="input t" type="time" name="from${i}" value="${d.from}" aria-label="${DAYS[i]}, с"><input class="input t" type="time" name="to${i}" value="${d.to}" aria-label="${DAYS[i]}, до">`).join('')}</div>
      <div><button class="btn primary" type="submit">Сохранить</button></div>
    </form>
    <section class="panel col"><div class="row between"><h2>Подключение к Alif</h2><span class="pill ${ALIF_STATUS[sh.alif.status][1]}">${ALIF_STATUS[sh.alif.status][0]}</span></div>
      <span class="small muted">Терминал Alif нужен, чтобы оплата за заказы приходила прямо на ваш счёт.</span>
      <div><button class="btn" data-nav="finance">${sh.alif.status === 'connected' ? 'Открыть' : 'Подключить'}</button></div></section>
    <section class="panel col">
      <h2>Категории товаров</h2>
      <div class="chips wrap">${S.cats.map(c => `<span class="chip">${esc(c)} <button class="btn ghost" style="padding:0 0 0 6px;min-height:0" data-delcat="${esc(c)}" aria-label="Удалить ${esc(c)}">${ICON.close}</button></span>`).join('')}</div>
      <form id="catForm" class="row"><input class="input" id="newCat" placeholder="Новая категория" style="flex:1 1 200px;width:auto" maxlength="30"><button class="btn" type="submit">Добавить</button></form>
    </section>
    <section class="panel col">
      <h2>Данные</h2>
      <span class="small muted">Сейчас всё хранится в этом браузере. После подключения сервера товары и заказы будут в общей базе, и войти можно будет с любого телефона.</span>
      <div class="row"><button class="btn" data-act="logout">Выйти из кабинета</button><button class="btn danger" data-act="wipe">Удалить магазин и все данные</button></div>
    </section>`;
}
export function vMore() {
  const item = (k, t, s) => `<button data-nav="${k}">${ICON[k]}<span>${t}<small>${s}</small></span></button>`;
  return `<div class="head"><h1>Ещё</h1></div>
    <div class="panel tight morelist">${item('finance', 'Деньги', 'Оплата через Alif и подключение')}${item('expenses', 'Расходы', 'Аренда, зарплата и другие траты')}${item('preview', 'Витрина', 'Как покупатели видят магазин')}${item('shop', 'Магазин', 'Профиль, график, выплаты, категории')}
    <button data-act="import">${ICON.import}<span>Загрузить товары из Excel<small>Сразу весь список</small></span></button>
    <button data-act="logout">${ICON.logout}<span>Выйти<small>+992 ${fmtPhone(auth.phone || '')}</small></span></button></div>`;
}
