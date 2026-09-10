#!/usr/bin/env php
<?php

declare(strict_types=1);

/**
 * Телеграм-бот хостинга: отвечает на /start и даёт кнопку, открывающую панель
 * как Mini App.
 *
 * Без него бот выглядел бы сломанным: кнопка меню Mini App настроена, но на
 * любое сообщение бот молчит. Это единственная его задача — никаких команд
 * управления хостингом здесь нет и быть не должно: всё привилегированное
 * делает root-воркер по заданиям из очереди, а не бот по сообщению из чата.
 *
 * Запускается через systemd (templates/systemd-bot.service.tpl), под
 * непривилегированным пользователем — ему не нужен ни root, ни база.
 */

$root = dirname(__DIR__, 3);
require $root . '/hosting/autoload.php';

use Hosting\Support\Env;

Env::loadHosting($root);

$token  = (string) (getenv('TELEGRAM_BOT_TOKEN') ?: '');
$domain = (string) (getenv('HOSTING_ROOT_DOMAIN') ?: '');
$panel  = 'https://panel.' . $domain;

$running = true;
if (function_exists('pcntl_async_signals')) {
    pcntl_async_signals(true);
    pcntl_signal(SIGTERM, function () use (&$running): void { $running = false; });
    pcntl_signal(SIGINT, function () use (&$running): void { $running = false; });
}

/**
 * Один вызов Bot API. Возвращает разобранный ответ или null, если сеть/Telegram подвели.
 *
 * Адрес API вынесен в TELEGRAM_API_BASE: тесты поднимают вместо Telegram
 * локальную заглушку и проверяют, что бот действительно отвечает на /start
 * кнопкой, — иначе это можно было бы проверить только руками на живом боте.
 */
function tg(string $token, string $method, array $params = [], int $timeout = 60): ?array
{
    $base = rtrim((string) (getenv('TELEGRAM_API_BASE') ?: 'https://api.telegram.org'), '/');
    $ch = curl_init($base . '/bot' . $token . '/' . $method);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => http_build_query($params),
        CURLOPT_TIMEOUT        => $timeout + 10,
    ]);
    $body = curl_exec($ch);
    curl_close($ch);

    if (!is_string($body)) {
        return null;
    }
    $decoded = json_decode($body, true);

    return is_array($decoded) ? $decoded : null;
}

// Без токена бот не нужен, но и падать нельзя: systemd крутил бы рестарты
// по кругу. Ждём — токен может появиться после setup.sh.
while ($running && $token === '') {
    fwrite(STDERR, "[hosting-bot] TELEGRAM_BOT_TOKEN не задан — жду настройки (sudo bash hosting/setup.sh)\n");
    for ($i = 0; $i < 60 && $running; $i++) {
        sleep(1);
    }
    Env::loadHosting($root);
    $token = (string) (getenv('TELEGRAM_BOT_TOKEN') ?: '');
}

$me = $running ? tg($token, 'getMe', [], 10) : null;
if ($me !== null && ($me['ok'] ?? false)) {
    fwrite(STDOUT, '[hosting-bot] запущен как @' . ($me['result']['username'] ?? '?') . "\n");
}

// Offset переживает перезапуск: иначе после каждого рестарта бот заново
// отвечал бы на уже обработанные сообщения.
$offsetFile = '/var/lib/hosting/bot-offset';
@mkdir(dirname($offsetFile), 0o750, true);
$offset = (int) @file_get_contents($offsetFile);

$greeting = "Это панель хостинга для PHP-сайтов.\n\n"
    . "Нажмите кнопку ниже — аккаунт создастся сам, регистрация и пароль не нужны.\n"
    . "Внутри: сайт с адресом вида вашсайт." . $domain . ", файловый менеджер, база данных и SSL.";

while ($running) {
    $updates = tg($token, 'getUpdates', [
        'offset'          => $offset,
        'timeout'         => 30,
        'allowed_updates' => json_encode(['message']),
    ]);

    if ($updates === null || !($updates['ok'] ?? false)) {
        // Сеть моргнула или Telegram ответил ошибкой — не шумим в журнал каждую
        // секунду, ждём и пробуем снова.
        sleep(5);
        continue;
    }

    foreach ($updates['result'] ?? [] as $update) {
        $offset = ((int) $update['update_id']) + 1;

        $chatId = $update['message']['chat']['id'] ?? null;
        if ($chatId === null) {
            continue;
        }

        // Кнопки web_app Telegram разрешает только в личных чатах. В группе такая
        // кнопка вернула бы BUTTON_TYPE_INVALID, и бот промолчал бы совсем —
        // поэтому там даём обычную ссылку.
        $isPrivate = ($update['message']['chat']['type'] ?? '') === 'private';
        $button = $isPrivate
            ? ['text' => 'Открыть панель', 'web_app' => ['url' => $panel . '/telegram']]
            : ['text' => 'Открыть панель', 'url' => $panel];

        tg($token, 'sendMessage', [
            'chat_id'      => $chatId,
            'text'         => $greeting,
            'reply_markup' => json_encode(['inline_keyboard' => [[$button]]]),
        ], 10);
    }

    @file_put_contents($offsetFile, (string) $offset);
}

fwrite(STDOUT, "[hosting-bot] остановлен\n");
