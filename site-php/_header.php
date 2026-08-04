<?php
/* =========================================================
   ALIJON — САЙТ В ОДНОМ ФАЙЛЕ
   =========================================================
   Загрузи этот файл в public_html — и всё работает.
   Больше ничего загружать не нужно: стили, шрифты, Three.js
   и весь код уже внутри.

   ЗДЕСЬ ЖЕ ПРИНИМАЮТСЯ ЗАЯВКИ С ФОРМЫ и уходят в твоего
   Telegram-бота. Заполни две строки ниже.
   ========================================================= */

/* ---------- НАСТРОЙКИ ЗАЯВОК ---------- */

/* 1. Токен бота. Получить: напиши @BotFather → /newbot
      Выглядит так: 1234567890:AAF...  */
$BOT_TOKEN = '';

/* 2. Твой числовой ID. Получить: напиши @userinfobot
      Выглядит так: 123456789  */
$CHAT_ID = '';

/* Пока эти строки пустые, заявка не отправляется ботом:
   сайт просто скопирует её в буфер и откроет твой чат. */


/* =========================================================
   ОБРАБОТКА ЗАЯВКИ
   Ниже трогать не нужно.
   ========================================================= */

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type: application/json; charset=utf-8');

    $raw  = file_get_contents('php://input');
    $data = json_decode($raw, true);
    if (!is_array($data)) { $data = $_POST; }

    $clean = static function ($value, $limit) {
        $value = is_string($value) ? $value : '';
        $value = trim(strip_tags($value));
        return mb_substr($value, 0, $limit, 'UTF-8');
    };

    $name     = $clean($data['name']     ?? '', 100);
    $telegram = $clean($data['telegram'] ?? '', 100);
    $project  = $clean($data['project']  ?? '', 3000);
    $budget   = $clean($data['budget']   ?? '', 100);
    $deadline = $clean($data['deadline'] ?? '', 100);

    // Ловушка для ботов: живой человек это поле не видит и не заполняет
    if (!empty($data['website'])) {
        echo json_encode(['ok' => true]);
        exit;
    }

    if (mb_strlen($name) < 2 || mb_strlen($telegram) < 2 || mb_strlen($project) < 10) {
        http_response_code(422);
        echo json_encode(['ok' => false, 'error' => 'Заполни имя, Telegram и описание проекта']);
        exit;
    }

    if ($BOT_TOKEN === '' || $CHAT_ID === '') {
        // Бот не настроен — сайт откроет Telegram как запасной путь
        http_response_code(503);
        echo json_encode(['ok' => false, 'error' => 'Бот не настроен']);
        exit;
    }

    $lines = [
        '<b>Новая заявка с сайта</b>',
        '',
        '<b>Имя:</b> ' . htmlspecialchars($name, ENT_QUOTES, 'UTF-8'),
        '<b>Telegram:</b> ' . htmlspecialchars($telegram, ENT_QUOTES, 'UTF-8'),
        '<b>Проект:</b> ' . htmlspecialchars($project, ENT_QUOTES, 'UTF-8'),
    ];
    if ($budget !== '')   { $lines[] = '<b>Бюджет:</b> ' . htmlspecialchars($budget, ENT_QUOTES, 'UTF-8'); }
    if ($deadline !== '') { $lines[] = '<b>Срок:</b> ' . htmlspecialchars($deadline, ENT_QUOTES, 'UTF-8'); }
    $lines[] = '';
    $lines[] = 'IP: ' . ($_SERVER['REMOTE_ADDR'] ?? '—');

    $payload = http_build_query([
        'chat_id'                  => $CHAT_ID,
        'text'                     => implode("\n", $lines),
        'parse_mode'               => 'HTML',
        'disable_web_page_preview' => true,
    ]);

    $url = 'https://api.telegram.org/bot' . $BOT_TOKEN . '/sendMessage';
    $sent = false;

    // На разных хостингах доступно разное: сначала пробуем cURL,
    // если его нет — обычный поток
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $payload,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 15,
        ]);
        $response = curl_exec($ch);
        $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        $sent = ($code === 200);
    } else {
        $context = stream_context_create([
            'http' => [
                'method'        => 'POST',
                'header'        => "Content-Type: application/x-www-form-urlencoded\r\n",
                'content'       => $payload,
                'timeout'       => 15,
                'ignore_errors' => true,
            ],
        ]);
        $response = @file_get_contents($url, false, $context);
        $sent = ($response !== false && strpos($response, '"ok":true') !== false);
    }

    if ($sent) {
        echo json_encode(['ok' => true]);
    } else {
        http_response_code(502);
        echo json_encode(['ok' => false, 'error' => 'Не удалось отправить в Telegram']);
    }
    exit;
}
?>
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">
<title>Alijon — Web, Telegram-боты и AI-решения</title>
<meta name="description" content="Создаю современные веб-сайты, Telegram-ботов, Mini Apps и AI-решения. Full Stack разработка.">
<meta name="theme-color" content="#05070D">
<meta property="og:type" content="website">
<meta property="og:title" content="Alijon — Web, Telegram-боты и AI-решения">
<meta property="og:description" content="Современные веб-сайты, Telegram-боты, Mini Apps и AI-решения.">
