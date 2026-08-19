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
    h('div', { class: 'side-brand' }, [h('span', { text: 'Alijon' }), h('span', { text: '.' })]),
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
  view.scrollIntoView({ block: 'start' });
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
