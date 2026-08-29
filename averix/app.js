/* AVERIX — минимальный JS: меню, появление блоков, форма в Telegram */
(function () {
  'use strict';

  var TELEGRAM_USER = 'rutsiyax';

  /* ---------- год в подвале ---------- */
  var year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();

  /* ---------- рамка у шапки при скролле ---------- */
  var nav = document.getElementById('nav');
  function onScroll() {
    if (nav) nav.classList.toggle('stuck', window.scrollY > 8);
  }
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  /* ---------- мобильное меню ---------- */
  var burger = document.getElementById('burger');
  var menu = document.getElementById('menu');

  function closeMenu() {
    if (!menu) return;
    menu.classList.remove('open');
    burger.setAttribute('aria-expanded', 'false');
    burger.setAttribute('aria-label', 'Открыть меню');
  }

  if (burger && menu) {
    burger.addEventListener('click', function () {
      var open = menu.classList.toggle('open');
      burger.setAttribute('aria-expanded', String(open));
      burger.setAttribute('aria-label', open ? 'Закрыть меню' : 'Открыть меню');
    });
    menu.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') closeMenu();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && menu.classList.contains('open')) {
        closeMenu();
        burger.focus();
      }
    });
  }

  /* ---------- появление блоков при скролле ---------- */
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var items = document.querySelectorAll('.r');

  if (reduced || !('IntersectionObserver' in window)) {
    Array.prototype.forEach.call(items, function (el) { el.classList.add('in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
    Array.prototype.forEach.call(items, function (el) { io.observe(el); });
  }

  /* ---------- форма → Telegram ---------- */
  var form = document.getElementById('form');
  if (!form) return;

  var status = document.getElementById('status');

  var FIELDS = [
    { id: 'f-name',    err: 'e-name',    label: 'Имя',      empty: 'Напишите, как к вам обращаться' },
    { id: 'f-contact', err: 'e-contact', label: 'Контакт',  empty: 'Оставьте Telegram или телефон — иначе мы не сможем ответить' },
    { id: 'f-task',    err: 'e-task',    label: 'Задача',   empty: 'Опишите задачу хотя бы в двух предложениях' }
  ];

  function showError(field, message) {
    var input = document.getElementById(field.id);
    var box = document.getElementById(field.err);
    input.setAttribute('aria-invalid', 'true');
    input.setAttribute('aria-describedby', field.err);
    box.textContent = message;
    box.hidden = false;
  }

  function clearError(field) {
    var input = document.getElementById(field.id);
    var box = document.getElementById(field.err);
    input.removeAttribute('aria-invalid');
    input.removeAttribute('aria-describedby');
    box.textContent = '';
    box.hidden = true;
  }

  /* проверяем при уходе из поля, а не на каждом нажатии */
  FIELDS.forEach(function (field) {
    var input = document.getElementById(field.id);
    input.addEventListener('blur', function () {
      if (input.value.trim()) clearError(field);
    });
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (status) status.textContent = '';

    var firstInvalid = null;

    FIELDS.forEach(function (field) {
      var input = document.getElementById(field.id);
      if (!input.value.trim()) {
        showError(field, field.empty);
        if (!firstInvalid) firstInvalid = input;
      } else {
        clearError(field);
      }
    });

    if (firstInvalid) {
      firstInvalid.focus();
      return;
    }

    var text =
      'Заявка с сайта AVERIX\n\n' +
      'Имя: ' + document.getElementById('f-name').value.trim() + '\n' +
      'Контакт: ' + document.getElementById('f-contact').value.trim() + '\n' +
      'Задача: ' + document.getElementById('f-task').value.trim();

    window.open(
      'https://t.me/' + TELEGRAM_USER + '?text=' + encodeURIComponent(text),
      '_blank',
      'noopener'
    );

    if (status) status.textContent = 'Открыли Telegram — осталось нажать «Отправить».';
    form.reset();
  });
})();
