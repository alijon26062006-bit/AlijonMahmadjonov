<?php
/**
 * Простой автозагрузчик классов (Composer не нужен).
 * CargoBot\Service\Calculator  ->  src/Service/Calculator.php
 */
spl_autoload_register(function (string $class): void {
    $prefix = 'CargoBot\\';
    if (strncmp($class, $prefix, strlen($prefix)) !== 0) {
        return;
    }
    $relative = substr($class, strlen($prefix));
    $file = __DIR__ . '/' . str_replace('\\', '/', $relative) . '.php';
    if (is_file($file)) {
        require $file;
    }
});
