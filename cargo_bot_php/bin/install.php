<?php
/**
 * Создание таблиц и загрузка демо-данных.
 *
 * Запуск в консоли:      php bin/install.php
 * Или через браузер:     https://ваш-домен/bin/install.php?key=СЕКРЕТ
 *                        (ключ = webhook_secret из config.php)
 *
 * Повторный запуск безопасен: существующие данные не затрагиваются.
 */
declare(strict_types=1);

require dirname(__DIR__) . '/src/autoload.php';

use CargoBot\Config;
use CargoBot\Database;
use CargoBot\Schema;
use CargoBot\Seeder;

$isCli = (PHP_SAPI === 'cli');
if (!$isCli) {
    header('Content-Type: text/plain; charset=utf-8');
}

$config = Config::load();

// Через браузер — только со знанием секрета
if (!$isCli) {
    $key = $_GET['key'] ?? '';
    if ($config->webhookSecret() === '' || !hash_equals($config->webhookSecret(), (string) $key)) {
        http_response_code(403);
        exit("Доступ запрещён. Добавьте ?key=<webhook_secret из config.php>\n");
    }
}

$db = new Database($config->db());
echo "Драйвер базы: " . $db->driver() . "\n";

foreach (Schema::statements($db->driver()) as $sql) {
    try {
        $db->pdo()->exec($sql);
    } catch (\PDOException $e) {
        // «индекс уже существует» и подобное — не ошибка
        if (stripos($e->getMessage(), 'exist') === false && stripos($e->getMessage(), 'duplicate') === false) {
            throw $e;
        }
    }
}
echo "Таблицы созданы.\n";

(new Seeder($db))->run();
echo "Демо-данные загружены.\n";

$counts = [
    'тарифов'          => 'tariffs',
    'категорий'        => 'categories',
    'типов доставки'   => 'delivery_types',
    'валют'            => 'currencies',
    'коэффициентов'    => 'coefficients',
    'сборов и скидок'  => 'extra_services',
];
foreach ($counts as $label => $table) {
    // выравниваем по символам: sprintf считает байты и портит кириллицу
    $label .= ':';
    $pad = str_repeat(' ', max(1, 20 - mb_strlen($label)));
    echo '  ' . $label . $pad . $db->value("SELECT COUNT(*) FROM $table") . "\n";
}

echo "\nГотово. Дальше: php bin/set_webhook.php https://ваш-домен/index.php\n";
