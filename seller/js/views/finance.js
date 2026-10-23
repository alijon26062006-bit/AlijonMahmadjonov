import { orderFee, orderTotal } from '../domain/orders.js';
import { addDays, esc, money, parseKey, r2, today, whenText } from '../lib/format.js';
import { S } from '../state.js';

// Деньги (Alif)
// Покупатель платит через Alif одним платежом. Alif замораживает деньги, после подтверждения доставки
// переводит долю продавца на его терминал, а комиссию — сервису. Сам сервис денег продавцов не держит.
export const ALIF_STATUS = { none: ['Не подключён', 'bad'], pending: ['Проверяем привязку', 'warn'], connected: ['Подключён', ''] };
export function money30() {
  const from = parseKey(addDays(today(), -29)).getTime();
  const app = S.orders.filter(o => o.source === 'app');
  const paid = app.filter(o => o.status === 'done').map(o => ({ ts: o.ts, no: o.no, total: orderTotal(o), fee: orderFee(o), net: r2(orderTotal(o) - orderFee(o)) }));
  const frozen = app.filter(o => ['new', 'accepted', 'ready'].includes(o.status)).reduce((s, o) => s + orderTotal(o) - orderFee(o), 0);
  const last = paid.filter(c => c.ts >= from);
  return { paid, frozen, net30: last.reduce((s, c) => s + c.net, 0), fee30: last.reduce((s, c) => s + c.fee, 0) };
}
export function alifBlock() {
  const a = S.shop.alif, [label, cls] = ALIF_STATUS[a.status];
  if (a.status === 'connected') return `
    <section class="panel col"><div class="row between"><h2>Подключение к Alif</h2><span class="pill ${cls}">${label}</span></div>
      <span>Терминал Alif <b class="num">${esc(a.terminal)}</b>${a.holder ? ' · ' + esc(a.holder) : ''}. Оплата за заказы приходит на счёт, привязанный к этому терминалу.</span>
      <div><button class="btn sm" data-act="alifedit">Изменить терминал</button></div></section>`;
  return `
    <section class="panel col"><div class="row between"><h2>Подключение к Alif</h2><span class="pill ${cls}">${label}</span></div>
      <p style="margin:0">Чтобы деньги за заказы приходили <b>прямо на ваш счёт</b>, магазину нужен свой терминал в Alif, привязанный к нашему сервису. Пока его нет, покупатели не смогут оплатить ваши товары онлайн.</p>
      <ol class="steps">
        <li>Обратитесь в Alif и откройте терминал эквайринга для своего магазина. Документы и условия подскажет Alif.</li>
        <li>Попросите Alif привязать терминал к маркетплейсу нашего сервиса.</li>
        <li>Впишите номер терминала ниже. Мы проверим привязку и включим оплату.</li>
      </ol>
      <form id="alifForm" class="col" novalidate style="gap:14px">
        <div class="grid3">
          <div class="field"><label for="al_t">Номер терминала Alif *</label><input class="input num" id="al_t" name="terminal" inputmode="numeric" value="${esc(a.terminal)}" placeholder="Например, 200001" autocomplete="off"></div>
          <div class="field"><label for="al_h">Получатель (ИП или компания) *</label><input class="input" id="al_h" name="holder" value="${esc(a.holder)}"></div>
          <div class="field"><label for="al_n">ИНН</label><input class="input num" id="al_n" name="tin" inputmode="numeric" value="${esc(a.tin)}"></div>
        </div>
        <div class="row"><button class="btn primary" type="submit">${a.status === 'pending' ? 'Обновить' : 'Отправить на проверку'}</button>
        ${a.status === 'pending' ? '<button class="btn" type="button" data-act="alifok">Отметить как подключённый (тест)</button>' : ''}</div>
        ${a.status === 'pending' ? '<span class="small muted">В рабочей версии привязку проверит сервер и сам поменяет статус. В тестовой версии её можно отметить кнопкой.</span>' : ''}
      </form></section>`;
}
export function vFinance() {
  const M = money30(), a = S.shop.alif;
  const ledger = M.paid.sort((x, y) => y.ts - x.ts).slice(0, 20);
  return `
    <div class="head"><div><div class="eyebrow"><span translate="no">${esc(S.shop.name)}</span></div><h1>Деньги</h1></div></div>
    ${a.status !== 'connected' ? `<div class="alert bad"><span><b>Онлайн-оплата не работает:</b> магазин ещё не подключён к Alif. Ниже показано, что сделать.</span></div>` : ''}
    <div class="kpis">
      <div class="kpi hero"><span>Переведено на ваш счёт за 30 дней</span><b class="num">${money(M.net30)}</b></div>
      <div class="kpi"><span>Заморожено, заказы в работе</span><b class="num">${money(M.frozen)}</b></div>
      <div class="kpi"><span>Комиссия сервиса за 30 дней</span><b class="num">${money(M.fee30)}</b></div>
      <div class="kpi"><span>Оплаченных заказов за 30 дней</span><b class="num">${M.paid.filter(c => c.ts >= parseKey(addDays(today(), -29)).getTime()).length}</b></div>
    </div>
    ${alifBlock()}
    <section class="panel col">
      <h2>Как приходят деньги</h2>
      <ol class="steps">
        <li>Покупатель оплачивает заказ. Деньги резервируются в Alif и видны в строке «Заморожено».</li>
        <li>Вы собираете заказ, курьер доставляет его покупателю.</li>
        <li>Покупатель получил заказ — Alif переводит сумму за вычетом комиссии сервиса на ваш счёт.</li>
      </ol>
      <span class="small muted">Если заказ отменён, покупателю возвращается вся сумма, комиссия не удерживается.</span>
    </section>
    <section class="panel tight"><div style="padding:16px 16px 6px"><h2>Переводы от Alif</h2></div>
      ${ledger.length ? `<div class="tablewrap"><table class="ledger"><thead><tr><th>Дата</th><th>Заказ</th><th class="r">Оплачено</th><th class="r">Комиссия</th><th class="r">Вам</th></tr></thead><tbody>${ledger.map(l => `<tr><td>${whenText(l.ts)}</td><td>№ ${l.no}</td><td class="r">${money(l.total)}</td><td class="r">${money(l.fee)}</td><td class="r"><b class="plus">+${money(l.net)}</b></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty"><b>Пока нет переводов</b><span>Здесь появится каждый оплаченный и полученный покупателем заказ.</span></div>'}
    </section>`;
}
