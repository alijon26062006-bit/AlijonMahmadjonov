/* =========================================================
   ПЕРЕВОДЫ — три языка
   =========================================================
   Меняй только текст в кавычках. Структуру не трогай:
   все три языка должны иметь одинаковый набор ключей.
   ========================================================= */

export const ru = {
  meta: {
    title: 'Alijon — Web, Telegram-боты и AI-решения',
    description:
      'Создаю современные веб-сайты, Telegram-ботов, Mini Apps и AI-решения. Full Stack разработка из Душанбе.',
    langName: 'Русский',
  },

  nav: {
    about: 'Обо мне',
    skills: 'Навыки',
    projects: 'Проекты',
    process: 'Процесс',
    contact: 'Контакты',
    order: 'Заказать проект',
  },

  preloader: {
    loading: 'Загрузка',
    enter: 'Войти',
    hint: 'Нажми, чтобы начать',
  },

  hero: {
    roles: ['Web Developer', 'Telegram Bot Developer', 'AI Enthusiast'],
    tagline: 'Создаю современные веб-сайты, Telegram-ботов, Mini Apps и AI-решения.',
    ctaOrder: 'Заказать проект',
    ctaProjects: 'Мои проекты',
    scroll: 'Листай вниз',
  },

  about: {
    eyebrow: 'Обо мне',
    title: 'Начинаю путь — но делаю это всерьёз.',
    p1: 'Меня зовут Али, в сети — Uways. Родом из Душанбе, сейчас работаю в Казахстане. Мне {age} лет, и я строю карьеру в разработке осознанно, а не по случайности.',
    p2: 'Занимаюсь веб-сайтами, Telegram-ботами и Mini Apps, автоматизацией и AI-решениями. Двигаюсь в сторону полноценной Full Stack разработки.',
    p3: 'Моя цель — стать сильным программистом мирового уровня и создавать цифровые продукты, которыми пользуются каждый день.',
    factAge: 'Возраст',
    factYears: '{age} лет',
    factCity: 'Родной город',
    factBased: 'Сейчас',
    factLangs: 'Языки',
    langsValue: 'Русский · Тоҷикӣ · English',
    factFocus: 'Направление',
    focusValue: 'Full Stack · AI',
  },

  skills: {
    eyebrow: 'Стек',
    title: 'Инструменты, которыми работаю.',
    lead: 'Не список ради списка — то, на чём реально собираю проекты.',
    frontend: 'Frontend',
    backend: 'Backend и данные',
    tools: 'Инструменты',
  },

  projects: {
    eyebrow: 'Работы',
    title: 'Проекты, которые я собрал.',
    lead: 'От мессенджера и маркетплейса до Telegram-ботов и AI.',
    view: 'Смотреть проект',
    soon: 'Скоро',
    stack: 'Стек',

    payom: {
      title: 'Payom Messenger',
      tagline: 'Мессенджер',
      description:
        'Мессенджер с обменом сообщениями в реальном времени: чаты, доставка сообщений, хранение истории. Самый большой мой проект по объёму логики.',
    },
    tajbozor: {
      title: 'TAJBOZOR',
      tagline: 'Маркетплейс',
      description:
        'Маркетплейс для Таджикистана: каталог товаров, поиск, карточки продавцов и заказы. Проект о том, как торговля переезжает в онлайн.',
    },
    cargo: {
      title: 'Telegram Cargo Bot',
      tagline: 'Telegram-бот',
      description:
        'Бот для грузоперевозок: приём заявок, расчёт, уведомления. Живёт прямо в Telegram — клиенту не нужно ничего устанавливать.',
    },
    miniapps: {
      title: 'Telegram Mini Apps',
      tagline: 'Mini Apps',
      description:
        'Полноценные веб-приложения внутри Telegram. Скорость мессенджера и возможности сайта в одном окне.',
    },
    ai: {
      title: 'AI-проекты',
      tagline: 'Искусственный интеллект',
      description:
        'Подключаю языковые модели к ботам и сервисам: ответы клиентам, обработка текста, автоматизация рутины.',
    },
    websites: {
      title: 'Веб-сайты',
      tagline: 'Web',
      description:
        'Современные сайты с анимацией и 3D — такие же, как тот, что ты сейчас смотришь.',
    },
  },

  process: {
    eyebrow: 'Как я работаю',
    title: 'Путь от идеи до запуска.',
    lead: 'Прозрачный процесс: ты всегда знаешь, на каком этапе проект.',
    steps: [
      { title: 'Идея', text: 'Разбираемся, какую задачу решает продукт и кто им будет пользоваться.' },
      { title: 'Дизайн', text: 'Собираю интерфейс и согласовываю его до начала разработки.' },
      { title: 'Разработка', text: 'Пишу код: фронтенд, бэкенд, база данных, интеграции.' },
      { title: 'Тестирование', text: 'Проверяю на телефонах и компьютерах, ловлю ошибки до запуска.' },
      { title: 'Запуск', text: 'Разворачиваю на хостинге, подключаю домен и аналитику.' },
      { title: 'Поддержка', text: 'Остаюсь на связи: правки, обновления, новые функции.' },
    ],
  },

  order: {
    eyebrow: 'Заявка',
    title: 'Расскажи о проекте.',
    lead: 'Отвечу в Telegram. Обычно в течение дня.',
    name: 'Имя',
    namePlaceholder: 'Как к тебе обращаться',
    telegram: 'Telegram',
    telegramPlaceholder: '@username',
    project: 'Описание проекта',
    projectPlaceholder: 'Что нужно сделать и для кого',
    budget: 'Бюджет',
    budgetPlaceholder: 'Например, 300–500 $',
    deadline: 'Срок',
    deadlinePlaceholder: 'Например, 3 недели',
    submit: 'Отправить заявку',
    sending: 'Отправляю…',
    success: 'Заявка собрана — открываю Telegram.',
    optional: 'необязательно',
    errors: {
      nameShort: 'Введи имя — минимум 2 символа',
      telegramShort: 'Укажи Telegram для связи',
      projectShort: 'Опиши задачу хотя бы в двух словах — от 10 символов',
    },
  },

  contact: {
    eyebrow: 'Контакты',
    title: 'Давай построим что-то стоящее.',
    lead: 'Пиши в любой удобный канал — отвечаю быстро.',
    copy: 'Скопировать',
    copied: 'Скопировано',
  },

  footer: {
    rights: 'Все права защищены',
    built: 'Собрано на Next.js, Three.js и GSAP',
  },

  sound: {
    on: 'Включить звук',
    off: 'Выключить звук',
  },
};

export const tg = {
  meta: {
    title: 'Alijon — Вебсайт, Telegram-бот ва ҳалли AI',
    description:
      'Вебсайтҳои муосир, Telegram-ботҳо, Mini Apps ва ҳалли AI месозам. Таҳияи Full Stack аз Душанбе.',
    langName: 'Тоҷикӣ',
  },

  nav: {
    about: 'Дар бораи ман',
    skills: 'Малакаҳо',
    projects: 'Лоиҳаҳо',
    process: 'Раванд',
    contact: 'Тамос',
    order: 'Лоиҳа фармоиш диҳед',
  },

  preloader: {
    loading: 'Боргирӣ',
    enter: 'Ворид шудан',
    hint: 'Барои оғоз зер кунед',
  },

  hero: {
    roles: ['Web Developer', 'Telegram Bot Developer', 'AI Enthusiast'],
    tagline: 'Вебсайтҳои муосир, Telegram-ботҳо, Mini Apps ва ҳалли AI месозам.',
    ctaOrder: 'Лоиҳа фармоиш диҳед',
    ctaProjects: 'Лоиҳаҳои ман',
    scroll: 'Ба поён',
  },

  about: {
    eyebrow: 'Дар бораи ман',
    title: 'Роҳро оғоз мекунам — вале ҷиддӣ.',
    p1: 'Номи ман Алӣ, дар шабака — Uways. Зодаи Душанбе ҳастам, ҳоло дар Қазоқистон кор мекунам. Ман {age}-сола ҳастам ва ин роҳро бошуурона интихоб кардаам.',
    p2: 'Бо вебсайтҳо, Telegram-ботҳо ва Mini Apps, автоматизатсия ва ҳалли AI машғулам. Тадриҷан ба таҳияи пурраи Full Stack мегузарам.',
    p3: 'Ҳадафи ман — барномасози сатҳи ҷаҳонӣ шудан ва маҳсулоти рақамӣ сохтан, ки мардум ҳар рӯз истифода мебаранд.',
    factAge: 'Синну сол',
    factYears: '{age} сола',
    factCity: 'Шаҳри зодгоҳ',
    factBased: 'Ҳоло дар',
    factLangs: 'Забонҳо',
    langsValue: 'Русский · Тоҷикӣ · English',
    factFocus: 'Самт',
    focusValue: 'Full Stack · AI',
  },

  skills: {
    eyebrow: 'Стек',
    title: 'Абзорҳое, ки бо онҳо кор мекунам.',
    lead: 'На рӯйхат барои рӯйхат — ин чизест, ки лоиҳаҳоям аз он сохта мешаванд.',
    frontend: 'Frontend',
    backend: 'Backend ва маълумот',
    tools: 'Абзорҳо',
  },

  projects: {
    eyebrow: 'Корҳо',
    title: 'Лоиҳаҳое, ки сохтаам.',
    lead: 'Аз мессенҷер ва бозори онлайн то Telegram-ботҳо ва AI.',
    view: 'Дидани лоиҳа',
    soon: 'Ба зудӣ',
    stack: 'Стек',

    payom: {
      title: 'Payom Messenger',
      tagline: 'Мессенҷер',
      description:
        'Мессенҷер бо мубодилаи паём дар вақти воқеӣ: чатҳо, расонидани паёмҳо, нигоҳдории таърих. Калонтарин лоиҳаи ман аз рӯи мантиқ.',
    },
    tajbozor: {
      title: 'TAJBOZOR',
      tagline: 'Бозори онлайн',
      description:
        'Бозори онлайн барои Тоҷикистон: феҳристи молҳо, ҷустуҷӯ, саҳифаи фурӯшандагон ва фармоишҳо. Лоиҳа дар бораи гузариши савдо ба онлайн.',
    },
    cargo: {
      title: 'Telegram Cargo Bot',
      tagline: 'Telegram-бот',
      description:
        'Бот барои боркашонӣ: қабули дархостҳо, ҳисоб, огоҳиномаҳо. Дар дохили Telegram кор мекунад — мизоҷ чизе насб намекунад.',
    },
    miniapps: {
      title: 'Telegram Mini Apps',
      tagline: 'Mini Apps',
      description:
        'Барномаҳои пурраи веб дар дохили Telegram. Суръати мессенҷер ва имконоти вебсайт дар як тиреза.',
    },
    ai: {
      title: 'Лоиҳаҳои AI',
      tagline: 'Зеҳни сунъӣ',
      description:
        'Моделҳои забониро ба ботҳо ва хидматҳо пайваст мекунам: ҷавоб ба мизоҷон, коркарди матн, автоматизатсияи корҳои такрорӣ.',
    },
    websites: {
      title: 'Вебсайтҳо',
      tagline: 'Web',
      description: 'Сайтҳои муосир бо аниматсия ва 3D — монанди ҳамин, ки ҳоло мебинед.',
    },
  },

  process: {
    eyebrow: 'Тарзи кори ман',
    title: 'Аз ғоя то оғоз.',
    lead: 'Раванди шаффоф: шумо ҳамеша медонед, ки лоиҳа дар кадом марҳила аст.',
    steps: [
      { title: 'Ғоя', text: 'Муайян мекунем, ки маҳсулот кадом масъаларо ҳал мекунад ва кӣ онро истифода мебарад.' },
      { title: 'Дизайн', text: 'Интерфейсро месозам ва пеш аз оғози таҳия мувофиқа мекунам.' },
      { title: 'Таҳия', text: 'Код менависам: frontend, backend, базаи маълумот, интегратсияҳо.' },
      { title: 'Санҷиш', text: 'Дар телефон ва компютер месанҷам, хатоҳоро пеш аз оғоз пайдо мекунам.' },
      { title: 'Оғоз', text: 'Ба хостинг мегузорам, домен ва таҳлилро пайваст мекунам.' },
      { title: 'Дастгирӣ', text: 'Дар тамос мемонам: ислоҳҳо, навсозиҳо ва имконоти нав.' },
    ],
  },

  order: {
    eyebrow: 'Дархост',
    title: 'Дар бораи лоиҳаатон нақл кунед.',
    lead: 'Дар Telegram ҷавоб медиҳам — одатан дар давоми як рӯз.',
    name: 'Ном',
    namePlaceholder: 'Шуморо чӣ гуна муроҷиат кунам',
    telegram: 'Telegram',
    telegramPlaceholder: '@username',
    project: 'Тавсифи лоиҳа',
    projectPlaceholder: 'Чӣ бояд сохта шавад ва барои кӣ',
    budget: 'Буҷа',
    budgetPlaceholder: 'Масалан, 300–500 $',
    deadline: 'Мӯҳлат',
    deadlinePlaceholder: 'Масалан, 3 ҳафта',
    submit: 'Фиристодани дархост',
    sending: 'Фиристода истодаам…',
    success: 'Дархост тайёр — Telegram кушода мешавад.',
    optional: 'ихтиёрӣ',
    errors: {
      nameShort: 'Номро ворид кунед — камаш 2 аломат',
      telegramShort: 'Telegram-ро барои тамос нависед',
      projectShort: 'Масъаларо мухтасар тавсиф кунед — камаш 10 аломат',
    },
  },

  contact: {
    eyebrow: 'Тамос',
    title: 'Биёед чизи арзанда созем.',
    lead: 'Ба ҳар канали қулай нависед — зуд ҷавоб медиҳам.',
    copy: 'Нусха бардоштан',
    copied: 'Нусха бардошта шуд',
  },

  footer: {
    rights: 'Ҳамаи ҳуқуқҳо ҳифз шудаанд',
    built: 'Сохта шудааст бо Next.js, Three.js ва GSAP',
  },

  sound: {
    on: 'Садоро фаъол кардан',
    off: 'Садоро хомӯш кардан',
  },
};

export const en = {
  meta: {
    title: 'Alijon — Web, Telegram Bots and AI Solutions',
    description:
      'I build modern websites, Telegram bots, Mini Apps and AI solutions. Full Stack development from Dushanbe.',
    langName: 'English',
  },

  nav: {
    about: 'About',
    skills: 'Skills',
    projects: 'Projects',
    process: 'Process',
    contact: 'Contact',
    order: 'Start a project',
  },

  preloader: {
    loading: 'Loading',
    enter: 'Enter',
    hint: 'Click to begin',
  },

  hero: {
    roles: ['Web Developer', 'Telegram Bot Developer', 'AI Enthusiast'],
    tagline: 'I build modern websites, Telegram bots, Mini Apps and AI solutions.',
    ctaOrder: 'Start a project',
    ctaProjects: 'See my work',
    scroll: 'Scroll down',
  },

  about: {
    eyebrow: 'About me',
    title: 'Early in the journey — and serious about it.',
    p1: "My name is Ali, online I go by Uways. I'm from Dushanbe and currently work in Kazakhstan. I'm {age}, and I'm building this career on purpose, not by accident.",
    p2: 'I work on websites, Telegram bots and Mini Apps, automation and AI solutions — moving steadily toward full stack development.',
    p3: 'My goal is to become a world-class developer and build digital products people actually use every day.',
    factAge: 'Age',
    factYears: '{age} years',
    factCity: 'Hometown',
    factBased: 'Based in',
    factLangs: 'Languages',
    langsValue: 'Русский · Тоҷикӣ · English',
    factFocus: 'Focus',
    focusValue: 'Full Stack · AI',
  },

  skills: {
    eyebrow: 'Stack',
    title: 'The tools I actually work with.',
    lead: 'Not a list for the sake of it — this is what my projects are built on.',
    frontend: 'Frontend',
    backend: 'Backend and data',
    tools: 'Tools',
  },

  projects: {
    eyebrow: 'Work',
    title: 'Projects I have built.',
    lead: 'From a messenger and a marketplace to Telegram bots and AI.',
    view: 'View project',
    soon: 'Soon',
    stack: 'Stack',

    payom: {
      title: 'Payom Messenger',
      tagline: 'Messenger',
      description:
        'A messenger with real-time conversations: chats, message delivery, stored history. The largest project I have built in terms of logic.',
    },
    tajbozor: {
      title: 'TAJBOZOR',
      tagline: 'Marketplace',
      description:
        'A marketplace for Tajikistan: product catalogue, search, seller profiles and orders. A project about moving local trade online.',
    },
    cargo: {
      title: 'Telegram Cargo Bot',
      tagline: 'Telegram bot',
      description:
        'A freight bot: takes requests, calculates, sends notifications. It lives inside Telegram, so the client installs nothing.',
    },
    miniapps: {
      title: 'Telegram Mini Apps',
      tagline: 'Mini Apps',
      description:
        'Full web apps running inside Telegram — the speed of a messenger with the capability of a website.',
    },
    ai: {
      title: 'AI projects',
      tagline: 'Artificial intelligence',
      description:
        'Connecting language models to bots and services: customer replies, text processing, routine automation.',
    },
    websites: {
      title: 'Websites',
      tagline: 'Web',
      description: 'Modern sites with motion and 3D — much like the one you are looking at.',
    },
  },

  process: {
    eyebrow: 'How I work',
    title: 'From idea to launch.',
    lead: 'A transparent process: you always know which stage the project is at.',
    steps: [
      { title: 'Idea', text: 'We work out what problem the product solves and who will use it.' },
      { title: 'Design', text: 'I build the interface and agree on it before any code is written.' },
      { title: 'Development', text: 'Writing the code: frontend, backend, database, integrations.' },
      { title: 'Testing', text: 'Checked on phones and desktops, catching issues before launch.' },
      { title: 'Launch', text: 'Deployed to hosting, with domain and analytics connected.' },
      { title: 'Support', text: 'I stay available: fixes, updates and new features.' },
    ],
  },

  order: {
    eyebrow: 'Request',
    title: 'Tell me about your project.',
    lead: "I'll reply on Telegram, usually within a day.",
    name: 'Name',
    namePlaceholder: 'What should I call you',
    telegram: 'Telegram',
    telegramPlaceholder: '@username',
    project: 'Project description',
    projectPlaceholder: 'What needs building, and who for',
    budget: 'Budget',
    budgetPlaceholder: 'For example, $300–500',
    deadline: 'Timeline',
    deadlinePlaceholder: 'For example, 3 weeks',
    submit: 'Send request',
    sending: 'Sending…',
    success: 'Request ready — opening Telegram.',
    optional: 'optional',
    errors: {
      nameShort: 'Enter your name — at least 2 characters',
      telegramShort: 'Add your Telegram so I can reply',
      projectShort: 'Describe the task briefly — at least 10 characters',
    },
  },

  contact: {
    eyebrow: 'Contact',
    title: "Let's build something worth building.",
    lead: 'Reach out on any channel — I reply quickly.',
    copy: 'Copy',
    copied: 'Copied',
  },

  footer: {
    rights: 'All rights reserved',
    built: 'Built with Next.js, Three.js and GSAP',
  },

  sound: {
    on: 'Turn sound on',
    off: 'Turn sound off',
  },
};

export const dicts = { ru, tg, en };
export const LANGS = ['ru', 'tg', 'en'];
export const LANG_LABELS = { ru: 'RU', tg: 'TJ', en: 'EN' };
