<?php

namespace CargoBot\Handler;

use CargoBot\Bot;
use CargoBot\Handler\Admin\AdminHandler;
use CargoBot\Handler\Admin\BroadcastHandler;
use CargoBot\Handler\Admin\CrudHandler;
use CargoBot\Handler\Admin\OrdersHandler;
use CargoBot\Handler\Admin\TracksHandler;
use CargoBot\Handler\User\CalcHandler;
use CargoBot\Handler\User\InfoHandler;
use CargoBot\Handler\User\OrderHandler;
use CargoBot\Handler\User\StartHandler;
use CargoBot\Handler\User\TrackHandler;
use CargoBot\Texts;

/** Разбирает апдейт Telegram и передаёт его нужному обработчику. */
class Router
{
    private Bot $bot;

    public function __construct(Bot $bot)
    {
        $this->bot = $bot;
    }

    public function handle(array $update): void
    {
        if (isset($update['callback_query'])) {
            $this->onCallback($update['callback_query']);
        } elseif (isset($update['message'])) {
            $this->onMessage($update['message']);
        }
    }

    // ------------------------------------------------------------------
    private function prepare(array $from, int $chatId): void
    {
        $bot = $this->bot;
        $bot->chatId = $chatId;
        $bot->tgId = (int) $from['id'];

        $fullName = trim(($from['first_name'] ?? '') . ' ' . ($from['last_name'] ?? ''));
        [$user, $created] = $bot->users->upsert(
            $bot->tgId,
            $from['username'] ?? null,
            $fullName !== '' ? $fullName : null
        );
        $bot->user = $user;
        $bot->lang = $user['language'] ?? 'ru';
        $bot->isAdmin = $bot->notify->isAdmin($bot->tgId);

        if ($created) {
            $bot->audit->log($bot->tgId, 'create', 'users', (int) $user['id'], null, [
                'tg_id'    => (string) $bot->tgId,
                'username' => (string) ($from['username'] ?? ''),
            ]);
        }
    }

    // ------------------------------------------------------------------
    private function onMessage(array $message): void
    {
        if (!isset($message['from'], $message['chat'])) {
            return;
        }
        $bot = $this->bot;
        $bot->messageId = null;
        $bot->callbackId = null;
        $this->prepare($message['from'], (int) $message['chat']['id']);

        $text = trim((string) ($message['text'] ?? ''));

        // 1. Команды
        if ($text === '/start' || strncmp($text, '/start ', 7) === 0) {
            $bot->state->clear($bot->chatId);
            (new StartHandler($bot))->start();
            return;
        }
        if ($text === '/admin') {
            if ($bot->isAdmin) {
                $bot->state->clear($bot->chatId);
                (new AdminHandler($bot))->menu(false);
            } else {
                $bot->send('Эта команда доступна только администраторам.');
            }
            return;
        }
        if ($text === '/cancel' || $text === Texts::get('btn_cancel', $bot->lang)) {
            $bot->state->clear($bot->chatId);
            $bot->send($bot->text('cancelled'), Texts::mainMenu($bot->lang));
            return;
        }

        // 2. Активный пошаговый диалог
        $state = $bot->state->state($bot->chatId);
        if ($state !== null) {
            if ($this->dispatchState($state, $message)) {
                return;
            }
            $bot->state->clear($bot->chatId);
        }

        // 3. Кнопки главного меню
        $menu = [
            'btn_calc'       => fn() => (new CalcHandler($bot))->start(),
            'btn_track'      => fn() => (new TrackHandler($bot))->start(),
            'btn_order'      => fn() => (new OrderHandler($bot))->start(),
            'btn_tariffs'    => fn() => (new InfoHandler($bot))->tariffs(),
            'btn_warehouses' => fn() => (new InfoHandler($bot))->warehouses(),
            'btn_contacts'   => fn() => (new InfoHandler($bot))->contacts(),
            'btn_faq'        => fn() => (new InfoHandler($bot))->faq(),
        ];
        foreach ($menu as $key => $action) {
            if ($text === Texts::get($key, $bot->lang)) {
                $action();
                return;
            }
        }

        // 4. Ничего не подошло
        (new StartHandler($bot))->fallback();
    }

    /** Передаёт сообщение обработчику активного состояния. @return bool обработано ли */
    private function dispatchState(string $state, array $message): bool
    {
        $bot = $this->bot;
        [$group, $step] = array_pad(explode(':', $state, 2), 2, '');

        switch ($group) {
            case 'calc':
                return (new CalcHandler($bot))->onState($step, $message);
            case 'order':
                return (new OrderHandler($bot))->onState($step, $message);
            case 'track':
                return (new TrackHandler($bot))->onState($step, $message);
            case 'crud':
                return $bot->isAdmin && (new CrudHandler($bot))->onState($step, $message);
            case 'bc':
                return $bot->isAdmin && (new BroadcastHandler($bot))->onState($step, $message);
            case 'trk':
                return $bot->isAdmin && (new TracksHandler($bot))->onState($step, $message);
        }
        return false;
    }

    // ------------------------------------------------------------------
    private function onCallback(array $cb): void
    {
        if (!isset($cb['from'], $cb['message'])) {
            return;
        }
        $bot = $this->bot;
        $this->prepare($cb['from'], (int) $cb['message']['chat']['id']);
        $bot->messageId = (int) $cb['message']['message_id'];
        $bot->callbackId = (string) $cb['id'];

        $data = (string) ($cb['data'] ?? '');
        $prefix = explode(':', $data)[0];

        // Разделы админки требуют прав администратора
        if (($prefix === 'adm' || $prefix === 'e') && !$bot->isAdmin) {
            $bot->answer('Доступно только администраторам', true);
            return;
        }

        switch ($prefix) {
            case 'noop':
                $bot->answer();
                return;
            case 'calc':
                (new CalcHandler($bot))->onCallback($data);
                return;
            case 'order':
                (new OrderHandler($bot))->onCallback($data);
                return;
            case 'faq':
                (new InfoHandler($bot))->onCallback($data);
                return;
            case 'e':
                (new CrudHandler($bot))->onCallback($data);
                return;
            case 'adm':
                $this->adminCallback($data);
                return;
        }
        $bot->answer();
    }

    private function adminCallback(string $data): void
    {
        $bot = $this->bot;
        $parts = explode(':', $data);
        $action = $parts[1] ?? '';

        if (in_array($action, ['orders', 'order', 'ostatus'], true)) {
            (new OrdersHandler($bot))->onCallback($data);
            return;
        }
        if (in_array($action, ['tracks', 'track', 'tstatus', 'track_new'], true)) {
            (new TracksHandler($bot))->onCallback($data);
            return;
        }
        if (in_array($action, ['broadcast', 'bc_go', 'bc_next'], true)) {
            (new BroadcastHandler($bot))->onCallback($data);
            return;
        }
        (new AdminHandler($bot))->onCallback($data);
    }
}
