/* ============================================================
   AVERIX — админка
   Единственный скрипт панели. Нужен, чтобы в разметке не было
   обработчиков вида onsubmit="...": их запрещает Content-Security-Policy,
   и без этого файла подтверждение удаления просто не появлялось бы.
   ============================================================ */
(function () {
  'use strict';

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || !form.getAttribute) return;
    var question = form.getAttribute('data-confirm');
    if (question && !window.confirm(question)) {
      e.preventDefault();
      return;
    }
    /* повторное нажатие отправило бы форму дважды */
    var button = form.querySelector('button[type="submit"]');
    if (button && !form.hasAttribute('data-keep-enabled')) {
      setTimeout(function () { button.disabled = true; }, 0);
      setTimeout(function () { button.disabled = false; }, 6000);
    }
  });
})();
