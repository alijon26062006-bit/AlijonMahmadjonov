/* ===========================================================
   Админ-панель Alijon. Правит data/*.json и коммитит их на GitHub.
   =========================================================== */

const { h, icon, clear, toast, confirmAction, group } = UI;

const FILES = {
  profile:  'data/profile.json',
  timeline: 'data/timeline.json',
  projects: 'data/projects.json',
  diary:    'data/diary.json'
};

const State = {
  files: {},          // ключ -> { data, sha, dirty }
  view: 'profile',
  editing: null,      // индекс редактируемого проекта
  assets: [],
  busy: false
};

const app = document.getElementById('app');

/* --- Работа с данными ------------------------------------------ */

const data = key => State.files[key]?.data;
const isDirty = key => Boolean(State.files[key]?.dirty);
const dirtyKeys = () => Object.keys(State.files).filter(isDirty);

function touch(key) {
  if (State.files[key]) State.files[key].dirty = true;
  updateTopbar();
}

/** Меняет значение по пути 'about.title' и помечает файл изменённым. */
function setIn(key, path, value) {
  const parts = path.split('.');
  let node = data(key);
  for (const part of parts.slice(0, -1)) node = node[part];
  node[parts.at(-1)] = value;
  touch(key);
}

const getIn = (key, path) =>
  path.split('.').reduce((acc, part) => (acc == null ? acc : acc[part]), data(key));

function moveItem(arr, from, to) {
  if (to < 0 || to >= arr.length) return;
  arr.splice(to, 0, arr.splice(from, 1)[0]);
}

/* --- Экран входа ------------------------------------------------ */

function showLogin(message) {
  clear(app);
  const cfg = GH.cfg();

  const tokenInput = h('input', {
    class: 'input mono',
    attrs: { type: 'password', placeholder: 'github_pat_...', autocomplete: 'off', spellcheck: 'false' }
  });

  const enter = async () => {
    const value = tokenInput.value.trim();
    if (!value) { toast('Вставь токен в поле.', 'error'); return; }
    GH.saveToken(value);
    button.disabled = true;
    button.textContent = 'Проверяю...';
    try {
      const info = await GH.verify();
      if (!info.canWrite) {
        GH.clearToken();
        showLogin('Токен читает репозиторий, но не может в него писать. Нужно право Contents: read and write.');
        return;
      }
      toast('Токен подошёл: ' + info.name);
      loadAll();
    } catch (err) {
      GH.clearToken();
      showLogin(err.message);
    }
  };

  const button = h('button', {
    class: 'btn btn-solid', attrs: { type: 'submit' }
  }, [icon('key'), h('span', { text: 'Войти' })]);

  app.appendChild(h('div', { class: 'login' }, [
    h('form', {
      class: 'login-card',
      on: { submit: e => { e.preventDefault(); enter(); } }
    }, [
      h('h1', { text: 'Панель управления' }),
      h('p', { class: 'hint', text: 'Отсюда ты публикуешь проекты, пишешь дневник и правишь тексты сайта.' }),

      message ? h('div', { class: 'warn' }, [icon('alert'), h('span', { text: message })]) : null,

      h('div', { class: 'login-steps' }, [
        h('strong', { text: 'Как получить токен — один раз, 2 минуты:' }),
        h('ol', {}, [
          h('li', {}, [
            h('span', { text: 'Открой ' }),
            h('a', {
              text: 'страницу создания токена',
              attrs: {
                href: 'https://github.com/settings/personal-access-tokens/new',
                target: '_blank', rel: 'noopener'
              }
            })
          ]),
          h('li', { text: 'Repository access → Only select repositories → выбери ' + cfg.repo }),
          h('li', {}, [
            h('span', { text: 'Permissions → Repository permissions → ' }),
            h('code', { text: 'Contents' }),
            h('span', { text: ' поставь ' }),
            h('code', { text: 'Read and write' })
          ]),
          h('li', { text: 'Expiration — 90 дней. Создай токен и вставь сюда.' })
        ])
      ]),

      h('div', { class: 'field' }, [
        h('label', { text: 'Токен GitHub', attrs: { for: (tokenInput.id = 'token') } }),
        tokenInput,
        h('p', { class: 'hint', text: 'Токен сохранится только в этом браузере. На чужом устройстве его не вводи.' })
      ]),

      button,

      h('div', { class: 'warn' }, [
        icon('alert'),
        h('span', { text: 'Токен даёт доступ только к этому репозиторию. Если он попадёт к чужому — испортят сайт, но не аккаунт. Поэтому и срок 90 дней.' })
      ])
    ])
  ]));

  tokenInput.focus();
}

/* --- Загрузка --------------------------------------------------- */

function showLoading(text = 'Загружаю данные с GitHub...') {
  clear(app);
  app.appendChild(h('div', { class: 'loading' }, [h('div', { class: 'spinner' }), h('p', { text })]));
}

async function loadAll() {
  showLoading();
  try {
    const entries = await Promise.all(Object.entries(FILES).map(async ([key, path]) => {
      const file = await GH.getFile(path);
      if (!file) throw new Error(`Файл ${path} не найден в ветке ${GH.cfg().branch}. Проверь ветку в Настройках.`);
      return [key, { data: JSON.parse(file.text), sha: file.sha, dirty: false }];
    }));
    State.files = Object.fromEntries(entries);
    renderShell();
  } catch (err) {
    if (err instanceof GH.GHError && err.status === 401) { GH.clearToken(); showLogin(err.message); return; }
    clear(app);
    app.appendChild(h('div', { class: 'loading' }, [
      icon('alert'),
      h('p', { text: err.message }),
      h('button', { class: 'btn btn-line', text: 'Попробовать снова', on: { click: loadAll } }),
      h('button', { class: 'btn btn-ghost', text: 'Сменить токен', on: { click: () => { GH.clearToken(); showLogin(); } } })
    ]));
  }
}

/* --- Каркас ------------------------------------------------------ */

const NAV = [
  { id: 'profile',  label: 'Профиль',  icon: 'user',     file: 'profile' },
  { id: 'projects', label: 'Проекты',  icon: 'folder',   file: 'projects' },
  { id: 'timeline', label: 'Мой путь', icon: 'route',    file: 'timeline' },
  { id: 'diary',    label: 'Дневник',  icon: 'book',     file: 'diary' },
  { id: 'media',    label: 'Медиа',    icon: 'image' },
  { id: 'settings', label: 'Настройки', icon: 'settings' }
];

function renderShell() {
  clear(app);
  const cfg = GH.cfg();

  const nav = h('nav', {}, NAV.map(item => h('button', {
    attrs: { type: 'button', 'aria-current': State.view === item.id ? 'page' : null },
    on: { click: () => { State.view = item.id; State.editing = null; renderShell(); } }
  }, [
    icon(item.icon),
    h('span', { text: item.label }),
    item.file && isDirty(item.file) ? h('span', { class: 'dot', attrs: { title: 'Есть несохранённые правки' } }) : null
  ])));

  const side = h('aside', { class: 'side' }, [
    h('div', { class: 'side-brand' }, [h('span', { text: 'Alijon' }), h('span', { class: 'accent', text: '.' })]),
    nav,
    h('div', { class: 'side-foot' }, [
      h('a', { attrs: { href: GH.siteUrl(), target: '_blank', rel: 'noopener' } },
        [icon('external'), h('span', { text: 'Открыть сайт' })]),
      h('button', {
        attrs: { type: 'button' },
        on: { click: async () => {
          if (dirtyKeys().length && !await confirmAction('Есть неопубликованные правки. Выйти и потерять их?', 'Выйти')) return;
          GH.clearToken(); State.files = {}; showLogin();
        }}
      }, [icon('logout'), h('span', { text: 'Выйти' })])
    ])
  ]);

  const view = h('div', { class: 'view', id: 'view' });
  const main = h('main', { class: 'main' }, [buildTopbar(cfg), view]);

  app.appendChild(h('div', { class: 'shell' }, [side, main]));
  renderView();
}

let topbarRefs = {};

function buildTopbar(cfg) {
  const counter = h('span', { class: 'dirty-count', attrs: { hidden: true } });
  const publishBtn = h('button', {
    class: 'btn btn-solid', attrs: { type: 'button', disabled: true }, on: { click: publish }
  }, [icon('save'), h('span', { text: 'Опубликовать' })]);
  const reloadBtn = h('button', {
    class: 'icon-btn', attrs: { type: 'button', title: 'Перезагрузить с GitHub', 'aria-label': 'Перезагрузить с GitHub' },
    on: { click: async () => {
      if (dirtyKeys().length && !await confirmAction('Перезагрузка сотрёт несохранённые правки. Продолжить?', 'Перезагрузить')) return;
      loadAll();
    }}
  }, [icon('refresh')]);

  topbarRefs = { counter, publishBtn };
  const bar = h('header', { class: 'topbar' }, [
    h('span', { class: 'repo', text: `${cfg.owner}/${cfg.repo} · ${cfg.branch}` }),
    counter, reloadBtn, publishBtn
  ]);
  queueMicrotask(updateTopbar);
  return bar;
}

function updateTopbar() {
  const n = dirtyKeys().length;
  if (topbarRefs.counter) {
    topbarRefs.counter.textContent = n === 1 ? '1 файл изменён' : `${n} файла изменено`;
    topbarRefs.counter.hidden = n === 0;
  }
  if (topbarRefs.publishBtn) topbarRefs.publishBtn.disabled = n === 0 || State.busy;

  // Точки в боковом меню
  for (const [i, button] of [...document.querySelectorAll('.side nav button')].entries()) {
    const item = NAV[i];
    const dot = button.querySelector('.dot');
    const need = item.file && isDirty(item.file);
    if (need && !dot) button.appendChild(h('span', { class: 'dot' }));
    if (!need && dot) dot.remove();
  }
}

function renderView() {
  const view = document.getElementById('view');
  if (!view) return;
  clear(view);
  const render = {
    profile: viewProfile, projects: viewProjects, timeline: viewTimeline,
    diary: viewDiary, media: viewMedia, settings: viewSettings
  }[State.view];
  render(view);
  // Прокрутка именно окна: scrollIntoView загонял бы заголовок под липкую шапку
  window.scrollTo({ top: 0 });
}

/* --- Публикация --------------------------------------------------- */

async function publish() {
  const keys = dirtyKeys();
  if (!keys.length || State.busy) return;

  State.busy = true;
  updateTopbar();
  topbarRefs.publishBtn.textContent = 'Публикую...';

  try {
    for (const key of keys) {
      const file = State.files[key];
      const text = JSON.stringify(file.data, null, 2) + '\n';
      file.sha = await GH.putFile(FILES[key], text, file.sha, `Обновить ${FILES[key]} через панель управления`);
      file.dirty = false;
    }
    toast('Готово. Сайт обновится примерно через минуту.');
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    State.busy = false;
    clear(topbarRefs.publishBtn);
    topbarRefs.publishBtn.append(icon('save'), h('span', { text: 'Опубликовать' }));
    updateTopbar();
    renderView();
  }
}

/* --- Предупреждение при уходе со страницы -------------------------- */

window.addEventListener('beforeunload', e => {
  if (dirtyKeys().length) { e.preventDefault(); e.returnValue = ''; }
});

/* --- Старт --------------------------------------------------------- */

async function injectSprite() {
  try {
    const res = await fetch('../icons/sprite.svg', { cache: 'force-cache' });
    if (!res.ok) return;
    const holder = h('div', { attrs: { 'aria-hidden': 'true' } });
    holder.innerHTML = await res.text();
    holder.style.display = 'none';
    document.body.prepend(holder);
  } catch (_) {}
}

injectSprite();
if (GH.token()) loadAll(); else showLogin();

/* ===========================================================
   Экраны. Формы описываются схемой, а не рисуются руками —
   иначе форма профиля превратилась бы в тысячу строк.
   =========================================================== */

const ICON_OPTIONS = ['bot', 'globe', 'cpu', 'sparkles', 'code', 'route', 'user',
                      'check-circle', 'book', 'folder', 'telegram', 'instagram', 'github']
  .map(v => ({ value: v, label: v }));

const LEVEL_OPTIONS = [
  { value: 'learning',  label: 'Учу' },
  { value: 'able',      label: 'Умею' },
  { value: 'confident', label: 'Уверенно' }
];

const STATUS_OPTIONS = [
  { value: 'idea', label: 'Идея' },
  { value: 'wip',  label: 'В работе' },
  { value: 'done', label: 'Готов' }
];

/** Собирает одно поле формы по описанию. container[def.k] — само значение. */
function fieldFor(fileKey, container, def) {
  const save = value => { container[def.k] = value; touch(fileKey); };

  switch (def.type) {
    case 'bi':
    case 'bi-area':
      return UI.bilingual({
        label: def.l, value: container[def.k], hint: def.hint,
        multiline: def.type === 'bi-area',
        onInput: save
      });

    case 'select':
      return UI.select({
        label: def.l, value: container[def.k], options: def.options, hint: def.hint,
        onChange: save
      });

    case 'check':
      return UI.checkbox({ label: def.l, value: container[def.k], onChange: save });

    case 'media':
      return mediaField(fileKey, container, def);

    case 'csv':
      return UI.text({
        label: def.l, value: (container[def.k] || []).join(', '), hint: def.hint || 'Через запятую',
        onInput: v => save(v.split(',').map(s => s.trim()).filter(Boolean))
      });

    case 'headline':
      return headlineField(fileKey, container, def);

    case 'color':
      return UI.text({ label: def.l, value: container[def.k], hint: 'Например #5FD9FF', mono: true, onInput: save });

    default:
      return UI.text({
        label: def.l, value: container[def.k], hint: def.hint, mono: def.mono,
        multiline: def.type === 'area', onInput: save
      });
  }
}

/** Заголовок с градиентным словом: у каждого языка свои «до» и «выделенное». */
function headlineField(fileKey, container, def) {
  const value = container[def.k] || {};
  const langs = [['tj', 'Тоҷикӣ'], ['ru', 'Русский']];

  return UI.h('div', { class: 'field' }, [
    UI.h('span', { class: 'field-label', text: def.l }),
    UI.h('p', { class: 'hint', text: 'Второе поле — слово, которое зальётся градиентом.' }),
    ...langs.map(([code, caption]) => UI.h('div', { class: 'group-body', attrs: { style: 'padding:0;margin-top:12px' } }, [
      UI.h('span', { class: 'bi-lang', text: caption }),
      UI.h('div', { class: 'bi' }, [
        UI.text({
          label: 'Обычный текст', value: (value[code] || {}).before,
          onInput: v => { container[def.k][code] = { ...(value[code] || {}), before: v }; touch(fileKey); }
        }),
        UI.text({
          label: 'Слово градиентом', value: (value[code] || {}).accent,
          onInput: v => { container[def.k][code] = { ...(value[code] || {}), accent: v }; touch(fileKey); }
        })
      ])
    ]))
  ]);
}

/** Путь к картинке + кнопка выбора из загруженных. */
function mediaField(fileKey, container, def) {
  const input = UI.h('input', {
    class: 'input mono', props: { value: container[def.k] ?? '' },
    attrs: { type: 'text', placeholder: 'assets/фото.jpg' },
    on: { input: e => { container[def.k] = e.target.value; touch(fileKey); } }
  });
  const id = input.id = 'm' + def.k + Math.random().toString(36).slice(2, 7);

  return UI.h('div', { class: 'field' }, [
    UI.h('label', { text: def.l, attrs: { for: id } }),
    UI.h('div', { attrs: { style: 'display:flex;gap:8px;align-items:flex-start' } }, [
      input,
      UI.h('button', {
        class: 'btn btn-line', attrs: { type: 'button', style: 'flex:none' },
        on: { click: async () => {
          const chosen = await pickMedia();
          if (chosen) { input.value = chosen; container[def.k] = chosen; touch(fileKey); }
        }}
      }, [UI.icon('image'), UI.h('span', { text: 'Выбрать' })])
    ]),
    def.hint ? UI.h('p', { class: 'hint', text: def.hint }) : null
  ]);
}

/** Окно выбора картинки из папки assets. */
function pickMedia() {
  return new Promise(async resolve => {
    const grid = UI.h('div', { class: 'media-grid' });
    const close = value => { overlay.remove(); document.body.style.overflow = ''; resolve(value); };
    const dialog = UI.h('div', {
      class: 'dialog', attrs: { role: 'dialog', 'aria-modal': 'true', style: 'width:min(100%,720px)' }
    }, [
      UI.h('h2', { text: 'Выбери картинку', attrs: { style: 'margin:0 0 16px;font-size:1.1rem' } }),
      grid,
      UI.h('div', { class: 'dialog-actions', attrs: { style: 'margin-top:24px' } }, [
        UI.h('button', { class: 'btn btn-ghost', text: 'Отмена', on: { click: () => close(null) } })
      ])
    ]);
    const overlay = UI.h('div', {
      class: 'overlay', on: { click: e => { if (e.target === overlay) close(null); } }
    }, [dialog]);
    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';

    grid.appendChild(UI.h('p', { class: 'hint', text: 'Загружаю список...' }));
    try {
      const files = (await GH.listDir('assets'))
        .filter(f => /\.(jpe?g|png|webp|gif|avif)$/i.test(f.name));
      UI.clear(grid);
      if (!files.length) {
        grid.appendChild(UI.h('p', { class: 'hint', text: 'В папке assets пока нет картинок. Загрузи их в разделе «Медиа».' }));
      }
      for (const file of files) {
        grid.appendChild(UI.h('button', {
          class: 'media-tile', attrs: { type: 'button' }, on: { click: () => close('assets/' + file.name) }
        }, [
          UI.h('img', { attrs: { src: file.download_url, alt: '', loading: 'lazy' } }),
          UI.h('figcaption', { text: file.name })
        ]));
      }
    } catch (err) {
      UI.clear(grid);
      grid.appendChild(UI.h('p', { class: 'hint', text: err.message }));
    }
  });
}

/** Строит редактор массива по схеме элемента. */
function listFor(fileKey, arr, itemSchema, opts = {}) {
  const rerender = () => { touch(fileKey); renderView(); };
  return UI.list({
    items: arr,
    addLabel: opts.addLabel,
    emptyText: opts.emptyText,
    titleOf: opts.titleOf,
    onAdd: () => { arr.push(structuredClone(opts.blank)); rerender(); },
    onRemove: async i => {
      if (await confirmAction('Удалить этот пункт?')) { arr.splice(i, 1); rerender(); }
    },
    onMove: (from, to) => { moveItem(arr, from, to); rerender(); },
    renderItem: (item, i) => {
      // Список абзацев хранит {tj, ru} прямо в элементе, без вложенного ключа
      if (itemSchema === 'self-bi') {
        return UI.h('div', {}, [UI.bilingual({
          label: 'Текст', value: item, multiline: true,
          onInput: value => { arr[i] = value; touch(fileKey); }
        })]);
      }
      return UI.h('div', {}, itemSchema.map(def => fieldFor(fileKey, item, def)));
    }
  });
}

/* --- Экран: Профиль --------------------------------------------- */

function viewProfile(view) {
  const p = data('profile');

  view.appendChild(UI.sectionHead('Профиль',
    'Всё, что человек читает о тебе на сайте. Слева таджикский, справа русский.'));

  const F = def => fieldFor('profile', def.on, def);

  view.append(
    group('Главное', [
      F({ on: p.meta, k: 'name', l: 'Имя на сайте' }),
      F({ on: p.meta, k: 'photo', l: 'Твоё фото', type: 'media', hint: 'Показывается в блоке «Кто я»' }),
      F({ on: p.meta, k: 'video', l: 'Видео на первом экране', type: 'media', hint: 'Оставь пустым, чтобы показывать только кадр' }),
      F({ on: p.meta, k: 'videoPoster', l: 'Кадр для первого экрана', type: 'media' }),
      F({ on: p.meta, k: 'defaultLang', l: 'Какой язык открывается первым', type: 'select',
          options: [{ value: 'tj', label: 'Таджикский' }, { value: 'ru', label: 'Русский' }] })
    ], true),

    group('Первый экран', [
      F({ on: p.hero, k: 'badge', l: 'Метка над заголовком', type: 'bi' }),
      F({ on: p.hero, k: 'headline', l: 'Главный заголовок', type: 'headline' }),
      F({ on: p.hero, k: 'tagline', l: 'Подпись под заголовком', type: 'bi-area' }),
      F({ on: p.hero, k: 'ctaPrimary', l: 'Кнопка в Telegram', type: 'bi' }),
      F({ on: p.hero, k: 'ctaSecondary', l: 'Вторая кнопка', type: 'bi' }),
      F({ on: p.hero, k: 'ticker', l: 'Бегущая строка', type: 'csv' }),
      UI.h('span', { class: 'field-label', text: 'Цифры' }),
      listFor('profile', p.hero.stats, [
        { k: 'v', l: 'Число' },
        { k: 'k', l: 'Подпись', type: 'bi' }
      ], { addLabel: 'Добавить цифру', titleOf: s => s.v || 'Цифра', blank: { v: '', k: { tj: '', ru: '' } } })
    ]),

    group('Кто я', [
      F({ on: p.about, k: 'badge', l: 'Метка', type: 'bi' }),
      F({ on: p.about, k: 'greeting', l: 'Приветствие', type: 'headline' }),
      F({ on: p.about, k: 'role', l: 'Кто ты одной строкой', type: 'bi' }),
      F({ on: p.about, k: 'statusBadge', l: 'Плашка на фото', type: 'bi' }),
      UI.h('span', { class: 'field-label', text: 'Рассказ о себе' }),
      listFor('profile', p.about.paragraphs, 'self-bi',
        { addLabel: 'Добавить абзац', titleOf: (x, i) => 'Абзац ' + (i + 1), blank: { tj: '', ru: '' } }),
      F({ on: p.about, k: 'stackTitle', l: 'Подпись над стеком', type: 'bi' }),
      UI.h('span', { class: 'field-label', text: 'Чипы стека' }),
      listFor('profile', p.about.stack, [
        { k: 'name', l: 'Название' },
        { k: 'color', l: 'Цвет точки', type: 'color' }
      ], { addLabel: 'Добавить технологию', titleOf: s => s.name, blank: { name: '', color: '#5FD9FF' } })
    ]),

    group('Как я работаю', [
      F({ on: p.work, k: 'title', l: 'Заголовок', type: 'bi' }),
      listFor('profile', p.work.paragraphs, 'self-bi',
        { addLabel: 'Добавить абзац', titleOf: (x, i) => 'Абзац ' + (i + 1), blank: { tj: '', ru: '' } })
    ]),

    group('Почему я', [
      F({ on: p.advantages, k: 'badge', l: 'Метка', type: 'bi' }),
      F({ on: p.advantages, k: 'title', l: 'Заголовок', type: 'headline' }),
      listFor('profile', p.advantages.items, [
        { k: 'icon', l: 'Иконка', type: 'select', options: ICON_OPTIONS },
        { k: 't', l: 'Заголовок', type: 'bi' },
        { k: 'd', l: 'Описание', type: 'bi-area' }
      ], { addLabel: 'Добавить карточку', titleOf: x => x.t?.ru || x.t?.tj || 'Карточка',
           blank: { icon: 'sparkles', t: { tj: '', ru: '' }, d: { tj: '', ru: '' } } })
    ]),

    group('Что умею', [
      F({ on: p.skills, k: 'title', l: 'Метка', type: 'bi' }),
      F({ on: p.skills, k: 'note', l: 'Заголовок', type: 'bi' }),
      listFor('profile', p.skills.items, [
        { k: 'name', l: 'Навык' },
        { k: 'level', l: 'Уровень', type: 'select', options: LEVEL_OPTIONS }
      ], { addLabel: 'Добавить навык', titleOf: s => s.name, blank: { name: '', level: 'learning' } })
    ]),

    group('Цели', [
      F({ on: p.goals, k: 'badge', l: 'Метка', type: 'bi' }),
      F({ on: p.goals, k: 'title', l: 'Заголовок', type: 'bi' }),
      listFor('profile', p.goals.items, [
        { k: 'when', l: 'Когда', type: 'bi' },
        { k: 't', l: 'Цель', type: 'bi' },
        { k: 'd', l: 'Описание', type: 'bi-area' }
      ], { addLabel: 'Добавить цель', titleOf: x => x.t?.ru || x.t?.tj || 'Цель',
           blank: { when: { tj: '', ru: '' }, t: { tj: '', ru: '' }, d: { tj: '', ru: '' } } })
    ]),

    group('Заказать работу', [
      F({ on: p.services, k: 'badge', l: 'Метка', type: 'bi' }),
      F({ on: p.services, k: 'lead', l: 'Заголовок', type: 'bi-area' }),
      listFor('profile', p.services.items, [
        { k: 'icon', l: 'Иконка', type: 'select', options: ICON_OPTIONS },
        { k: 't', l: 'Услуга', type: 'bi' },
        { k: 'd', l: 'Что входит', type: 'bi-area' }
      ], { addLabel: 'Добавить услугу', titleOf: x => x.t?.ru || x.t?.tj || 'Услуга',
           blank: { icon: 'bot', t: { tj: '', ru: '' }, d: { tj: '', ru: '' } } })
    ]),

    group('Контакты', [
      F({ on: p.contacts, k: 'badge', l: 'Метка', type: 'bi' }),
      F({ on: p.contacts, k: 'formTitle', l: 'Заголовок формы', type: 'headline' }),
      F({ on: p.contacts, k: 'lead', l: 'Подпись', type: 'bi-area' }),
      listFor('profile', p.contacts.items, [
        { k: 'icon', l: 'Иконка', type: 'select', options: ICON_OPTIONS },
        { k: 'label', l: 'Название' },
        { k: 'value', l: 'Что показывать' },
        { k: 'url', l: 'Ссылка', mono: true }
      ], { addLabel: 'Добавить контакт', titleOf: c => c.label, blank: { icon: 'telegram', label: '', value: '', url: '' } }),
      F({ on: p.contacts.form, k: 'name', l: 'Подпись поля «Имя»', type: 'bi' }),
      F({ on: p.contacts.form, k: 'task', l: 'Подпись поля «Задача»', type: 'bi' }),
      F({ on: p.contacts.form, k: 'send', l: 'Кнопка отправки', type: 'bi' }),
      F({ on: p.contacts.form, k: 'note', l: 'Пояснение под кнопкой', type: 'bi' }),
      F({ on: p.contacts.form, k: 'greeting', l: 'Начало письма в Telegram', type: 'bi' })
    ]),

    group('Языки, которыми владеешь', [
      listFor('profile', p.languages.items, [
        { k: 'name', l: 'Язык', type: 'bi' },
        { k: 'level', l: 'Уровень', type: 'bi' }
      ], { addLabel: 'Добавить язык', titleOf: l => l.name?.ru || l.name?.tj, blank: { name: { tj: '', ru: '' }, level: { tj: '', ru: '' } } })
    ]),

    group('Подписи разделов', [
      ...Object.keys(p.nav).map(k => fieldFor('profile', p.nav, { k, l: 'Меню: ' + k, type: 'bi' })),
      ...['timeline', 'timelineBadge', 'projects', 'projectsBadge', 'projectsEmpty',
          'diary', 'diaryBadge', 'diaryLead', 'diaryEmpty']
        .filter(k => p.sections[k])
        .map(k => fieldFor('profile', p.sections, { k, l: 'Раздел: ' + k, type: 'bi' })),
      fieldFor('profile', p.footer, { k: 'note', l: 'Строка в подвале', type: 'bi' })
    ])
  );
}

/* --- Экран: Проекты ---------------------------------------------- */

const PROJECT_BLANK = {
  slug: '', title: { tj: '', ru: '' }, summary: { tj: '', ru: '' }, body: { tj: '', ru: '' },
  tags: [], repo: '', demo: '', cover: '', status: 'wip', date: '', visible: true
};

/** Делает адрес из названия: «Мой бот» → «moy-bot». */
function slugify(text) {
  const map = {
    а:'a',б:'b',в:'v',г:'g',ғ:'gh',д:'d',е:'e',ё:'yo',ж:'zh',з:'z',и:'i',ӣ:'i',й:'y',
    к:'k',қ:'q',л:'l',м:'m',н:'n',о:'o',п:'p',р:'r',с:'s',т:'t',у:'u',ӯ:'u',ф:'f',
    х:'h',ҳ:'h',ц:'c',ч:'ch',ҷ:'j',ш:'sh',щ:'sch',ъ:'',ы:'y',ь:'',э:'e',ю:'yu',я:'ya'
  };
  return String(text).toLowerCase().split('')
    .map(ch => map[ch] ?? ch)
    .join('')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
}

function viewProjects(view) {
  const projects = data('projects').items;

  view.appendChild(UI.sectionHead('Проекты',
    'Карточки на главной. Пока список пуст, на сайте показывается вежливая заглушка.'));

  if (State.editing !== null) { renderProjectForm(view, projects, State.editing); return; }

  view.appendChild(UI.h('button', {
    class: 'btn btn-solid', attrs: { type: 'button', style: 'margin-bottom:24px' },
    on: { click: () => {
      projects.push(structuredClone(PROJECT_BLANK));
      State.editing = projects.length - 1;
      touch('projects');
      renderView();
    }}
  }, [UI.icon('plus'), UI.h('span', { text: 'Новый проект' })]));

  if (!projects.length) {
    view.appendChild(UI.h('p', { class: 'hint', text: 'Проектов пока нет. Добавь первый — даже маленький и незаконченный.' }));
    return;
  }

  const rows = UI.h('div', { class: 'rows' });
  projects.forEach((pr, i) => {
    const thumb = UI.h('div', { class: 'row-thumb' },
      pr.cover ? [UI.h('img', { attrs: { src: pr.cover, alt: '' } })] : [UI.icon('image')]);

    rows.appendChild(UI.h('div', { class: 'row' }, [
      thumb,
      UI.h('div', { class: 'row-main' }, [
        UI.h('div', { class: 'row-title', text: pr.title?.ru || pr.title?.tj || 'Без названия' }),
        UI.h('div', { class: 'row-sub', text: pr.slug || 'адрес не задан' })
      ]),
      UI.h('span', { class: 'badge', text: (STATUS_OPTIONS.find(o => o.value === pr.status) || {}).label || '—',
                     attrs: { 'data-status': pr.status } }),
      pr.visible === false ? UI.h('span', { class: 'badge badge-hidden', text: 'скрыт' }) : null,
      UI.h('div', { class: 'row-tools' }, [
        UI.h('button', { class: 'icon-btn', attrs: { type: 'button', title: 'Поднять', 'aria-label': 'Поднять', disabled: i === 0 },
          on: { click: () => { moveItem(projects, i, i - 1); touch('projects'); renderView(); } } }, [UI.icon('chevron-down', 'icon flip')]),
        UI.h('button', { class: 'icon-btn', attrs: { type: 'button', title: 'Опустить', 'aria-label': 'Опустить', disabled: i === projects.length - 1 },
          on: { click: () => { moveItem(projects, i, i + 1); touch('projects'); renderView(); } } }, [UI.icon('chevron-down')]),
        UI.h('button', { class: 'icon-btn', attrs: { type: 'button', title: 'Изменить', 'aria-label': 'Изменить' },
          on: { click: () => { State.editing = i; renderView(); } } }, [UI.icon('save')]),
        UI.h('button', { class: 'icon-btn icon-btn-danger', attrs: { type: 'button', title: 'Удалить', 'aria-label': 'Удалить' },
          on: { click: async () => {
            if (await confirmAction(`Удалить проект «${pr.title?.ru || pr.slug || 'без названия'}»?`)) {
              projects.splice(i, 1); touch('projects'); renderView();
            }
          }}}, [UI.icon('trash')])
      ])
    ]));
  });
  view.appendChild(rows);
}

function renderProjectForm(view, projects, index) {
  const pr = projects[index];

  view.appendChild(UI.h('button', {
    class: 'btn btn-ghost', attrs: { type: 'button', style: 'margin-bottom:16px' },
    on: { click: () => { State.editing = null; renderView(); } }
  }, [UI.icon('chevron-down', 'icon flip'), UI.h('span', { text: 'Назад к списку' })]));

  const titleField = UI.bilingual({
    label: 'Название', value: pr.title, onInput: (value, lang, raw) => {
      pr.title = value;
      // Адрес подставляем сам, пока его не трогали руками
      if (!pr.slug || pr.slug === slugify(pr.title.ru) || pr.slug === slugify(pr.title.tj)) {
        pr.slug = slugify(raw);
        const slugInput = document.getElementById('projectSlug');
        if (slugInput) slugInput.value = pr.slug;
      }
      touch('projects');
    }
  });

  const slugInput = UI.h('input', {
    class: 'input mono', props: { value: pr.slug ?? '' }, attrs: { type: 'text', id: 'projectSlug' },
    on: { input: e => { pr.slug = slugify(e.target.value); touch('projects'); } }
  });

  view.append(
    titleField,
    UI.h('div', { class: 'field' }, [
      UI.h('label', { text: 'Адрес страницы', attrs: { for: 'projectSlug' } }),
      slugInput,
      UI.h('p', { class: 'hint', text: 'Только латиница и дефисы — это часть ссылки на проект.' })
    ]),
    fieldFor('projects', pr, { k: 'summary', l: 'Коротко: одна-две строки', type: 'bi-area' }),
    fieldFor('projects', pr, { k: 'body', l: 'Подробный рассказ', type: 'bi-area',
      hint: 'Пустая строка между абзацами разделит текст на страницы проекта.' }),
    fieldFor('projects', pr, { k: 'tags', l: 'Теги', type: 'csv' }),
    fieldFor('projects', pr, { k: 'cover', l: 'Обложка', type: 'media' }),
    fieldFor('projects', pr, { k: 'repo', l: 'Ссылка на GitHub', mono: true }),
    fieldFor('projects', pr, { k: 'demo', l: 'Ссылка на живой проект', mono: true }),
    fieldFor('projects', pr, { k: 'status', l: 'Статус', type: 'select', options: STATUS_OPTIONS }),
    fieldFor('projects', pr, { k: 'date', l: 'Дата', hint: 'В виде 2026-08-19' }),
    fieldFor('projects', pr, { k: 'visible', l: 'Показывать на сайте', type: 'check' })
  );
}

/* --- Экран: Мой путь ---------------------------------------------- */

function viewTimeline(view) {
  const items = data('timeline').items;
  view.appendChild(UI.sectionHead('Мой путь',
    'Каждое событие — точка на линии. Отмеченное «поворотным» подсвечивается градиентом.'));

  view.appendChild(listFor('timeline', items, [
    { k: 'year', l: 'Год' },
    { k: 't', l: 'Что случилось', type: 'bi' },
    { k: 'd', l: 'Подробнее', type: 'bi-area' },
    { k: 'highlight', l: 'Поворотный момент', type: 'check' },
    { k: 'future', l: 'Это ещё впереди', type: 'check' }
  ], {
    addLabel: 'Добавить событие',
    titleOf: x => `${x.year || '····'} — ${x.t?.ru || x.t?.tj || ''}`,
    blank: { id: '', year: String(new Date().getFullYear()), t: { tj: '', ru: '' }, d: { tj: '', ru: '' } }
  }));
}

/* --- Экран: Дневник ------------------------------------------------ */

function viewDiary(view) {
  const items = data('diary').items;
  view.appendChild(UI.sectionHead('Дневник',
    'Короткие записи о том, что изучаешь. На сайте новые показываются первыми.'));

  view.appendChild(listFor('diary', items, [
    { k: 'date', l: 'Дата', hint: 'В виде 2026-08-19' },
    { k: 't', l: 'Заголовок', type: 'bi' },
    { k: 'd', l: 'Текст', type: 'bi-area' }
  ], {
    addLabel: 'Новая запись',
    titleOf: x => `${x.date || ''} — ${x.t?.ru || x.t?.tj || ''}`,
    blank: { id: '', date: new Date().toISOString().slice(0, 10), t: { tj: '', ru: '' }, d: { tj: '', ru: '' } }
  }));
}

/* --- Экран: Медиа --------------------------------------------------- */

const MAX_SIDE = 1600;      // больше для сайта не нужно
const JPEG_QUALITY = 0.82;

/** Уменьшает и пережимает картинку прямо в браузере. Возвращает {base64, name, size}. */
async function shrinkImage(file) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const w = Math.round(bitmap.width * scale);
  const h = Math.round(bitmap.height * scale);

  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  canvas.getContext('2d').drawImage(bitmap, 0, 0, w, h);
  bitmap.close?.();

  const blob = await new Promise(res => canvas.toBlob(res, 'image/jpeg', JPEG_QUALITY));
  const bytes = new Uint8Array(await blob.arrayBuffer());

  // btoa не переваривает длинную строку целиком — кодируем кусками
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }

  const base = file.name.replace(/\.[^.]+$/, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) || 'photo';

  return { base64: btoa(binary), name: `${base}-${Date.now().toString(36)}.jpg`, size: blob.size };
}

function viewMedia(view) {
  view.appendChild(UI.sectionHead('Медиа',
    'Картинки для обложек проектов и фото. Перед отправкой они уменьшаются прямо здесь, чтобы сайт грузился быстро.'));

  const input = UI.h('input', {
    attrs: { type: 'file', accept: 'image/*', multiple: true, hidden: true },
    on: { change: e => upload([...e.target.files]) }
  });

  const drop = UI.h('div', { class: 'drop' }, [
    UI.icon('upload'),
    UI.h('p', { text: 'Перетащи картинки сюда или выбери на устройстве', attrs: { style: 'margin:0' } }),
    UI.h('button', { class: 'btn btn-line', attrs: { type: 'button' }, on: { click: () => input.click() } },
      [UI.icon('image'), UI.h('span', { text: 'Выбрать файлы' })]),
    input
  ]);

  for (const type of ['dragenter', 'dragover']) {
    drop.addEventListener(type, e => { e.preventDefault(); drop.classList.add('over'); });
  }
  for (const type of ['dragleave', 'drop']) {
    drop.addEventListener(type, e => { e.preventDefault(); drop.classList.remove('over'); });
  }
  drop.addEventListener('drop', e => {
    upload([...e.dataTransfer.files].filter(f => f.type.startsWith('image/')));
  });

  const grid = UI.h('div', { class: 'media-grid' });
  view.append(drop, grid);
  loadAssets();

  async function upload(files) {
    if (!files.length) return;
    for (const file of files) {
      try {
        const { base64, name, size } = await shrinkImage(file);
        const path = 'assets/' + name;
        await GH.putBinary(path, base64, null, `Загрузить ${path} через панель управления`);
        toast(`${name} — ${Math.round(size / 1024)} КБ, загружено`);
      } catch (err) {
        toast(`${file.name}: ${err.message}`, 'error');
      }
    }
    loadAssets();
  }

  async function loadAssets() {
    UI.clear(grid);
    grid.appendChild(UI.h('p', { class: 'hint', text: 'Загружаю список...' }));
    try {
      const files = (await GH.listDir('assets')).filter(f => /\.(jpe?g|png|webp|gif|avif)$/i.test(f.name));
      UI.clear(grid);
      if (!files.length) {
        grid.appendChild(UI.h('p', { class: 'hint', text: 'Картинок пока нет.' }));
        return;
      }
      for (const file of files) {
        grid.appendChild(UI.h('button', {
          class: 'media-tile', attrs: { type: 'button', title: 'Скопировать путь' },
          on: { click: async () => {
            try {
              await navigator.clipboard.writeText('assets/' + file.name);
              toast('Путь скопирован: assets/' + file.name);
            } catch (_) {
              toast('Путь: assets/' + file.name);
            }
          }}
        }, [
          UI.h('img', { attrs: { src: file.download_url, alt: '', loading: 'lazy' } }),
          UI.h('figcaption', { text: `${file.name} · ${Math.round(file.size / 1024)} КБ` })
        ]));
      }
    } catch (err) {
      UI.clear(grid);
      grid.appendChild(UI.h('p', { class: 'hint', text: err.message }));
    }
  }
}

/* --- Экран: Настройки ------------------------------------------------ */

function viewSettings(view) {
  const cfg = GH.cfg();
  view.appendChild(UI.sectionHead('Настройки', 'Куда панель складывает изменения и что делать, если что-то пошло не так.'));

  const draft = { ...cfg };
  const set = key => value => { draft[key] = value.trim(); };

  view.append(
    group('Репозиторий', [
      UI.text({ label: 'Владелец', value: cfg.owner, mono: true, onInput: set('owner') }),
      UI.text({ label: 'Репозиторий', value: cfg.repo, mono: true, onInput: set('repo') }),
      UI.text({
        label: 'Ветка', value: cfg.branch, mono: true, onInput: set('branch'),
        hint: 'Та же ветка, из которой GitHub Pages публикует сайт. Обычно main.'
      }),
      UI.h('button', {
        class: 'btn btn-solid', attrs: { type: 'button' },
        on: { click: async () => {
          GH.saveCfg(draft);
          try {
            const info = await GH.verify();
            toast(`Есть связь: ${info.name}, ветка ${info.branch}`);
            loadAll();
          } catch (err) { toast(err.message, 'error'); }
        }}
      }, [UI.icon('check'), UI.h('span', { text: 'Сохранить и проверить' })])
    ], true),

    group('Если что-то сломалось', [
      UI.h('p', { class: 'hint', text: 'Скачай файлы на устройство — так правки точно не пропадут, даже если GitHub недоступен.' }),
      UI.h('div', { attrs: { style: 'display:flex;flex-wrap:wrap;gap:8px;margin-top:12px' } },
        Object.keys(FILES).map(key => UI.h('button', {
          class: 'btn btn-line', attrs: { type: 'button' },
          on: { click: () => downloadJSON(key) }
        }, [UI.icon('download'), UI.h('span', { text: key + '.json' })])))
    ]),

    group('Токен', [
      UI.h('p', { class: 'hint', text: 'Токен хранится только в этом браузере. Если ты входил с чужого устройства — обязательно выйди там, а лучше отзови токен на GitHub.' }),
      UI.h('div', { attrs: { style: 'display:flex;flex-wrap:wrap;gap:8px;margin-top:12px' } }, [
        UI.h('a', {
          class: 'btn btn-line',
          attrs: { href: 'https://github.com/settings/personal-access-tokens', target: '_blank', rel: 'noopener' }
        }, [UI.icon('key'), UI.h('span', { text: 'Мои токены на GitHub' })]),
        UI.h('button', {
          class: 'btn btn-danger', attrs: { type: 'button' },
          on: { click: async () => {
            if (dirtyKeys().length && !await confirmAction('Есть неопубликованные правки. Всё равно выйти?', 'Выйти')) return;
            GH.clearToken(); State.files = {}; showLogin();
          }}
        }, [UI.icon('logout'), UI.h('span', { text: 'Выйти' })])
      ])
    ]),

    group('Сайт', [
      UI.h('a', { class: 'btn btn-line', attrs: { href: GH.siteUrl(), target: '_blank', rel: 'noopener' } },
        [UI.icon('external'), UI.h('span', { text: GH.siteUrl() })])
    ])
  );
}

/** Запасной путь: сохранить файл на устройство, если GitHub недоступен. */
function downloadJSON(key) {
  const text = JSON.stringify(data(key), null, 2) + '\n';
  const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
  const link = UI.h('a', { attrs: { href: url, download: key + '.json' } });
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
