<?php
declare(strict_types=1);

/**
 * Заглушка Bot API для тестов. Поднимается встроенным сервером PHP и отвечает
 * как Telegram: getMe — данные бота, getUpdates — одно сообщение «/start»
 * (один раз), sendMessage — записывает полученное в файл, чтобы тест мог
 * проверить, что именно бот отправил пользователю.
 *
 * Путь к файлу с записями передаётся через FAKE_TG_LOG.
 */

$log = (string) getenv('FAKE_TG_LOG');
$method = basename((string) parse_url((string) ($_SERVER['REQUEST_URI'] ?? ''), PHP_URL_PATH));
$body = file_get_contents('php://input') ?: '';
parse_str($body, $params);

header('Content-Type: application/json');

switch ($method) {
    case 'getMe':
        echo json_encode(['ok' => true, 'result' => ['id' => 777, 'username' => 'testhostbot', 'first_name' => 'TestHost']]);
        break;

    case 'getUpdates':
        // Отдаём сообщение ровно один раз: бот обязан запомнить offset и не
        // отвечать на него по кругу.
        $stamp = $log . '.updates-served';
        if (file_exists($stamp)) {
            echo json_encode(['ok' => true, 'result' => []]);
            break;
        }
        touch($stamp);
        echo json_encode(['ok' => true, 'result' => [[
            'update_id' => 1001,
            'message'   => [
                'message_id' => 5,
                'chat' => ['id' => 42, 'type' => 'private'],
                'from' => ['id' => 42, 'first_name' => 'Алиджон'],
                'text' => '/start',
            ],
        ]]]);
        break;

    case 'sendMessage':
        file_put_contents($log, json_encode($params, JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND);
        echo json_encode(['ok' => true, 'result' => ['message_id' => 6]]);
        break;

    default:
        echo json_encode(['ok' => true, 'result' => []]);
}
