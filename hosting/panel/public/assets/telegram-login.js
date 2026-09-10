// Вход из Telegram Mini App: страница отдаёт подписанную initData на сервер,
// а проверка подписи целиком делается там (Service\TelegramAuth).
//
// Файл отдельный, а не <script> внутри страницы, потому что CSP панели
// разрешает скрипты только 'self': inline-скрипт браузер молча блокирует, и
// вход через Mini App просто не срабатывает — без единой ошибки на экране.
(function () {
  var tg = window.Telegram && window.Telegram.WebApp;
  var status = document.querySelector('[data-tg-status]');

  if (!tg || !tg.initData) {
    if (status) {
      status.textContent = 'Эта страница открывается только изнутри Telegram.';
    }
    return;
  }

  tg.ready();
  if (tg.expand) {
    tg.expand();
  }

  document.getElementById('tg-init-data').value = tg.initData;
  document.getElementById('tg-form').submit();
})();
