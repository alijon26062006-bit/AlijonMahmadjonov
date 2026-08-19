/* ===========================================================
   Кирпичики интерфейса админки: поля, списки, уведомления.
   Ничего не знает ни о GitHub, ни о структуре данных.
   =========================================================== */

const UI = (() => {

  /** Создаёт элемент. Текст всегда через textContent — разметка из данных не исполняется. */
  function h(tag, opts = {}, children = []) {
    const node = document.createElement(tag);
    if (opts.id) node.id = opts.id;
    if (opts.class) node.className = opts.class;
    if (opts.text != null) node.textContent = opts.text;
    for (const [k, v] of Object.entries(opts.attrs || {})) {
      if (v != null && v !== false) node.setAttribute(k, v === true ? '' : v);
    }
    for (const [k, v] of Object.entries(opts.on || {})) node.addEventListener(k, v);
    for (const [k, v] of Object.entries(opts.props || {})) node[k] = v;
    for (const child of [].concat(children)) if (child) node.appendChild(child);
    return node;
  }

  function icon(name, cls = 'icon') {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', cls);
    svg.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', '#i-' + name);
    svg.appendChild(use);
    return svg;
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  /* --- уведомления ---------------------------------------------- */

  let toastBox = null;

  function toast(message, kind = 'ok') {
    if (!toastBox) {
      toastBox = h('div', { class: 'toasts', attrs: { role: 'status', 'aria-live': 'polite' } });
      document.body.appendChild(toastBox);
    }
    const node = h('div', { class: `toast toast-${kind}` }, [
      icon(kind === 'ok' ? 'check-circle' : 'alert'),
      h('span', { text: message })
    ]);
    toastBox.appendChild(node);
    // Ошибку держим дольше — её нужно успеть прочитать.
    setTimeout(() => node.remove(), kind === 'ok' ? 3500 : 7000);
  }

  /* --- подтверждение -------------------------------------------- */

  function confirmAction(message, confirmLabel = 'Удалить') {
    return new Promise(resolve => {
      const close = answer => { overlay.remove(); document.body.style.overflow = ''; resolve(answer); };
      const dialog = h('div', { class: 'dialog', attrs: { role: 'dialog', 'aria-modal': 'true' } }, [
        h('p', { text: message }),
        h('div', { class: 'dialog-actions' }, [
          h('button', { class: 'btn btn-ghost', text: 'Отмена', on: { click: () => close(false) } }),
          h('button', { class: 'btn btn-danger', text: confirmLabel, on: { click: () => close(true) } })
        ])
      ]);
      const overlay = h('div', {
        class: 'overlay',
        on: { click: e => { if (e.target === overlay) close(false); } }
      }, [dialog]);
      document.addEventListener('keydown', function esc(e) {
        if (e.key === 'Escape') { document.removeEventListener('keydown', esc); close(false); }
      });
      document.body.appendChild(overlay);
      document.body.style.overflow = 'hidden';
      dialog.querySelector('.btn-danger').focus();
    });
  }

  /* --- поля ------------------------------------------------------ */

  let fieldId = 0;
  const nextId = () => 'f' + (++fieldId);

  function wrapField(labelText, control, hint) {
    const id = control.id || (control.id = nextId());
    return h('div', { class: 'field' }, [
      h('label', { text: labelText, attrs: { for: id } }),
      control,
      hint ? h('p', { class: 'hint', text: hint }) : null
    ]);
  }

  /** Обычная строка. */
  function text({ label, value, onInput, hint, placeholder, multiline, mono }) {
    const control = h(multiline ? 'textarea' : 'input', {
      class: 'input' + (mono ? ' mono' : ''),
      props: { value: value ?? '' },
      attrs: { placeholder: placeholder || '', rows: multiline ? 4 : null, type: multiline ? null : 'text' },
      on: { input: e => onInput(e.target.value) }
    });
    return wrapField(label, control, hint);
  }

  /** Двуязычное поле: таджикский и русский рядом. */
  function bilingual({ label, value, onInput, multiline, hint }) {
    // Копим значение здесь: если брать снимок при отрисовке, ввод во второе
    // поле затирал бы то, что уже набрано в первом.
    const current = { tj: '', ru: '', ...(value && typeof value === 'object' ? value : {}) };
    const make = (lang, caption) => {
      const control = h(multiline ? 'textarea' : 'input', {
        class: 'input',
        props: { value: current[lang] ?? '' },
        attrs: { rows: multiline ? 4 : null, type: multiline ? null : 'text' },
        on: { input: e => {
          current[lang] = e.target.value;
          onInput({ ...current }, lang, e.target.value);
        }}
      });
      const id = control.id = nextId();
      return h('div', { class: 'bi-col' }, [
        h('label', { class: 'bi-lang', text: caption, attrs: { for: id } }),
        control
      ]);
    };
    return h('div', { class: 'field' }, [
      h('span', { class: 'field-label', text: label }),
      h('div', { class: 'bi' }, [make('tj', 'Тоҷикӣ'), make('ru', 'Русский')]),
      hint ? h('p', { class: 'hint', text: hint }) : null
    ]);
  }

  /** Выпадающий список. */
  function select({ label, value, options, onChange, hint }) {
    const control = h('select', {
      class: 'input',
      on: { change: e => onChange(e.target.value) }
    }, options.map(o => h('option', {
      text: o.label, attrs: { value: o.value, selected: o.value === value }
    })));
    control.value = value;
    return wrapField(label, control, hint);
  }

  /** Галочка. */
  function checkbox({ label, value, onChange }) {
    const input = h('input', {
      attrs: { type: 'checkbox' },
      props: { checked: Boolean(value) },
      on: { change: e => onChange(e.target.checked) }
    });
    const id = input.id = nextId();
    return h('div', { class: 'field field-check' }, [
      input,
      h('label', { text: label, attrs: { for: id } })
    ]);
  }

  /**
   * Редактор списка: добавить, удалить, поднять, опустить.
   * Кнопками, а не перетаскиванием — перетаскивание не работает пальцем на телефоне.
   */
  function list({ items, addLabel, onAdd, onRemove, onMove, renderItem, titleOf, emptyText }) {
    const box = h('div', { class: 'list' });

    if (!items.length) {
      box.appendChild(h('p', { class: 'hint', text: emptyText || 'Пока пусто.' }));
    }

    items.forEach((item, i) => {
      const head = h('div', { class: 'list-head' }, [
        h('span', { class: 'list-title', text: titleOf ? titleOf(item, i) : `№${i + 1}` }),
        h('div', { class: 'list-tools' }, [
          h('button', {
            class: 'icon-btn', attrs: { type: 'button', title: 'Поднять', 'aria-label': 'Поднять выше', disabled: i === 0 },
            on: { click: () => onMove(i, i - 1) }
          }, [icon('chevron-down', 'icon flip')]),
          h('button', {
            class: 'icon-btn', attrs: { type: 'button', title: 'Опустить', 'aria-label': 'Опустить ниже', disabled: i === items.length - 1 },
            on: { click: () => onMove(i, i + 1) }
          }, [icon('chevron-down')]),
          h('button', {
            class: 'icon-btn icon-btn-danger', attrs: { type: 'button', title: 'Удалить', 'aria-label': 'Удалить' },
            on: { click: () => onRemove(i) }
          }, [icon('trash')])
        ])
      ]);
      box.appendChild(h('div', { class: 'list-item' }, [head, renderItem(item, i)]));
    });

    if (onAdd) {
      box.appendChild(h('button', {
        class: 'btn btn-line btn-add', attrs: { type: 'button' }, on: { click: onAdd }
      }, [icon('plus'), h('span', { text: addLabel || 'Добавить' })]));
    }
    return box;
  }

  /** Заголовок раздела с описанием. */
  function sectionHead(title, description) {
    return h('div', { class: 'section-head' }, [
      h('h2', { text: title }),
      description ? h('p', { class: 'hint', text: description }) : null
    ]);
  }

  /** Складной блок — иначе форма профиля превращается в бесконечную простыню. */
  function group(title, children, open = false) {
    const body = h('div', { class: 'group-body' }, children);
    const toggle = h('button', {
      class: 'group-head', attrs: { type: 'button', 'aria-expanded': String(open) },
      on: { click: () => {
        const next = toggle.getAttribute('aria-expanded') !== 'true';
        toggle.setAttribute('aria-expanded', String(next));
        body.hidden = !next;
      }}
    }, [h('span', { text: title }), icon('chevron-down')]);
    body.hidden = !open;
    return h('section', { class: 'group' }, [toggle, body]);
  }

  return { h, icon, clear, toast, confirmAction, text, bilingual, select, checkbox, list, sectionHead, group };
})();
