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
