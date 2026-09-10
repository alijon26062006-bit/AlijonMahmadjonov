// Редактор файлов панели.
//
// Сознательно без Monaco/CodeMirror: панель работает под CSP script-src 'self',
// то есть подключать редактор с CDN нельзя, а класть в репозиторий мегабайты
// чужого кода ради подсветки — плохой обмен. Здесь textarea плюс то, чего людям
// реально не хватает: нумерация строк, Tab отступом, Ctrl/Cmd+S, предупреждение
// о несохранённых правках и переход к строке с ошибкой PHP.
(function () {
  var area = document.getElementById('code');
  if (!area) {
    return;
  }

  var gutter = document.getElementById('gutter');
  var form = document.getElementById('editor-form');
  var saveButton = document.getElementById('save-button');
  var status = document.getElementById('editor-status');
  var initial = area.value;
  var saving = false;

  function renderGutter() {
    if (!gutter) {
      return;
    }
    var lines = area.value.split('\n').length;
    var html = '';
    for (var i = 1; i <= lines; i++) {
      html += i + '\n';
    }
    gutter.textContent = html;
    gutter.scrollTop = area.scrollTop;
  }

  function dirty() {
    return area.value !== initial;
  }

  function updateStatus() {
    if (!status) {
      return;
    }
    status.textContent = dirty() ? 'Есть несохранённые изменения' : 'Сохранено';
    status.className = dirty() ? 'ed-status is-dirty' : 'ed-status';
  }

  area.addEventListener('input', function () {
    renderGutter();
    updateStatus();
  });
  area.addEventListener('scroll', function () {
    if (gutter) {
      gutter.scrollTop = area.scrollTop;
    }
  });

  // Tab внутри редактора — это отступ, а не переход к следующему полю.
  area.addEventListener('keydown', function (e) {
    if (e.key === 'Tab') {
      e.preventDefault();
      var start = area.selectionStart;
      var end = area.selectionEnd;
      area.value = area.value.slice(0, start) + '    ' + area.value.slice(end);
      area.selectionStart = area.selectionEnd = start + 4;
      renderGutter();
      updateStatus();
      return;
    }

    if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      if (form) {
        saving = true;
        form.submit();
      }
    }
  });

  // Автоотступ: новая строка начинается с тем же отступом, что предыдущая.
  area.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter') {
      return;
    }
    var start = area.selectionStart;
    var before = area.value.slice(0, start);
    var lineStart = before.lastIndexOf('\n') + 1;
    var indent = (before.slice(lineStart).match(/^[ \t]*/) || [''])[0];
    if (!indent) {
      return;
    }
    e.preventDefault();
    var insert = '\n' + indent;
    area.value = before + insert + area.value.slice(area.selectionEnd);
    area.selectionStart = area.selectionEnd = start + insert.length;
    renderGutter();
    updateStatus();
  });

  if (form) {
    form.addEventListener('submit', function () {
      saving = true;
    });
  }
  if (saveButton) {
    saveButton.addEventListener('click', function () {
      saving = true;
    });
  }

  window.addEventListener('beforeunload', function (e) {
    if (saving || !dirty()) {
      return;
    }
    e.preventDefault();
    e.returnValue = '';
  });

  // Если сервер вернул строку с ошибкой PHP — ставим туда курсор.
  var errorLine = parseInt(area.getAttribute('data-error-line') || '0', 10);
  if (errorLine > 0) {
    var pos = 0;
    var parts = area.value.split('\n');
    for (var i = 0; i < errorLine - 1 && i < parts.length; i++) {
      pos += parts[i].length + 1;
    }
    area.focus();
    area.setSelectionRange(pos, pos + (parts[errorLine - 1] || '').length);
  }

  renderGutter();
  updateStatus();
})();
