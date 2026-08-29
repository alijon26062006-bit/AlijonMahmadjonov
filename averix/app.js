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
     Замер этой же страницы
     Цифры не вписаны в разметку — их измеряет браузер посетителя.
     Если браузер не отдаёт размеры (например, файл открыт с диска),
     пункт убирается, а не показывает выдуманное значение.
     ============================================================ */
  function measure() {
    var nav = performance.getEntriesByType('navigation')[0];
    var res = performance.getEntriesByType('resource');
    if (!nav) return;

    var bytes = nav.transferSize || 0;
    res.forEach(function (r) { bytes += r.transferSize || 0; });

    set('weight', bytes ? Math.round(bytes / 1024) + ' КБ' : null);
    set('requests', res.length + 1);

    var ms = nav.domContentLoadedEventEnd - nav.startTime;
    set('time', ms > 0 ? (ms < 1000 ? Math.round(ms) + ' мс' : (ms / 1000).toFixed(1) + ' с') : null);
  }

  function set(metric, value) {
    var el = document.querySelector('[data-metric="' + metric + '"]');
    if (!el) return;
    if (value === null) {
      var row = el.closest('div');
      if (row) row.remove();
      return;
    }
    el.textContent = value;
  }

  if (document.readyState === 'complete') measure();
  else window.addEventListener('load', function () { setTimeout(measure, 0); });

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

    'measure.title': 'Ченкунии ҳамин саҳифа дар браузери шумо',
    'measure.weight': 'вазн',
    'measure.time': 'боркунӣ',
    'measure.requests': 'дархостҳо',
    'measure.contrast': 'контрасти матн',

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
    try { localStorage.setItem('averix-lang', code); } catch (e) {}
  }

  langButtons.forEach(function (b) {
    b.addEventListener('click', function () { setLang(b.dataset.lang); });
  });

  try {
    var saved = localStorage.getItem('averix-lang');
    if (saved === 'tg') setLang('tg');
  } catch (e) {}

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

  function closeMenu() {
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

  var year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();

  /* ============================================================
     Появление блоков
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
