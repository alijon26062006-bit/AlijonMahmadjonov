// Общие мелочи интерфейса панели.
//
// Всё вынесено в отдельный файл, потому что CSP разрешает скрипты только 'self':
// атрибуты вида onsubmit="return confirm(...)" браузер блокирует, и подтверждение
// удаления молча не появляется — форма отправляется сразу.
(function () {
  // Подтверждение опасных действий: <form data-confirm="Удалить файл?">
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || !form.getAttribute) {
      return;
    }
    var question = form.getAttribute('data-confirm');
    if (question && !window.confirm(question)) {
      e.preventDefault();
    }
  });

  // Переименование: <button data-prompt="Новое имя" data-prompt-default="index.php"
  //                         data-prompt-target="имя_скрытого_поля">
  document.addEventListener('click', function (e) {
    var button = e.target.closest ? e.target.closest('[data-prompt]') : null;
    if (!button) {
      return;
    }
    var form = button.form || button.closest('form');
    if (!form) {
      return;
    }
    var answer = window.prompt(button.getAttribute('data-prompt'), button.getAttribute('data-prompt-default') || '');
    if (answer === null || answer === '') {
      e.preventDefault();
      return;
    }
    var field = form.querySelector('[name="' + button.getAttribute('data-prompt-target') + '"]');
    if (field) {
      field.value = answer;
    }
  });
})();

// Кнопки «скопировать» рядом с полями: <button data-copy="значение">
(function () {
  document.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('[data-copy]') : null;
    if (!btn) {
      return;
    }
    e.preventDefault();
    var value = btn.getAttribute('data-copy');

    function done() {
      var old = btn.getAttribute('title') || '';
      btn.setAttribute('title', 'Скопировано');
      btn.classList.add('is-copied');
      setTimeout(function () {
        btn.setAttribute('title', old);
        btn.classList.remove('is-copied');
      }, 1200);
    }

    // navigator.clipboard есть только на https (и на localhost). На обычном http
    // его нет вовсе, поэтому нужен запасной путь через скрытое поле — иначе
    // кнопка молча ничего не делает.
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(value).then(done, fallback);
    } else {
      fallback();
    }

    function fallback() {
      var tmp = document.createElement('textarea');
      tmp.value = value;
      tmp.setAttribute('readonly', '');
      tmp.style.position = 'fixed';
      tmp.style.opacity = '0';
      document.body.appendChild(tmp);
      tmp.select();
      try { document.execCommand('copy'); done(); } catch (err) { /* нечего показать */ }
      document.body.removeChild(tmp);
    }
  });

  // Показать/скрыть пароль: <button data-reveal="#id-поля">
  document.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('[data-reveal]') : null;
    if (!btn) {
      return;
    }
    e.preventDefault();
    var target = document.querySelector(btn.getAttribute('data-reveal'));
    if (!target) {
      return;
    }
    var hidden = target.getAttribute('data-hidden') === '1';
    target.textContent = hidden ? target.getAttribute('data-secret') : '••••••••••';
    target.setAttribute('data-hidden', hidden ? '0' : '1');
  });
})();
