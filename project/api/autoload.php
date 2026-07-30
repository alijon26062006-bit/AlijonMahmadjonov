<?php
declare(strict_types=1);

/**
 * PSR-4 style autoloader for the API layer.
 *   Core\*        -> api/core/*.php
 *   Models\*      -> api/models/*.php
 *   Controllers\* -> api/controllers/*.php
 */
spl_autoload_register(static function (string $class): void {
    $map = [
        'Core\\'        => __DIR__ . '/core/',
        'Models\\'      => __DIR__ . '/models/',
        'Controllers\\' => __DIR__ . '/controllers/',
    ];
    foreach ($map as $prefix => $dir) {
        if (str_starts_with($class, $prefix)) {
            $file = $dir . substr($class, strlen($prefix)) . '.php';
            if (is_file($file)) {
                require $file;
            }
            return;
        }
    }
});
