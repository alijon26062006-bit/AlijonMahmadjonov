<?php

namespace CargoBot;

use CargoBot\Repository\SettingsRepo;
use CargoBot\Repository\StateRepo;
use CargoBot\Repository\UserRepo;
use CargoBot\Service\Audit;
use CargoBot\Service\Calculator;
use CargoBot\Service\Notify;
use CargoBot\Telegram\Api;

/**
 * Контейнер зависимостей и контекст текущего обновления.
 * Передаётся во все обработчики.
 */
class Bot
{
    public Config $config;
    public Database $db;
    public Api $api;
    public StateRepo $state;
    public SettingsRepo $settings;
    public UserRepo $users;
    public Audit $audit;
    public Notify $notify;
    public Calculator $calc;

    // Контекст текущего апдейта
    public int $chatId = 0;
    public int $tgId = 0;
    public ?array $user = null;
    public bool $isAdmin = false;
    public string $lang = 'ru';
    public ?int $messageId = null;
    public ?string $callbackId = null;

    public function __construct(Config $config, ?Database $db = null, ?Api $api = null)
    {
        $this->config   = $config;
        $this->db       = $db ?: new Database($config->db());
        $this->api      = $api ?: new Api($config->token());
        $this->state    = new StateRepo($this->db);
        $this->settings = new SettingsRepo($this->db);
        $this->users    = new UserRepo($this->db);
        $this->audit    = new Audit($this->db);
        $this->notify   = new Notify($this->db, $this->api, $config->adminIds());
        $this->calc     = new Calculator($this->db);
    }

    public function text(string $key): string
    {
        return Texts::get($key, $this->lang);
    }

    /** Отправить сообщение в текущий чат. */
    public function send(string $text, ?array $keyboard = null): void
    {
        $this->api->sendMessage($this->chatId, $text, $keyboard);
    }

    /** Изменить сообщение, на кнопку которого нажали (для inline-меню). */
    public function edit(string $text, ?array $keyboard = null): void
    {
        if ($this->messageId === null) {
            $this->send($text, $keyboard);
            return;
        }
        $ok = $this->api->editMessageText($this->chatId, $this->messageId, $text, $keyboard);
        if ($ok === null) {
            // сообщение могло быть удалено или текст не изменился — отправим новое
            $err = (string) $this->api->lastError();
            if (strpos($err, 'message is not modified') === false) {
                $this->send($text, $keyboard);
            }
        }
    }

    public function answer(string $text = '', bool $alert = false): void
    {
        if ($this->callbackId !== null) {
            $this->api->answerCallback($this->callbackId, $text, $alert);
        }
    }

    public function userId(): ?int
    {
        return $this->user ? (int) $this->user['id'] : null;
    }

    public function dataDir(): string
    {
        return dirname(__DIR__) . '/data';
    }

    public function log(string $message): void
    {
        $file = $this->config->get('log_file');
        if (!$file) {
            return;
        }
        $dir = dirname($file);
        if (!is_dir($dir)) {
            @mkdir($dir, 0775, true);
        }
        @file_put_contents($file, date('Y-m-d H:i:s') . ' ' . $message . PHP_EOL, FILE_APPEND);
    }
}
