<?php
/** @var array<string,mixed> $site
 *  @var string $type
 *  @var list<string> $lines
 */
use Hosting\Support\Html;
?>
<p><a href="/sites">&larr; к сайтам</a> · <?= Html::e($site['domain']) ?></p>
<div class="card">
  <div style="margin-bottom:10px;">
    <a class="btn <?= $type === 'error' ? '' : 'secondary' ?>" href="?type=error">Ошибки PHP</a>
    <a class="btn <?= $type === 'access' ? '' : 'secondary' ?>" href="?type=access">Доступ (nginx)</a>
  </div>
  <p class="muted">Последние <?= count($lines) ?> строк</p>
  <pre style="max-height:70vh;"><?php foreach ($lines as $line): ?><?= Html::e($line) ?>
<?php endforeach; if ($lines === []): ?>(пусто)<?php endif; ?></pre>
</div>
