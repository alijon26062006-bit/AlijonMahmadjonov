<?php
/** @var int $status
 *  @var string $message
 */
use Hosting\Support\Html;
?>
<div class="card" style="max-width:480px;margin:60px auto;text-align:center;">
  <h1 style="font-size:48px;margin:0;"><?= (int) $status ?></h1>
  <p><?= Html::e($message) ?></p>
  <p><a href="/dashboard">На главную</a></p>
</div>
