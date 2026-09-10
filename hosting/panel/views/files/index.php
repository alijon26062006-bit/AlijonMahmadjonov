<?php
/** @var string $csrf
 *  @var array<string,mixed> $site
 *  @var string $path
 *  @var list<array{name:string,path:string,is_dir:bool,size:int,modified:int}> $entries
 *  @var list<array{name:string,path:string}> $breadcrumbs
 *  @var array{used:int,limit:int,percent:int,exceeded:bool} $quota
 */
use Hosting\Support\Html;
use Hosting\Support\Path;
?>
<p><a href="/sites">&larr; к сайтам</a> · <?= Html::e($site['domain']) ?></p>

<div class="card">
  <div class="muted">Диск: <?= Html::e(Path::humanSize($quota['used'])) ?> / <?= Html::e(Path::humanSize($quota['limit'])) ?>
    (<?= $quota['percent'] ?>%)<?= $quota['exceeded'] ? ' — КВОТА ИСЧЕРПАНА' : '' ?></div>
</div>

<div class="card">
  <div class="muted">
    <a href="/sites/<?= (int) $site['id'] ?>/files">Корень</a>
    <?php foreach ($breadcrumbs as $i => $crumb): if ($i === 0) continue; ?>
      / <a href="/sites/<?= (int) $site['id'] ?>/files?path=<?= rawurlencode($crumb['path']) ?>"><?= Html::e($crumb['name']) ?></a>
    <?php endforeach; ?>
  </div>

  <table style="margin-top:12px;">
    <thead><tr><th>Имя</th><th>Размер</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($entries as $entry): ?>
      <tr>
        <td>
          <?php if ($entry['is_dir']): ?>
            📁 <a href="/sites/<?= (int) $site['id'] ?>/files?path=<?= rawurlencode($entry['path']) ?>"><?= Html::e($entry['name']) ?></a>
          <?php else: ?>
            📄 <a href="/sites/<?= (int) $site['id'] ?>/files/edit?path=<?= rawurlencode($entry['path']) ?>"><?= Html::e($entry['name']) ?></a>
          <?php endif; ?>
        </td>
        <td class="muted"><?= $entry['is_dir'] ? '—' : Html::e(Path::humanSize($entry['size'])) ?></td>
        <td style="white-space:nowrap;">
          <form method="post" action="/sites/<?= (int) $site['id'] ?>/files/delete" style="display:inline;"
                onsubmit="return confirm('Удалить <?= Html::e($entry['name']) ?>?');">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <input type="hidden" name="target" value="<?= Html::e($entry['path']) ?>">
            <button type="submit" class="danger">Удалить</button>
          </form>
        </td>
      </tr>
    <?php endforeach; ?>
    <?php if ($entries === []): ?>
      <tr><td colspan="3" class="muted">Пусто</td></tr>
    <?php endif; ?>
    </tbody>
  </table>
</div>

<div class="card">
  <h3>Загрузить файл</h3>
  <form method="post" action="/sites/<?= (int) $site['id'] ?>/files/upload" enctype="multipart/form-data">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <input type="hidden" name="path" value="<?= Html::e($path) ?>">
    <input type="file" name="file" required>
    <label style="display:flex;align-items:center;gap:6px;margin-top:8px;">
      <input type="checkbox" name="extract" value="1" style="width:auto;"> распаковать, если это ZIP
    </label>
    <div style="margin-top:10px;"><button type="submit">Загрузить</button></div>
  </form>
</div>

<div class="card" style="display:flex;gap:24px;flex-wrap:wrap;">
  <form method="post" action="/sites/<?= (int) $site['id'] ?>/files/mkdir">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <input type="hidden" name="path" value="<?= Html::e($path) ?>">
    <label>Новая папка</label>
    <div style="display:flex;gap:8px;">
      <input type="text" name="name" required>
      <button type="submit" class="secondary">Создать</button>
    </div>
  </form>
  <form method="post" action="/sites/<?= (int) $site['id'] ?>/files/newfile">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <input type="hidden" name="path" value="<?= Html::e($path) ?>">
    <label>Новый файл</label>
    <div style="display:flex;gap:8px;">
      <input type="text" name="name" placeholder="index.php" required>
      <button type="submit" class="secondary">Создать</button>
    </div>
  </form>
</div>
