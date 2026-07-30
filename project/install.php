<?php
/**
 * Установщик базы данных (одноразовый).
 *
 * Откройте в браузере ОДИН раз:
 *   https://ваш-домен/install.php?key=ВАШ_WEBHOOK_SECRET
 * Чтобы добавить демо-фильмы, добавьте &seed=1:
 *   https://ваш-домен/install.php?key=ВАШ_WEBHOOK_SECRET&seed=1
 *
 * Создаёт все таблицы прямо из database/schema.sql — импорт через phpMyAdmin
 * не нужен.  ПОСЛЕ УСПЕХА УДАЛИТЕ ЭТОТ ФАЙЛ с хостинга.
 */

header('Content-Type: text/plain; charset=utf-8');

$config = require __DIR__ . '/config/config.php';

// Защита: без секрета никто чужой не запустит установку.
if (($_GET['key'] ?? '') !== $config['telegram']['webhook_secret']) {
    http_response_code(403);
    exit("Доступ запрещён. Откройте так:\n  install.php?key=ВАШ_WEBHOOK_SECRET\n");
}

$db = $config['db'];

// --- Подключение к базе ---
try {
    $dsn = "mysql:host={$db['host']};port={$db['port']};dbname={$db['name']};charset={$db['charset']}";
    $pdo = new PDO($dsn, $db['user'], $db['pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
} catch (Throwable $e) {
    exit("❌ Не удалось подключиться к базе:\n" . $e->getMessage()
        . "\n\nПроверьте DB_NAME / DB_USER / DB_PASS в config/config.php\n");
}

/**
 * Выполняет SQL-файл по одному запросу (комментарии «--» удаляются).
 */
$runSqlFile = static function (PDO $pdo, string $file): int {
    $sql = @file_get_contents($file);
    if ($sql === false) {
        throw new RuntimeException("Не найден файл: {$file}");
    }
    $sql = preg_replace('/^\s*--.*$/m', '', $sql) ?? $sql; // убрать строки-комментарии
    $count = 0;
    foreach (explode(';', $sql) as $stmt) {
        $stmt = trim($stmt);
        if ($stmt === '') {
            continue;
        }
        // Пропускаем выбор/создание базы — таблицы идут в уже подключённую базу.
        if (preg_match('/^(CREATE\s+DATABASE|USE)\b/i', $stmt)) {
            continue;
        }
        // Убираем внешние ключи (некоторые хостинги запрещают привилегию REFERENCES).
        $lines = preg_split('/\n/', $stmt) ?: [];
        $lines = array_filter($lines, static function ($l) {
            return !preg_match('/^\s*CONSTRAINT\b/i', $l) && stripos($l, 'FOREIGN KEY') === false;
        });
        $stmt = implode("\n", $lines);
        // Чиним «висячую» запятую перед закрывающей скобкой.
        $stmt = preg_replace('/,(\s*)\)/', '$1)', $stmt) ?? $stmt;

        $pdo->exec($stmt);
        $count++;
    }
    return $count;
};

// --- Создание таблиц ---
try {
    $n = $runSqlFile($pdo, __DIR__ . '/database/schema.sql');
    echo "✅ Структура базы создана (выполнено запросов: {$n}).\n";

    if (($_GET['seed'] ?? '') === '1') {
        $n2 = $runSqlFile($pdo, __DIR__ . '/database/seed.sql');
        echo "✅ Демо-контент добавлен (запросов: {$n2}).\n";
    }
} catch (Throwable $e) {
    exit("❌ Ошибка при создании таблиц:\n" . $e->getMessage() . "\n");
}

// --- Проверка ---
$tables = $pdo->query("SHOW TABLES")->fetchAll(PDO::FETCH_COLUMN);
echo "\n📋 Таблиц в базе: " . count($tables) . "\n   " . implode(', ', $tables) . "\n";

echo "\n🎉 Готово! Теперь:\n";
echo "   1) УДАЛИТЕ файл install.php с хостинга (безопасность).\n";
echo "   2) Откройте: " . $config['app']['base_url'] . "/api/index.php?route=home\n";
echo "   3) Приложение: " . $config['app']['base_url'] . "/miniapp/index.php\n";
