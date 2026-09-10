#!/usr/bin/env php
<?php

declare(strict_types=1);

/**
 * Запускает все hosting/tests/test_*.php по очереди. Без внешних зависимостей
 * (PHPUnit на сервере может не стоять) — просто assert-функции из bootstrap.php.
 *
 *   php hosting/tests/run.php
 */

require __DIR__ . '/bootstrap.php';

$files = glob(__DIR__ . '/test_*.php') ?: [];
sort($files, SORT_STRING);

if ($files === []) {
    fwrite(STDERR, "Тестовые файлы не найдены\n");
    exit(1);
}

foreach ($files as $file) {
    echo basename($file) . "\n";
    HostingTestRunner::run($file);
    echo "\n";
}

exit(HostingTestRunner::summary());
