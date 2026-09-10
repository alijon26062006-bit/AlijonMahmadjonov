<?php
/** @var string $csrf
 *  @var array<string,mixed> $site
 *  @var string $path
 *  @var string $contents
 */
use Hosting\Support\Html;
?>
<p><a href="/sites/<?= (int) $site['id'] ?>/files">&larr; к файлам</a> · <code><?= Html::e($path) ?></code></p>
<div class="card">
  <form method="post" action="/sites/<?= (int) $site['id'] ?>/files/save">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <input type="hidden" name="path" value="<?= Html::e($path) ?>">
    <textarea name="contents" spellcheck="false"
              style="width:100%;min-height:420px;font-family:ui-monospace,Consolas,monospace;font-size:13px;
                     background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:8px;padding:10px;"
    ><?= Html::e($contents) ?></textarea>
    <div style="margin-top:10px;"><button type="submit">Сохранить</button></div>
  </form>
</div>
