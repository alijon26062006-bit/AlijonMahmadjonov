<?php
/**
 * Autoloader for the bot layer. Reuses the API's Core/Models classes and adds
 * the Bot\ namespace.
 */
spl_autoload_register(static function (string $class): void {
    $map = [
        'Bot\\'    => __DIR__ . '/',
        'Core\\'   => __DIR__ . '/../api/core/',
        'Models\\' => __DIR__ . '/../api/models/',
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
