<?php

declare(strict_types=1);

/**
 * Простой PSR-4-подобный автозагрузчик без composer — проект сознательно без внешних
 * PHP-зависимостей на рантайме (меньше поверхность атаки на shared-хостинге).
 *
 *   Hosting\Worker\Foo\Bar  →  hosting/worker/src/Foo/Bar.php
 *   Hosting\Foo\Bar         →  hosting/panel/src/Foo/Bar.php
 */

spl_autoload_register(static function (string $class): void {
    $base = __DIR__;

    $map = [
        'Hosting\\Worker\\' => $base . '/worker/src/',
        'Hosting\\'         => $base . '/panel/src/',
    ];

    foreach ($map as $prefix => $dir) {
        if (!str_starts_with($class, $prefix)) {
            continue;
        }
        $relative = substr($class, strlen($prefix));
        $file = $dir . str_replace('\\', '/', $relative) . '.php';
        if (is_file($file)) {
            require $file;
        }
        return;
    }
});
