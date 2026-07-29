<?php
// ============================================================================
// РЕАЛТАЙМ ДЛЯ ОБЫЧНОГО ХОСТИНГА — доставка сообщений «как в Telegram»
// через сервис Pusher (pusher.com). На обычном PHP-хостинге свой постоянный
// сервер держать нельзя, поэтому мгновенную доставку берёт на себя Pusher.
// ----------------------------------------------------------------------------
// КАК ВКЛЮЧИТЬ (5 минут, один раз):
//   1) Зарегистрируйся на https://pusher.com (бесплатный тариф).
//   2) Создай приложение: Channels → Create app.
//   3) В разделе «App Keys» будут 4 значения — впиши их ниже.
//   4) Загрузи этот файл рядом с messenger.php. Всё.
//
// Пока значения пустые — реалтайм ВЫКЛЮЧЕН, и мессенджер работает по-старому
// (обычный опрос). Ничего не сломается: включение полностью безопасно.
// ============================================================================

define('PUSHER_APP_ID',  '');   // например: 1234567
define('PUSHER_KEY',     '');   // например: a1b2c3d4e5f6...
define('PUSHER_SECRET',  '');   // например: 9f8e7d6c5b4a... (держи в секрете!)
define('PUSHER_CLUSTER', '');   // например: eu  (или ap1, mt1 — как в панели Pusher)

/**
 * Отправляет мгновенное событие в канал Pusher.
 * Вызывается из messenger.php при новом сообщении. Ничего не задерживает:
 * таймаут короткий, любые сбои молча игнорируются (реалтайм — это «бонус»,
 * а надёжной доставкой остаётся сохранение в базу).
 *
 * @param string $channel имя канала, напр. "chat-123"
 * @param string $event   имя события, напр. "message"
 * @param array  $data    полезные данные события
 */
function pusher_publish($channel, $event, array $data) {
    // Реалтайм не настроен — тихо выходим (работает опрос).
    if (!defined('PUSHER_KEY') || PUSHER_KEY === '' || PUSHER_SECRET === ''
        || PUSHER_APP_ID === '' || PUSHER_CLUSTER === '') return;
    if (!function_exists('curl_init')) return;

    // Тело запроса по протоколу Pusher: данные события — это СТРОКА JSON.
    $body = json_encode([
        'name'     => $event,
        'channels' => [$channel],
        'data'     => json_encode($data, JSON_UNESCAPED_UNICODE),
    ], JSON_UNESCAPED_UNICODE);

    $path = '/apps/' . PUSHER_APP_ID . '/events';

    // Параметры авторизации (обязательно отсортированы по алфавиту для подписи).
    $params = [
        'auth_key'       => PUSHER_KEY,
        'auth_timestamp' => (string)time(),
        'auth_version'   => '1.0',
        'body_md5'       => md5($body),
    ];
    ksort($params);
    $query = http_build_query($params);

    // Подпись запроса (HMAC-SHA256) — как требует Pusher REST API.
    $toSign    = "POST\n" . $path . "\n" . $query;
    $signature = hash_hmac('sha256', $toSign, PUSHER_SECRET);

    $url = 'https://api-' . PUSHER_CLUSTER . '.pusher.com' . $path
         . '?' . $query . '&auth_signature=' . $signature;

    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $body,
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 2,   // не тормозим ответ пользователю
        CURLOPT_CONNECTTIMEOUT => 1,
    ]);
    @curl_exec($ch);
    @curl_close($ch);
}
