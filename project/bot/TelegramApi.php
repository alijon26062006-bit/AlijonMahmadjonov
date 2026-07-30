<?php
declare(strict_types=1);

namespace Bot;

use Core\Logger;

/**
 * Minimal Telegram Bot API client built on cURL.
 */
final class TelegramApi
{
    private string $token;
    private string $endpoint;

    public function __construct(string $token)
    {
        $this->token    = $token;
        $this->endpoint = "https://api.telegram.org/bot{$token}/";
    }

    /** Generic API call. */
    public function call(string $method, array $params = []): array
    {
        $ch = curl_init($this->endpoint . $method);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $params,
            CURLOPT_TIMEOUT        => 30,
        ]);
        $raw = curl_exec($ch);
        if ($raw === false) {
            Logger::error('Telegram cURL error: ' . curl_error($ch));
            curl_close($ch);
            return ['ok' => false];
        }
        curl_close($ch);
        $data = json_decode((string) $raw, true) ?: ['ok' => false];
        if (empty($data['ok'])) {
            Logger::error('Telegram API ' . $method . ' failed: ' . $raw);
        }
        return $data;
    }

    public function sendMessage(int|string $chatId, string $text, array $extra = []): array
    {
        return $this->call('sendMessage', array_merge([
            'chat_id'    => $chatId,
            'text'       => $text,
            'parse_mode' => 'HTML',
            'disable_web_page_preview' => true,
        ], $extra));
    }

    public function sendPhoto(int|string $chatId, string $photo, string $caption = '', array $extra = []): array
    {
        return $this->call('sendPhoto', array_merge([
            'chat_id'    => $chatId,
            'photo'      => $photo,
            'caption'    => $caption,
            'parse_mode' => 'HTML',
        ], $extra));
    }

    public function editMessageText(int|string $chatId, int $messageId, string $text, array $extra = []): array
    {
        return $this->call('editMessageText', array_merge([
            'chat_id'    => $chatId,
            'message_id' => $messageId,
            'text'       => $text,
            'parse_mode' => 'HTML',
            'disable_web_page_preview' => true,
        ], $extra));
    }

    public function answerCallbackQuery(string $id, string $text = '', bool $alert = false): array
    {
        return $this->call('answerCallbackQuery', [
            'callback_query_id' => $id,
            'text'              => $text,
            'show_alert'        => $alert,
        ]);
    }

    /** Resolve a file_id to a downloadable path. */
    public function getFileUrl(string $fileId): ?string
    {
        $res = $this->call('getFile', ['file_id' => $fileId]);
        if (empty($res['ok']) || empty($res['result']['file_path'])) {
            return null;
        }
        return "https://api.telegram.org/file/bot{$this->token}/" . $res['result']['file_path'];
    }

    public function setWebhook(string $url, string $secret): array
    {
        return $this->call('setWebhook', [
            'url'             => $url,
            'secret_token'    => $secret,
            'allowed_updates' => json_encode(['message', 'callback_query']),
            'drop_pending_updates' => true,
        ]);
    }
}
