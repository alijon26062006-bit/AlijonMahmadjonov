<?php

namespace CargoBot\Telegram;

/**
 * Клиент Telegram Bot API на cURL.
 * Транспорт можно подменить (используется в тестах).
 */
class Api
{
    private string $token;
    /** @var callable|null */
    private $transport;
    private ?string $lastError = null;

    public function __construct(string $token, ?callable $transport = null)
    {
        $this->token = $token;
        $this->transport = $transport;
    }

    public function lastError(): ?string
    {
        return $this->lastError;
    }

    /**
     * Вызов метода API. Возвращает поле result или null при ошибке.
     * @return mixed
     */
    public function call(string $method, array $params = [])
    {
        $this->lastError = null;
        foreach ($params as $k => $v) {
            if ($v === null) {
                unset($params[$k]);
            } elseif (is_array($v)) {
                $params[$k] = json_encode($v, JSON_UNESCAPED_UNICODE);
            }
        }

        if ($this->transport) {
            $raw = ($this->transport)($method, $params);
        } else {
            $raw = $this->request($method, $params);
        }
        if ($raw === null) {
            return null;
        }

        $data = json_decode($raw, true);
        if (!is_array($data)) {
            $this->lastError = 'Некорректный ответ Telegram: ' . substr((string) $raw, 0, 200);
            return null;
        }
        if (empty($data['ok'])) {
            $this->lastError = ($data['error_code'] ?? '?') . ': ' . ($data['description'] ?? 'неизвестная ошибка');
            return null;
        }
        return $data['result'];
    }

    private function request(string $method, array $params): ?string
    {
        $ch = curl_init("https://api.telegram.org/bot{$this->token}/{$method}");
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $params,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_CONNECTTIMEOUT => 10,
        ]);
        $raw = curl_exec($ch);
        if ($raw === false) {
            $this->lastError = 'cURL: ' . curl_error($ch);
            curl_close($ch);
            return null;
        }
        curl_close($ch);
        return (string) $raw;
    }

    /** @return mixed */
    public function sendMessage($chatId, string $text, ?array $keyboard = null, bool $disablePreview = true)
    {
        return $this->call('sendMessage', [
            'chat_id'                  => $chatId,
            'text'                     => $text,
            'parse_mode'               => 'HTML',
            'reply_markup'             => $keyboard,
            'disable_web_page_preview' => $disablePreview ? 'true' : null,
        ]);
    }

    /** @return mixed */
    public function editMessageText($chatId, int $messageId, string $text, ?array $keyboard = null)
    {
        return $this->call('editMessageText', [
            'chat_id'                  => $chatId,
            'message_id'               => $messageId,
            'text'                     => $text,
            'parse_mode'               => 'HTML',
            'reply_markup'             => $keyboard,
            'disable_web_page_preview' => 'true',
        ]);
    }

    /** @return mixed */
    public function answerCallback(string $callbackId, string $text = '', bool $alert = false)
    {
        return $this->call('answerCallbackQuery', [
            'callback_query_id' => $callbackId,
            'text'              => $text !== '' ? $text : null,
            'show_alert'        => $alert ? 'true' : null,
        ]);
    }

    /** @return mixed */
    public function sendDocument($chatId, string $path, string $caption = '')
    {
        if ($this->transport) {
            return ($this->transport)('sendDocument', ['chat_id' => $chatId, 'path' => $path]);
        }
        $ch = curl_init("https://api.telegram.org/bot{$this->token}/sendDocument");
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST           => true,
            CURLOPT_TIMEOUT        => 60,
            CURLOPT_POSTFIELDS     => [
                'chat_id'  => $chatId,
                'document' => new \CURLFile($path),
                'caption'  => $caption,
            ],
        ]);
        $raw = curl_exec($ch);
        curl_close($ch);
        $data = json_decode((string) $raw, true);
        return is_array($data) && !empty($data['ok']) ? $data['result'] : null;
    }

    public function setWebhook(string $url, string $secret = ''): array
    {
        $result = $this->call('setWebhook', [
            'url'             => $url,
            'secret_token'    => $secret !== '' ? $secret : null,
            'allowed_updates' => ['message', 'callback_query'],
            'drop_pending_updates' => 'true',
        ]);
        return ['ok' => $result !== null, 'error' => $this->lastError];
    }

    /** @return mixed */
    public function getMe()
    {
        return $this->call('getMe');
    }
}
