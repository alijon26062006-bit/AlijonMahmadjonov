/* ============================================================
   AVERIX
   Замер страницы, переключатель языка, меню, форма.
   Зависимостей нет.
   ============================================================ */
(function () {
  'use strict';

  var TELEGRAM_USER = 'rutsiyax';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ============================================================
     Язык: русский в разметке, таджикский — словарём.
     Русские строки берём из самой страницы, поэтому без JS
     сайт остаётся полностью читаемым.
     ============================================================ */
  var TG = {
    'skip': 'Гузаштан ба мундариҷа',

    'nav.who': 'Дар бораи ман',
    'nav.services': 'Хизматрасонӣ',
    'nav.process': 'Раванди кор',
    'nav.contact': 'Дархост',

    'hero.eyebrow': 'IT-студия · Душанбе · аз соли 2023',
    'hero.h1': 'Сомонаҳое, ки бо <em>даст</em> сохта мешаванд, на бо конструктор',
    'hero.sub': 'Ҳар лоиҳа аз сифр барои вазифаи мушаххаси тиҷорат навишта мешавад. ' +
                'Барои ҳамин он дар як лаҳза бор мешавад, на дар панҷ сония, ва баъдтар ' +
                'онро рушд додан мумкин аст, на партофтан.',
    'cta.discuss': 'Муҳокимаи лоиҳа',
    'cta.process': 'Кор чӣ тавр меравад',
    'cta.calc': 'Гирифтани ҳисоб',

    'stats.years': 'сол',
    'stats.years.note': 'ҳар рӯз код менависам',
    'stats.active': 'лоиҳа айни замон дар кор',
    'stats.happy': 'мизоҷон корро қабул карданд',

    'who.label': 'Кӣ месозад',
    'who.h2': 'Номи ман <em>Алиҷон</em>',
    'who.role': 'асосгузори AVERIX · веб-барномасоз · Душанбе',
    'who.open': 'Барои лоиҳаҳои нав кушодаам',
    'who.p1': 'Ман 19-солаам, ва се соли он ҳар рӯз код менависам. Аз Python ва ботҳо ' +
              'сар кардам, ҳоло сомона месозам: аз яксаҳифагӣ то корпоративӣ.',
    'who.p2': 'Ман шаблон намегирам ва логотипи шуморо ба он намекашам. Ҳар лоиҳа аз сифр ' +
              'сохта мешавад — ин тӯлонитар аст, вале сомона зуд бор мешавад, онро рушд ' +
              'додан мумкин аст ва он аз аввалин ислоҳ вайрон намешавад.',
    'who.p3': 'Рӯирост кор мекунам: агар вазифа аз имконияти ман берун бошад ё мӯҳлат ' +
              'воқеӣ набошад — дар аввалин сӯҳбат мегӯям, на баъди пешпардохт.',

    'services.label': 'Хизматрасонӣ',
    'services.h2': 'Мо чӣ мекунем',
    'services.lede': 'Се самт. Боқимондаро алоҳида муҳокима мекунем — ва рӯирост мегӯем, мегирем ё не.',

    'svc1.h': 'Лендинг барои вазифа',
    'svc1.p': 'Як саҳифа бо як мақсад: дархост, занг, сабт. Сохтор аз рӯи маҳсулот ва ' +
              'эродҳои мизоҷони шумо сохта мешавад.',
    'svc1.l1': 'Прототип ва матн',
    'svc1.l2': 'Дизайн мувофиқи бренди шумо',
    'svc1.l3': 'Шакли дархост ба Telegram',
    'svc1.l4': 'Мутобиқшавӣ ба телефон',

    'svc2.h': 'Сомонаи пурра',
    'svc2.p': 'Сомонаи бисёрсаҳифаи ширкат: хизматрасонӣ, дар бораи мо, тамос, блог. ' +
              'Сохтори равшан ва навигатсияи муқаррарӣ.',
    'svc2.l1': 'То 8 саҳифа',
    'svc2.l2': 'Панел барои ислоҳи матн',
    'svc2.l3': 'SEO-разметка ва микромаълумот',
    'svc2.l4': 'Пайвасти домен ва SSL',

    'svc3.h': 'Дастгирӣ ва такмил',
    'svc3.p': 'Сомона ҳаст, вале суст аст, дар телефон вайрон мешавад ё касе нест, ки ' +
              'навсозӣ кунад — ба хизматрасонӣ мегирем.',
    'svc3.l1': 'Тезонидани боркунӣ',
    'svc3.l2': 'Ислоҳи вёрстка дар мобилӣ',
    'svc3.l3': 'Бахшҳо ва блокҳои нав',
    'svc3.l4': 'Кӯчонидан ба хостинги дигар',

    'price.h': 'Нарх аз чӣ иборат аст',
    'price.p': 'Прайси ягона нест: лендинг аз панҷ блок ва сомона бо каталог — кори гуногун. ' +
               'Вале мо ҳамеша аз рӯи ҳамон чизҳо ҳисоб мекунем, ва ҳисобро шумо пеш аз оғоз мебинед.',
    'price.a.h': 'Ҳаҷм',
    'price.a.p': 'Чанд саҳифа ва блоки нотакрор. Зарбкунандаи асосӣ.',
    'price.b.h': 'Функсияҳо',
    'price.b.p': 'Шакл — содда. Каталог, кабинет, пардохт — кори алоҳида.',
    'price.c.h': 'Мазмун',
    'price.c.p': 'Матн ва акс ҳаст — зудтар. Мо менависем — тӯлонитар.',
    'price.foot': 'Нависед, ки чӣ лозим аст — дар давоми рӯз ҳисоб аз рӯи ин се банд ва ' +
                  'мӯҳлатро мефиристем. Ройгон ва ӯҳдадорӣ надорад.',

    'process.label': 'Раванд',
    'process.h2': 'Кор чӣ тавр меравад',
    'process.lede': 'Чор қадам. Пас аз ҳар яке шумо натиҷаро мебинед ва қарор мекунед, пеш ' +
                    'меравем ё не. Пардохт — аз рӯи марҳилаҳо, на пешакӣ барои ҳама.',

    'step1.h': 'Вазифаро таҳлил мекунем',
    'step1.p': 'Дар Telegram менависем ё занг мезанем. Муайян мекунем, мизоҷи шумо кист, ' +
               'вай дар сомона чӣ бояд кунад ва ҳоло чӣ ба ӯ халал мерасонад.',
    'step1.out': '→ рӯйхати саҳифаҳо ва блокҳо',
    'step2.h': 'Прототип ва матн',
    'step2.p': 'Нақшаи саҳифаро месозем: чӣ пас аз чӣ меояд ва ҳар блок кадом корро мекунад. ' +
               'Матнро якҷоя менависем — шумо маҳсулотро медонед, мо тарзи пешниҳодашро.',
    'step2.out': '→ сохтори мувофиқашуда пеш аз дизайн',
    'step3.h': 'Дизайн ва васл',
    'step3.p': 'Макетро мувофиқи бренди шумо мекашем, нишон медиҳем, ислоҳ мекунем. Баъд ' +
               'вёрстка: аввал телефон, баъд десктоп. Дар дастгоҳҳои воқеӣ месанҷем.',
    'step3.out': '→ сомонаи корӣ дар суроғаи санҷишӣ',
    'step4.h': 'Оғоз ва супоридан',
    'step4.p': 'Домен ва SSL-ро пайваст мекунем, аналитика мегузорем, шаклҳоро месанҷем. ' +
               'Ҳамаи дастрасӣ ва кодро месупорем — сомона пурра аз они шумост.',
    'step4.out': '→ сомона дар кор, дастрасӣ дар шумо',

    'final.label': 'Саволҳо ва дархост',
    'final.h2': 'Нависед, ки чӣ лозим аст',

    'faq1.q': 'Чанд ислоҳ ба кор дохил мешавад?',
    'faq1.a': 'Ислоҳҳо дар доираи сохтори мувофиқашуда — чанде ки лозим бошад. Алоҳида ' +
              'танҳо тағйири худи вазифа ҳисоб мешавад: масалан, ба ҷои лендинг мағоза. ' +
              'Дар ин бора фавран огоҳ мекунем, на дар ҳисобнома.',
    'faq2.q': 'Барои оғоз аз ман чӣ лозим аст?',
    'faq2.a': 'Ҳадди ақал: бо чӣ машғулед ва меҳмони сомона чӣ бояд кунад. Боқимондаро — ' +
              'матн, акс, сохтор — бо саволҳо дар марҳилаи аввал муайян мекунем. Логотип ва ' +
              'брендбук барои оғоз лозим нест.',
    'faq3.q': 'Ин чӣ қадар вақт мегирад?',
    'faq3.a': 'Мӯҳлатро пас аз таҳлили вазифа ҳамроҳи ҳисоб мегӯем. Он аз ҳаҷм ва аз он ' +
              'вобаста аст, ки ҷавобу маводҳо аз ҷониби шумо чӣ қадар зуд меоянд — одатан ' +
              'таъхири асосӣ ҳамин аст, на худи васл.',
    'faq4.q': 'Агар кор бас кунем, сомона дар ман мемонад?',
    'faq4.a': 'Бале. Домен ба номи шумо ба қайд гирифта мешавад, код ва ҳамаи дастрасиро ' +
              'пас аз оғоз месупорем. Ҳеҷ вобастагӣ ба хостинг ё аккаунтҳои мо нест.',
    'faq5.q': 'Танҳо дар Душанбе кор мекунед?',
    'faq5.a': 'Не. Тамоми кор дар мукотиба ва зангҳо мегузарад, барои ҳамин шаҳр муҳим нест. ' +
              'Танҳо мо аз ин ҷоем, ва дар Душанбе метавонем рӯ ба рӯ вохӯрем, агар қулайтар бошад.',

    'form.name': 'Шуморо чӣ хел муроҷиат кунем',
    'form.name.ph': 'Масалан, Фаррух',
    'form.contact': 'Telegram ё телефон',
    'form.contact.hint': 'ҳисобро ба куҷо фиристем',
    'form.task': 'Чӣ кор кардан лозим аст',
    'form.task.ph': 'Ду ҷумла: бо чӣ машғулед ва сомона чӣ бояд кунад',
    'form.submit': 'Ба Telegram фиристодан',
    'form.note': 'дархост ҳамчун паёми тайёр кушода мешавад — танҳо «Фиристодан»-ро пахш кунед',
    'form.sent': 'Telegram кушода шуд — «Фиристодан»-ро пахш кунед.',

    'foot.about': 'Студия аз Душанбе. Сомонаҳо ва лендингҳо, ки бо даст барои вазифаи тиҷорат сохта мешаванд.',
    'foot.services': 'Хизматрасонӣ',
    'foot.studio': 'Студия',
    'foot.contact': 'Тамос',
    'foot.faq': 'Саволҳо',
    'foot.city': 'Душанбе, Тоҷикистон'
  };

  var RU = {};   /* заполняется со страницы при загрузке */
  var langButtons = document.querySelectorAll('.lang button');

  document.querySelectorAll('[data-i18n]').forEach(function (el) {
    RU[el.dataset.i18n] = el.innerHTML;
  });
  document.querySelectorAll('[data-i18n-ph]').forEach(function (el) {
    RU[el.dataset.i18nPh] = el.placeholder;
  });

  function setLang(code) {
    var dict = code === 'tg' ? TG : RU;

    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var v = dict[el.dataset.i18n];
      if (v !== undefined) el.innerHTML = v;
    });
    document.querySelectorAll('[data-i18n-ph]').forEach(function (el) {
      var v = dict[el.dataset.i18nPh];
      if (v !== undefined) el.placeholder = v;
    });

    document.documentElement.lang = code === 'tg' ? 'tg' : 'ru';
    langButtons.forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.lang === code));
    });
    movePill(code);
    try { localStorage.setItem('averix-lang', code); } catch (e) {}
  }

  langButtons.forEach(function (b) {
    b.addEventListener('click', function () { setLang(b.dataset.lang); });
  });

  try {
    var saved = localStorage.getItem('averix-lang');
    if (saved === 'tg') setLang('tg');
  } catch (e) {}

  /* стартовое положение бегунка и пересчёт при смене размера шрифта/окна */
  movePill(document.documentElement.lang === 'tg' ? 'tg' : 'ru');
  window.addEventListener('resize', function () {
    movePill(document.documentElement.lang === 'tg' ? 'tg' : 'ru');
  });

  /* ============================================================
     Шапка и меню
     ============================================================ */
  var nav = document.getElementById('nav');
  var ticking = false;

  window.addEventListener('scroll', function () {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      if (nav) nav.classList.toggle('stuck', window.scrollY > 8);
      ticking = false;
    });
  }, { passive: true });

  var burger = document.getElementById('burger');
  var menu = document.getElementById('menu');
  var backdrop = document.getElementById('backdrop');

  function openMenu() {
    menu.classList.add('open');
    backdrop.hidden = false;
    /* следующий кадр — иначе переход прозрачности не проиграется */
    requestAnimationFrame(function () { backdrop.classList.add('open'); });
    burger.setAttribute('aria-expanded', 'true');
    burger.setAttribute('aria-label', 'Закрыть меню');
    document.body.style.overflow = 'hidden';
    var first = menu.querySelector('a');
    if (first) first.focus();
  }

  function closeMenu(returnFocus) {
    menu.classList.remove('open');
    backdrop.classList.remove('open');
    backdrop.hidden = true;
    burger.setAttribute('aria-expanded', 'false');
    burger.setAttribute('aria-label', 'Открыть меню');
    document.body.style.overflow = '';
    if (returnFocus) burger.focus();
  }

  if (burger && menu && backdrop) {
    burger.addEventListener('click', function () {
      if (menu.classList.contains('open')) closeMenu(true);
      else openMenu();
    });
    backdrop.addEventListener('click', function () { closeMenu(true); });
    menu.addEventListener('click', function (e) {
      if (e.target.closest('a')) closeMenu(false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && menu.classList.contains('open')) closeMenu(true);
    });
    /* панель живёт только на узких экранах — на широких закрываем принудительно */
    window.addEventListener('resize', function () {
      if (window.innerWidth > 900 && menu.classList.contains('open')) closeMenu(false);
    });
  }

  var year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();

  /* ============================================================
     Появление блоков
     ============================================================ */
  var items = document.querySelectorAll('.r');

  if (reduced || !('IntersectionObserver' in window)) {
    Array.prototype.forEach.call(items, function (el) { el.classList.add('in'); });
    document.querySelectorAll('[data-count]').forEach(countUp);
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          entry.target.querySelectorAll('[data-count]').forEach(countUp);
          io.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
    Array.prototype.forEach.call(items, function (el) { io.observe(el); });
  }


  /* ============================================================
     Бегунок переключателя языка
     ============================================================ */
  function movePill(code) {
    /* элемент ищем внутри функции: setLang вызывается раньше,
       чем выполнится присваивание на верхнем уровне */
    var pill = document.getElementById('lang-pill');
    if (!pill) return;
    var btn = document.querySelector('.lang button[data-lang="' + code + '"]');
    var first = document.querySelector('.lang button');
    if (!btn || !first) return;
    pill.style.width = btn.offsetWidth + 'px';
    pill.style.transform = 'translateX(' + (btn.offsetLeft - first.offsetLeft) + 'px)';
  }

  /* ============================================================
     Цифры набегают, когда блок появляется на экране
     ============================================================ */
  function countUp(el) {
    var target = parseInt(el.dataset.count, 10);
    if (reduced || !target) { el.textContent = target; return; }
    var start = null;
    var dur = 900;
    el.textContent = '0';
    function tick(now) {
      if (start === null) start = now;
      var p = Math.min((now - start) / dur, 1);
      /* замедление к концу — цифра «приезжает», а не щёлкает */
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased);
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  /* ============================================================
     Блик под курсором на стеклянных карточках
     ============================================================ */
  if (window.matchMedia('(hover: hover)').matches && !reduced) {
    document.querySelectorAll('.card').forEach(function (card) {
      var pending = false, mx = 0, my = 0;
      card.addEventListener('mousemove', function (e) {
        var rect = card.getBoundingClientRect();
        mx = e.clientX - rect.left;
        my = e.clientY - rect.top;
        if (pending) return;
        pending = true;
        requestAnimationFrame(function () {
          card.style.setProperty('--mx', mx + 'px');
          card.style.setProperty('--my', my + 'px');
          pending = false;
        });
      });
    });
  }

  /* ============================================================
     Вопросы раскрываются плавно
     Анимируем сам <details>, а не его содержимое: у закрытого
     <details> тело остаётся выложенным на полную высоту и просто
     обрезается, поэтому анимация по телу шла бы вхолостую.
     Движение прерываемое: повторный клик разворачивает его,
     а не ждёт окончания.
     ============================================================ */
  document.querySelectorAll('.faq details').forEach(function (d) {
    var summary = d.querySelector('summary');
    var body = d.querySelector('.faq-body');
    var closedH = d.getBoundingClientRect().height;   /* меряем до первого клика */
    var running = null;

    summary.addEventListener('click', function (e) {
      if (reduced) return;                 /* оставляем родное поведение */
      e.preventDefault();
      if (running) running.cancel();

      var startH = d.getBoundingClientRect().height;
      var opening = !d.open;

      if (opening) d.open = true;
      d.style.height = 'auto';
      var openH = d.getBoundingClientRect().height;
      d.style.height = startH + 'px';

      var endH = opening ? openH : closedH;

      running = d.animate(
        [{ height: startH + 'px' }, { height: endH + 'px' }],
        { duration: opening ? 340 : 250, easing: 'cubic-bezier(.22,.7,.28,1)' }
      );
      body.animate(
        [{ opacity: opening ? 0 : 1 }, { opacity: opening ? 1 : 0 }],
        { duration: opening ? 280 : 180, easing: 'ease-out', fill: 'none' }
      );

      running.onfinish = function () {
        running = null;
        d.style.height = '';
        if (!opening) d.open = false;
      };
    });
  });

  /* ============================================================
     Форма → Telegram
     Статике не нужен бэкенд: заявка открывается готовым сообщением.
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
    document.getElementById(field.id).addEventListener('blur', function (e) {
      if (e.target.value.trim()) clearError(field);
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

    if (status) {
      status.textContent = document.documentElement.lang === 'tg'
        ? TG['form.sent']
        : 'Открыли Telegram — осталось нажать «Отправить».';
    }
    form.reset();
  });
})();
