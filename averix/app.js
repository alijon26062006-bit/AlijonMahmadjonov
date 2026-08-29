/* AVERIX — звёздный фон, меню, появление блоков, форма в Telegram */
(function () {
  'use strict';

  var TELEGRAM_USER = 'rutsiyax';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ============================================================
     Звёздное поле
     Рисуется один раз в canvas, потом не потребляет процессор.
     Туманности — в цветах логотипа: #7021C1 и #038D47.
     ============================================================ */
  var sky = document.getElementById('sky');

  function drawSky() {
    if (!sky) return;
    var ctx = sky.getContext('2d');
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = window.innerWidth;
    var h = window.innerHeight * 1.25;   /* запас под параллакс */

    sky.width = w * dpr;
    sky.height = h * dpr;
    sky.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    ctx.fillStyle = '#07060D';
    ctx.fillRect(0, 0, w, h);

    /* туманности */
    var clouds = [
      { x: 0.78, y: 0.10, r: 0.62, c: '112,33,193', a: 0.30 },
      { x: 0.14, y: 0.34, r: 0.55, c: '112,33,193', a: 0.16 },
      { x: 0.62, y: 0.72, r: 0.58, c: '3,141,71',   a: 0.13 },
      { x: 0.30, y: 0.92, r: 0.50, c: '70,60,150',  a: 0.14 }
    ];
    var unit = Math.max(w, h * 0.6);
    clouds.forEach(function (n) {
      var g = ctx.createRadialGradient(n.x * w, n.y * h, 0, n.x * w, n.y * h, n.r * unit);
      g.addColorStop(0, 'rgba(' + n.c + ',' + n.a + ')');
      g.addColorStop(0.45, 'rgba(' + n.c + ',' + (n.a * 0.32).toFixed(3) + ')');
      g.addColorStop(1, 'rgba(' + n.c + ',0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
    });

    /* звёзды: три слоя глубины */
    var layers = [
      { n: Math.round(w * h / 5200), r: [0.35, 0.75], a: [0.20, 0.45] },
      { n: Math.round(w * h / 16000), r: [0.65, 1.15], a: [0.40, 0.75] },
      { n: Math.round(w * h / 62000), r: [1.10, 1.90], a: [0.70, 1.00] }
    ];
    layers.forEach(function (layer, li) {
      for (var i = 0; i < layer.n; i++) {
        var x = Math.random() * w;
        var y = Math.random() * h;
        var r = layer.r[0] + Math.random() * (layer.r[1] - layer.r[0]);
        var a = layer.a[0] + Math.random() * (layer.a[1] - layer.a[0]);

        /* редкая звезда уходит в фиолетовый или зелёный — фон дышит брендом */
        var tint = '237,235,245';
        var roll = Math.random();
        if (roll > 0.94) tint = '201,165,245';
        else if (roll > 0.90) tint = '110,231,168';

        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(' + tint + ',' + a.toFixed(2) + ')';
        ctx.fill();

        /* самым крупным — мягкое гало */
        if (li === 2) {
          var glow = ctx.createRadialGradient(x, y, 0, x, y, r * 6);
          glow.addColorStop(0, 'rgba(' + tint + ',' + (a * 0.30).toFixed(2) + ')');
          glow.addColorStop(1, 'rgba(' + tint + ',0)');
          ctx.fillStyle = glow;
          ctx.beginPath();
          ctx.arc(x, y, r * 6, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    });
  }

  drawSky();

  var resizeTimer;
  var lastW = window.innerWidth;
  window.addEventListener('resize', function () {
    /* на мобильных адресная строка меняет высоту — перерисовываем только при смене ширины */
    if (window.innerWidth === lastW) return;
    lastW = window.innerWidth;
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(drawSky, 220);
  });

  /* ============================================================
     Скролл: параллакс фона, состояние шапки, кнопка «наверх»
     ============================================================ */
  var nav = document.getElementById('nav');
  var topBtn = document.getElementById('top-btn');
  var ticking = false;

  function onScrollFrame() {
    var y = window.scrollY;
    if (nav) nav.classList.toggle('stuck', y > 12);
    if (topBtn) topBtn.classList.toggle('show', y > 700);
    if (sky && !reduced) sky.style.transform = 'translate3d(0,' + (-y * 0.06).toFixed(1) + 'px,0)';
    ticking = false;
  }

  window.addEventListener('scroll', function () {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(onScrollFrame);
    }
  }, { passive: true });
  onScrollFrame();

  if (topBtn) {
    topBtn.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' });
    });
  }

  var year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();

  /* ============================================================
     Мобильное меню
     ============================================================ */
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
    document.addEventListener('click', function (e) {
      if (menu.classList.contains('open') && !e.target.closest('.nav-in')) closeMenu();
    });
  }

  /* ============================================================
     Появление блоков при скролле
     ============================================================ */
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

  /* ============================================================
     Подсветка карточки под курсором (только там, где есть мышь)
     ============================================================ */
  if (window.matchMedia('(hover: hover)').matches && !reduced) {
    document.querySelectorAll('.card').forEach(function (card) {
      card.addEventListener('mousemove', function (e) {
        var rect = card.getBoundingClientRect();
        card.style.setProperty('--mx', (e.clientX - rect.left) + 'px');
        card.style.setProperty('--my', (e.clientY - rect.top) + 'px');
      });
    });
  }

  /* ============================================================
     Форма → Telegram
     ============================================================ */
  var form = document.getElementById('form');
  if (!form) return;

  var status = document.getElementById('status');

  var FIELDS = [
    { id: 'f-name',    err: 'e-name',    empty: 'Напишите, как к вам обращаться' },
    { id: 'f-contact', err: 'e-contact', empty: 'Оставьте Telegram или телефон — иначе мы не сможем ответить' },
    { id: 'f-task',    err: 'e-task',    empty: 'Опишите задачу хотя бы в двух предложениях' }
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

    window.open('https://t.me/' + TELEGRAM_USER + '?text=' + encodeURIComponent(text), '_blank', 'noopener');

    if (status) status.textContent = 'Открыли Telegram — осталось нажать «Отправить».';
    form.reset();
  });
})();
