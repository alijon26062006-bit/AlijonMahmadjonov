<?php
/** @var string $csrf
 *  @var array<string,mixed> $site
 *  @var string $path
 *  @var string $contents
 *  @var array{ok:bool,line:int|null,message:string|null}|null $syntax
 */
use Hosting\Service\PhpSyntax;
use Hosting\Support\Html;

$syntax ??= null;
$isPhp = str_ends_with(strtolower($path), '.php');
?>
<style>
  .ed-top { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:14px; }
  .ed-top .ed-path { font-family:ui-monospace,monospace; font-size:14px; }
  .ed-wrap { display:flex; border:1px solid var(--border); border-radius:var(--r-md);
             overflow:hidden; background:#0E1A38; }
  .ed-gutter { flex:none; width:52px; padding:12px 8px; margin:0; text-align:right;
               font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace; color:#64748B;
               background:#0A1330; white-space:pre; overflow:hidden; user-select:none; }
  .ed-area { flex:1 1 auto; min-height:60vh; padding:12px; border:0; border-radius:0; resize:vertical;
             font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace; color:#E2E8F0;
             background:#0E1A38; white-space:pre; overflow-wrap:normal; overflow-x:auto; tab-size:4; }
  .ed-area:focus { outline:none; box-shadow:none; }
  .ed-bar { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:14px; }
  .ed-status { font-size:13px; color:var(--muted); }
  .ed-status.is-dirty { color:var(--warning); font-weight:600; }
  .ed-hint { font-size:13px; color:var(--muted); }
  .ed-error { background:var(--danger-soft); border:1px solid #F7C9C9; color:#991B1B;
              border-radius:var(--r-md); padding:12px 14px; margin-bottom:14px; font-size:14px; }
  @media (max-width:640px) {
    .ed-gutter { width:38px; padding:12px 5px; }
    .ed-area { font-size:12.5px; min-height:52vh; }
    .ed-bar button, .ed-bar .btn { flex:1 1 auto; }
  }
</style>

<div class="ed-top">
  <a class="btn secondary" href="/sites/<?= (int) $site['id'] ?>/files?path=<?= rawurlencode((string) dirname($path) === '.' ? '' : (string) dirname($path)) ?>">← К файлам</a>
  <span class="ed-path"><?= Html::e($path) ?></span>
</div>

<?php if ($syntax !== null && !$syntax['ok']): ?>
  <div class="ed-error">
    <strong><?= Html::e(PhpSyntax::describe($syntax)) ?></strong><br>
    Файл не сохранён. Исправьте ошибку и нажмите «Сохранить» ещё раз —
    или сохраните как есть, если знаете, что делаете.
  </div>
<?php endif; ?>

<div class="card">
  <form method="post" action="/sites/<?= (int) $site['id'] ?>/files/save" id="editor-form">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <input type="hidden" name="path" value="<?= Html::e($path) ?>">

    <div class="ed-wrap">
      <pre class="ed-gutter" id="gutter" aria-hidden="true"></pre>
      <textarea class="ed-area" id="code" name="contents" spellcheck="false"
                autocapitalize="off" autocomplete="off" autocorrect="off" wrap="off"
                data-error-line="<?= (int) ($syntax['line'] ?? 0) ?>"><?= Html::e($contents) ?></textarea>
    </div>

    <div class="ed-bar">
      <button type="submit" id="save-button">Сохранить</button>
      <?php if ($syntax !== null && !$syntax['ok']): ?>
        <button type="submit" name="force" value="1" class="secondary">Сохранить с ошибкой</button>
      <?php endif; ?>
      <span class="ed-status" id="editor-status">Сохранено</span>
      <span class="ed-hint">Ctrl/Cmd + S — сохранить<?= $isPhp ? ' · синтаксис PHP проверяется перед записью' : '' ?></span>
    </div>
  </form>
</div>

<script src="/assets/editor.js"></script>
