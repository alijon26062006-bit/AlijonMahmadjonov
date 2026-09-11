<?php
/** @var string $csrf
 *  @var array<string,mixed> $site
 *  @var string $path
 *  @var list<array{name:string,path:string,is_dir:bool,size:int,modified:int}> $entries
 *  @var list<array{name:string,path:string}> $breadcrumbs
 *  @var array{used:int,limit:int,percent:int,exceeded:bool} $quota
 *  @var array<string,array{title:string,description:string}> $templates
 */
use Hosting\Support\Html;
use Hosting\Support\Path;

$sid = (int) $site['id'];
$browse = static fn (string $p): string => '/sites/' . $sid . '/files' . ($p === '' ? '' : '?path=' . rawurlencode($p));

/** Иконка 24×24 из набора ниже — чтобы не повторять обвязку <svg> двадцать раз. */
$ico = static fn (string $body): string =>
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" '
    . 'stroke-linecap="round" stroke-linejoin="round">' . $body . '</svg>';

$icons = [
    'home'   => '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9.5"/>',
    'up'     => '<path d="M19 12H5"/><path d="m11 6-6 6 6 6"/>',
    'folder' => '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>',
    'code'   => '<path d="m9 8-5 4 5 4"/><path d="m15 8 5 4-5 4"/>',
    'lock'   => '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    'file'   => '<path d="M6 3h8l4 4v14H6V3Z"/><path d="M14 3v4h4"/>',
    'zip'    => '<path d="M6 3h8l4 4v14H6V3Z"/><path d="M11 3v3M13 6v3M11 9v3M13 12v3"/>',
    'pencil' => '<path d="M4 20h4L19.5 8.5a2.1 2.1 0 0 0-3-3L5 17v3Z"/>',
    'trash'  => '<path d="M4 7h16"/><path d="M9 7V5h6v2"/><path d="M6 7v13a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7"/>',
    'down'   => '<path d="M12 4v11"/><path d="m7 11 5 5 5-5"/><path d="M5 20h14"/>',
    'rename' => '<path d="M3 11.5V5a2 2 0 0 1 2-2h6.5L21 12.5 12.5 21 3 11.5Z"/><circle cx="7.3" cy="7.3" r="1.2"/>',
    'unzip'  => '<path d="M21 8v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8"/><path d="M2 4h20v4H2z"/><path d="M10 12h4"/>',
    'upload' => '<path d="M12 19V8"/><path d="m7 12 5-5 5 5"/><path d="M5 21h14"/>',
    'plus'   => '<path d="M12 5v14"/><path d="M5 12h14"/>',
    'spark'  => '<path d="m12 3 2.2 5.8L20 11l-5.8 2.2L12 19l-2.2-5.8L4 11l5.8-2.2L12 3Z"/>',
];
?>
<style>
  .fm-head { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:14px; }

  /* Панель инструментов как в привычных файловых менеджерах: хлебные крошки
     слева, действия справа. На телефоне действия переносятся на вторую строку
     и остаются нажимаемыми — горизонтальной прокрутки здесь быть не должно. */
  .fm-bar { position:relative; display:flex; flex-wrap:wrap; align-items:center; gap:10px 8px;
            padding-bottom:14px; border-bottom:1px solid var(--border); }
  .fm-crumbs { display:flex; flex-wrap:wrap; align-items:center; gap:6px; font-size:14px;
               flex:1 1 200px; min-width:0; }
  .fm-crumbs a { display:inline-flex; align-items:center; gap:5px; }
  .fm-crumbs svg { width:16px; height:16px; }
  .fm-crumbs i { color:var(--muted); font-style:normal; }
  .fm-tools { display:flex; flex-wrap:wrap; gap:8px; }

  /* Кнопка-раскрывашка: форма прячется под ней и открывается без JavaScript —
     CSP панели запрещает inline-скрипты, а <details> работает и без них. */
  .fm-tool > summary { list-style:none; cursor:pointer; display:inline-flex; align-items:center; gap:7px;
                       padding:9px 14px; border-radius:var(--r-md); border:1px solid var(--border);
                       background:var(--surface); color:var(--text); font-size:14px; font-weight:600;
                       user-select:none; }
  .fm-tool > summary::-webkit-details-marker { display:none; }
  .fm-tool > summary:hover { border-color:var(--primary); color:var(--primary); }
  .fm-tool[open] > summary { background:var(--primary); border-color:var(--primary); color:#fff; }
  .fm-tool summary svg { width:17px; height:17px; }
  /* Панель раскрывается во всю ширину бара и НЕ участвует в его ширине:
     Chrome держит содержимое закрытого <details> в раскладке (content-visibility),
     и без absolute широкая форма растягивала карточку за край экрана. */
  .fm-panel { position:absolute; left:0; right:0; top:100%; z-index:20;
              padding:14px; background:var(--surface); box-shadow:var(--shadow-md);
              border:1px solid var(--border); border-radius:var(--r-md); }
  .fm-panel label { font-size:13px; }
  .fm-inline { display:flex; gap:8px; }
  .fm-inline input[type=text] { flex:1 1 auto; min-width:0; }

  /* minmax(0,1fr), а не просто grid: колонка с авто-минимумом раздувается до
     min-content самой широкой строки и вылезает за карточку. */
  .fm-list { display:grid; grid-template-columns:minmax(0,1fr); gap:8px; margin-top:14px; }
  .fm-row { display:flex; align-items:center; gap:12px; min-width:0; padding:10px 12px;
            background:var(--surface); border:1px solid var(--border); border-radius:var(--r-md); }
  .fm-row:hover { border-color:var(--primary); }
  .fm-icon { flex:none; width:38px; height:38px; border-radius:11px; display:grid; place-items:center; }
  .fm-icon svg { width:19px; height:19px; }
  .fm-dir  { background:var(--primary-soft); color:var(--primary); }
  .fm-file { background:var(--surface-2); color:var(--muted); }
  .fm-php  { background:var(--purple-soft); color:var(--purple); }
  .fm-env  { background:var(--warning-soft); color:var(--warning); }
  .fm-main { flex:1 1 auto; min-width:0; }
  .fm-name { display:block; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  /* Размер и дата в одну строку: иначе на телефоне они переносятся в три
     строки и строка файла становится выше кнопок рядом с ней. */
  .fm-meta { display:block; font-size:12.5px; color:var(--muted);
             white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

  /* Иконки-действия одинаковой ширины: строка не «прыгает» от длины имени. */
  .fm-actions { display:flex; align-items:center; gap:2px; flex:none; }
  .fm-actions form { display:contents; }
  .fm-actions .icon-btn { width:34px; height:34px; }
  .fm-actions .icon-btn svg { width:17px; height:17px; }
  .fm-actions .is-danger:hover { background:var(--danger-soft); color:var(--danger); }

  .fm-tpl { display:grid; gap:10px; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); }
  .fm-tpl button { display:block; width:100%; text-align:left; background:var(--surface);
                   color:var(--text); border:1px solid var(--border); font-weight:600; }
  .fm-tpl button:hover { background:var(--primary-soft); border-color:var(--primary); }
  .fm-tpl small { display:block; font-weight:400; color:var(--muted); margin-top:3px; }

  @media (max-width:560px) {
    .fm-tool { flex:1 1 calc(50% - 4px); }
    .fm-tool > summary { width:100%; justify-content:center; }
  }
  @media (max-width:420px) {
    .fm-row { gap:8px; padding:10px; }
    .fm-icon { width:34px; height:34px; }
    .fm-actions .icon-btn { width:30px; height:30px; }
    .fm-actions .icon-btn svg { width:16px; height:16px; }
  }
</style>

<div class="fm-head">
  <a class="btn secondary" href="/sites/<?= $sid ?>">← <?= Html::e($site['domain']) ?></a>
  <span class="muted">Диск: <?= Html::e(Path::humanSize($quota['used'])) ?> из <?= Html::e(Path::humanSize($quota['limit'])) ?>
    (<?= (int) $quota['percent'] ?>%)<?= $quota['exceeded'] ? ' — квота исчерпана' : '' ?></span>
</div>

<div class="card">
  <div class="fm-bar">
    <div class="fm-crumbs">
      <a href="<?= $browse('') ?>"><?= $ico($icons['home']) ?>Сайт</a>
      <?php foreach ($breadcrumbs as $i => $crumb): if ($i === 0) continue; ?>
        <i>/</i>
        <a href="<?= $browse($crumb['path']) ?>"><?= Html::e($crumb['name']) ?></a>
      <?php endforeach; ?>
    </div>

    <div class="fm-tools">
      <details class="fm-tool">
        <summary><?= $ico($icons['upload']) ?>Загрузить</summary>
        <div class="fm-panel">
          <form method="post" action="/sites/<?= $sid ?>/files/upload" enctype="multipart/form-data">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <input type="hidden" name="path" value="<?= Html::e($path) ?>">
            <label>Файл или ZIP-архив</label>
            <input type="file" name="file" required>
            <label style="display:flex;align-items:center;gap:8px;margin-top:8px;font-weight:400;">
              <input type="checkbox" name="extract" value="1" style="width:auto;"> распаковать, если это ZIP
            </label>
            <div style="margin-top:10px;"><button type="submit">Загрузить</button></div>
          </form>
        </div>
      </details>

      <details class="fm-tool">
        <summary><?= $ico($icons['folder']) ?>Папка</summary>
        <div class="fm-panel">
          <form method="post" action="/sites/<?= $sid ?>/files/mkdir">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <input type="hidden" name="path" value="<?= Html::e($path) ?>">
            <label>Имя папки</label>
            <div class="fm-inline">
              <input type="text" name="name" placeholder="images" required>
              <button type="submit">Создать</button>
            </div>
          </form>
        </div>
      </details>

      <details class="fm-tool">
        <summary><?= $ico($icons['plus']) ?>Новый файл</summary>
        <div class="fm-panel">
          <form method="post" action="/sites/<?= $sid ?>/files/newfile">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <input type="hidden" name="path" value="<?= Html::e($path) ?>">
            <label>Имя файла — откроется в редакторе</label>
            <div class="fm-inline">
              <input type="text" name="name" placeholder="index.php" required>
              <button type="submit">Создать</button>
            </div>
            <div class="muted" style="margin-top:6px;">Можно написать просто <code>index</code> — станет <code>index.php</code></div>
          </form>
        </div>
      </details>

      <details class="fm-tool">
        <summary><?= $ico($icons['spark']) ?>Шаблон</summary>
        <div class="fm-panel">
          <p class="muted" style="margin:0 0 10px;">Готовый рабочий файл вместо пустой страницы.</p>
          <form method="post" action="/sites/<?= $sid ?>/files/template">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <div class="fm-tpl">
              <?php foreach ($templates as $key => $tpl): ?>
                <button type="submit" name="template" value="<?= Html::e($key) ?>">
                  <?= Html::e($tpl['title']) ?>
                  <small><?= Html::e($tpl['description']) ?></small>
                </button>
              <?php endforeach; ?>
            </div>
            <label style="display:flex;align-items:center;gap:8px;margin-top:12px;font-weight:400;">
              <input type="checkbox" name="overwrite" value="1" style="width:auto;"> перезаписать, если файл уже есть
            </label>
          </form>
        </div>
      </details>
    </div>
  </div>

  <div class="fm-list">
    <?php if ($path !== ''): ?>
      <?php $up = (string) dirname($path); ?>
      <a class="fm-row" href="<?= $browse($up === '.' ? '' : $up) ?>" style="text-decoration:none;color:inherit;">
        <span class="fm-icon fm-dir"><?= $ico($icons['up']) ?></span>
        <span class="fm-main"><span class="fm-name">Наверх</span></span>
      </a>
    <?php endif; ?>

    <?php foreach ($entries as $entry):
      $isPhp = !$entry['is_dir'] && str_ends_with(strtolower($entry['name']), '.php');
      $isEnv = str_starts_with($entry['name'], '.env');
      $isZip = !$entry['is_dir'] && str_ends_with(strtolower($entry['name']), '.zip');
      $cls = $entry['is_dir'] ? 'fm-dir' : ($isEnv ? 'fm-env' : ($isPhp ? 'fm-php' : 'fm-file'));
      $glyph = $entry['is_dir'] ? 'folder' : ($isEnv ? 'lock' : ($isPhp ? 'code' : ($isZip ? 'zip' : 'file')));
      $editUrl = '/sites/' . $sid . '/files/edit?path=' . rawurlencode($entry['path']);
    ?>
      <div class="fm-row">
        <span class="fm-icon <?= $cls ?>"><?= $ico($icons[$glyph]) ?></span>

        <span class="fm-main">
          <?php if ($entry['is_dir']): ?>
            <a class="fm-name" href="<?= $browse($entry['path']) ?>"><?= Html::e($entry['name']) ?></a>
            <span class="fm-meta">папка</span>
          <?php else: ?>
            <a class="fm-name" href="<?= $editUrl ?>"><?= Html::e($entry['name']) ?></a>
            <span class="fm-meta"><?= Html::e(Path::humanSize($entry['size'])) ?><?= $entry['modified'] ? ' · ' . date('d.m.Y', $entry['modified']) : '' ?></span>
          <?php endif; ?>
        </span>

        <span class="fm-actions">
          <?php if (!$entry['is_dir']): ?>
            <a class="icon-btn" href="<?= $editUrl ?>" title="Изменить" aria-label="Изменить <?= Html::e($entry['name']) ?>"><?= $ico($icons['pencil']) ?></a>
            <a class="icon-btn" href="/sites/<?= $sid ?>/files/download?path=<?= rawurlencode($entry['path']) ?><?= $isEnv ? '&confirm=yes' : '' ?>"
               title="<?= $isEnv ? 'Скачать .env' : 'Скачать' ?>" aria-label="Скачать <?= Html::e($entry['name']) ?>"><?= $ico($icons['down']) ?></a>
          <?php endif; ?>

          <?php if ($isZip): ?>
            <form method="post" action="/sites/<?= $sid ?>/files/extract"
                  data-confirm="Распаковать <?= Html::e($entry['name']) ?> в эту папку?">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <input type="hidden" name="target" value="<?= Html::e($entry['path']) ?>">
              <button type="submit" class="icon-btn" title="Распаковать" aria-label="Распаковать <?= Html::e($entry['name']) ?>"><?= $ico($icons['unzip']) ?></button>
            </form>
          <?php endif; ?>

          <form method="post" action="/sites/<?= $sid ?>/files/rename">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <input type="hidden" name="target" value="<?= Html::e($entry['path']) ?>">
            <input type="hidden" name="name" value="">
            <button type="submit" class="icon-btn" title="Переименовать" aria-label="Переименовать <?= Html::e($entry['name']) ?>"
                    data-prompt="Новое имя" data-prompt-default="<?= Html::e($entry['name']) ?>"
                    data-prompt-target="name"><?= $ico($icons['rename']) ?></button>
          </form>

          <form method="post" action="/sites/<?= $sid ?>/files/delete"
                data-confirm="Удалить <?= Html::e($entry['name']) ?>? Это необратимо.">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <input type="hidden" name="target" value="<?= Html::e($entry['path']) ?>">
            <button type="submit" class="icon-btn is-danger" title="Удалить" aria-label="Удалить <?= Html::e($entry['name']) ?>"><?= $ico($icons['trash']) ?></button>
          </form>
        </span>
      </div>
    <?php endforeach; ?>

    <?php if ($entries === []): ?>
      <div class="fm-row"><span class="fm-main muted">Папка пуста — начните с кнопки «Новый файл» или «Шаблон»</span></div>
    <?php endif; ?>
  </div>
</div>
