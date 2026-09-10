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
?>
<style>
  .fm-head { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:14px; }
  .fm-crumbs { display:flex; flex-wrap:wrap; align-items:center; gap:6px; font-size:14px; }
  .fm-crumbs span { color:var(--muted); }
  .fm-list { display:grid; gap:10px; }
  .fm-row { display:flex; align-items:center; gap:12px; padding:12px 14px; background:var(--surface);
            border:1px solid var(--border); border-radius:var(--r-md); }
  .fm-icon { flex:none; width:38px; height:38px; border-radius:11px; display:grid; place-items:center; }
  .fm-icon svg { width:19px; height:19px; }
  .fm-dir  { background:var(--primary-soft); color:var(--primary); }
  .fm-file { background:var(--surface-2); color:var(--muted); }
  .fm-php  { background:var(--purple-soft); color:var(--purple); }
  .fm-env  { background:var(--warning-soft); color:var(--warning); }
  .fm-main { flex:1 1 auto; min-width:0; }
  .fm-name { display:block; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .fm-meta { font-size:12.5px; color:var(--muted); }
  .fm-actions { display:flex; flex-wrap:wrap; gap:6px; flex:none; }
  .fm-actions button, .fm-actions .btn { padding:7px 12px; font-size:13px; border-radius:9px; }
  .fm-tools { display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); }
  .fm-inline { display:flex; gap:8px; }
  .fm-inline input[type=text] { flex:1 1 auto; }
  .fm-tpl { display:grid; gap:10px; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); }
  .fm-tpl button { width:100%; justify-content:flex-start; text-align:left; background:var(--surface-2);
                   color:var(--text); border:1px solid var(--border); font-weight:600; }
  .fm-tpl button:hover { background:var(--primary-soft); border-color:var(--primary); }
  .fm-tpl small { display:block; font-weight:400; color:var(--muted); margin-top:3px; }
  @media (max-width:640px) {
    /* Никаких таблиц и уезжающих вправо кнопок: строка превращается в карточку. */
    .fm-row { flex-wrap:wrap; }
    .fm-main { flex:1 1 100%; order:1; }
    .fm-icon { order:0; }
    .fm-actions { flex:1 1 100%; order:2; }
    .fm-actions form, .fm-actions .btn { flex:1 1 calc(50% - 3px); }
    .fm-actions button, .fm-actions .btn { width:100%; }
  }
</style>

<div class="fm-head">
  <a class="btn secondary" href="/sites/<?= $sid ?>">← <?= Html::e($site['domain']) ?></a>
  <span class="muted">Диск: <?= Html::e(Path::humanSize($quota['used'])) ?> из <?= Html::e(Path::humanSize($quota['limit'])) ?>
    (<?= (int) $quota['percent'] ?>%)<?= $quota['exceeded'] ? ' — квота исчерпана' : '' ?></span>
</div>

<div class="card">
  <div class="fm-crumbs">
    <a href="<?= $browse('') ?>">Сайт</a>
    <?php foreach ($breadcrumbs as $i => $crumb): if ($i === 0) continue; ?>
      <span>/</span>
      <a href="<?= $browse($crumb['path']) ?>"><?= Html::e($crumb['name']) ?></a>
    <?php endforeach; ?>
  </div>

  <div class="fm-list" style="margin-top:14px;">
    <?php if ($path !== ''): ?>
      <?php $up = (string) dirname($path); ?>
      <a class="fm-row" href="<?= $browse($up === '.' ? '' : $up) ?>" style="text-decoration:none;color:inherit;">
        <span class="fm-icon fm-dir">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="m11 6-6 6 6 6"/></svg>
        </span>
        <span class="fm-main"><span class="fm-name">Наверх</span></span>
      </a>
    <?php endif; ?>

    <?php foreach ($entries as $entry):
      $isPhp = !$entry['is_dir'] && str_ends_with(strtolower($entry['name']), '.php');
      $isEnv = str_starts_with($entry['name'], '.env');
      $isZip = !$entry['is_dir'] && str_ends_with(strtolower($entry['name']), '.zip');
      $cls = $entry['is_dir'] ? 'fm-dir' : ($isEnv ? 'fm-env' : ($isPhp ? 'fm-php' : 'fm-file'));
    ?>
      <div class="fm-row">
        <span class="fm-icon <?= $cls ?>">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
            <?php if ($entry['is_dir']): ?>
              <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>
            <?php elseif ($isPhp): ?>
              <path d="m9 8-5 4 5 4"/><path d="m15 8 5 4-5 4"/>
            <?php elseif ($isEnv): ?>
              <rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>
            <?php else: ?>
              <path d="M6 3h8l4 4v14H6V3Z"/><path d="M14 3v4h4"/>
            <?php endif; ?>
          </svg>
        </span>

        <span class="fm-main">
          <?php if ($entry['is_dir']): ?>
            <a class="fm-name" href="<?= $browse($entry['path']) ?>"><?= Html::e($entry['name']) ?></a>
            <span class="fm-meta">папка</span>
          <?php else: ?>
            <a class="fm-name" href="/sites/<?= $sid ?>/files/edit?path=<?= rawurlencode($entry['path']) ?>"><?= Html::e($entry['name']) ?></a>
            <span class="fm-meta"><?= Html::e(Path::humanSize($entry['size'])) ?><?= $entry['modified'] ? ' · ' . date('d.m.Y H:i', $entry['modified']) : '' ?></span>
          <?php endif; ?>
        </span>

        <span class="fm-actions">
          <?php if (!$entry['is_dir']): ?>
            <a class="btn secondary" href="/sites/<?= $sid ?>/files/edit?path=<?= rawurlencode($entry['path']) ?>">Изменить</a>
            <a class="btn secondary" href="/sites/<?= $sid ?>/files/download?path=<?= rawurlencode($entry['path']) ?><?= $isEnv ? '&confirm=yes' : '' ?>">
              <?= $isEnv ? 'Скачать .env' : 'Скачать' ?>
            </a>
          <?php endif; ?>

          <?php if ($isZip): ?>
            <form method="post" action="/sites/<?= $sid ?>/files/extract"
                  data-confirm="Распаковать <?= Html::e($entry['name']) ?> в эту папку?">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <input type="hidden" name="target" value="<?= Html::e($entry['path']) ?>">
              <button type="submit" class="secondary">Распаковать</button>
            </form>
          <?php endif; ?>

          <form method="post" action="/sites/<?= $sid ?>/files/rename">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <input type="hidden" name="target" value="<?= Html::e($entry['path']) ?>">
            <input type="hidden" name="name" value="">
            <button type="submit" class="secondary"
                    data-prompt="Новое имя" data-prompt-default="<?= Html::e($entry['name']) ?>"
                    data-prompt-target="name">Переименовать</button>
          </form>

          <form method="post" action="/sites/<?= $sid ?>/files/delete"
                data-confirm="Удалить <?= Html::e($entry['name']) ?>? Это необратимо.">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <input type="hidden" name="target" value="<?= Html::e($entry['path']) ?>">
            <button type="submit" class="danger">Удалить</button>
          </form>
        </span>
      </div>
    <?php endforeach; ?>

    <?php if ($entries === []): ?>
      <div class="fm-row"><span class="fm-main muted">Папка пуста</span></div>
    <?php endif; ?>
  </div>
</div>

<div class="card">
  <h3 style="margin-top:0;">Создать</h3>
  <div class="fm-tools">
    <form method="post" action="/sites/<?= $sid ?>/files/newfile">
      <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
      <input type="hidden" name="path" value="<?= Html::e($path) ?>">
      <label>Файл — откроется в редакторе</label>
      <div class="fm-inline">
        <input type="text" name="name" placeholder="index.php" required>
        <button type="submit">Создать</button>
      </div>
      <div class="muted" style="margin-top:6px;">Можно написать просто <code>index</code> — станет <code>index.php</code></div>
    </form>

    <form method="post" action="/sites/<?= $sid ?>/files/mkdir">
      <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
      <input type="hidden" name="path" value="<?= Html::e($path) ?>">
      <label>Папка</label>
      <div class="fm-inline">
        <input type="text" name="name" placeholder="images" required>
        <button type="submit" class="secondary">Создать</button>
      </div>
    </form>

    <form method="post" action="/sites/<?= $sid ?>/files/upload" enctype="multipart/form-data">
      <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
      <input type="hidden" name="path" value="<?= Html::e($path) ?>">
      <label>Загрузить файл или ZIP</label>
      <input type="file" name="file" required>
      <label style="display:flex;align-items:center;gap:8px;margin-top:8px;font-weight:400;">
        <input type="checkbox" name="extract" value="1" style="width:auto;"> распаковать, если это ZIP
      </label>
      <div style="margin-top:10px;"><button type="submit" class="secondary">Загрузить</button></div>
    </form>
  </div>
</div>

<div class="card">
  <h3 style="margin-top:0;">Создать из шаблона</h3>
  <p class="muted" style="margin-top:0;">Готовый рабочий файл вместо пустой страницы.</p>
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
