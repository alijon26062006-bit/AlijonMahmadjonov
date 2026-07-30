<?php
declare(strict_types=1);

namespace Bot;

use Core\ImageProcessor;
use Core\OpenAiClient;
use Models\User;

/**
 * Top-level Telegram update dispatcher: greetings, user navigation menu,
 * admin panel, callback handling. Content wizards are delegated to AdminFlow.
 */
final class Bot
{
    private TelegramApi $api;
    private AdminFlow $flow;
    private AiFlow $aiFlow;
    private EpisodeFlow $episodeFlow;
    private ContentRepo $repo;
    private StateStore $store;
    private array $cfg;

    public function __construct(array $config)
    {
        $this->cfg   = $config;
        $this->api   = new TelegramApi($config['telegram']['bot_token']);
        $this->store = new StateStore();
        $this->repo  = new ContentRepo();
        $media       = new Media($this->api, $config['app']['uploads_dir']);
        $this->flow  = new AdminFlow(
            $this->api, $media, $this->repo, $this->store,
            $config['telegram']['miniapp_url']
        );
        $this->aiFlow = new AiFlow(
            $this->api,
            $media,
            $this->repo,
            $this->store,
            new ImageProcessor($config['app']['uploads_dir']),
            new OpenAiClient($config['openai'] ?? []),
            $config['app']['uploads_dir'],
            $config['telegram']['miniapp_url']
        );
        $this->episodeFlow = new EpisodeFlow($this->api, $this->repo, $this->store);

        // Values hardcoded in config.php take priority: sync them into settings
        // so every flow (archive posts, deep links) uses the same source.
        // Guarded so a partially updated deployment can never brick the bot.
        if (method_exists($this->repo, 'getSetting') && method_exists($this->repo, 'setSetting')) {
            try {
                $cfgChannel = (string) ($config['telegram']['archive_channel_id'] ?? '');
                if ($cfgChannel !== '' && $this->repo->getSetting('archive_channel_id') !== $cfgChannel) {
                    $this->repo->setSetting('archive_channel_id', $cfgChannel);
                }
                $cfgUser = ltrim((string) ($config['telegram']['bot_username'] ?? ''), '@');
                if ($cfgUser !== '' && $this->repo->getSetting('bot_username') !== $cfgUser) {
                    $this->repo->setSetting('bot_username', $cfgUser);
                }
            } catch (\Throwable $e) {
                \Core\Logger::error('Settings sync skipped: ' . $e->getMessage());
            }
        }
    }

    public function handleUpdate(array $update): void
    {
        if (isset($update['callback_query'])) {
            $this->onCallback($update['callback_query']);
            return;
        }
        if (isset($update['message'])) {
            $this->onMessage($update['message']);
        }
    }

    // ---- Messages -------------------------------------------------------

    private function onMessage(array $msg): void
    {
        $chatId = (int) ($msg['chat']['id'] ?? 0);
        $from   = $msg['from'] ?? [];
        $tid    = (int) ($from['id'] ?? 0);
        $text   = trim((string) ($msg['text'] ?? ''));

        // Register / refresh the user
        if ($from) {
            (new User())->upsertFromTelegram($from);
        }

        // Global commands ALWAYS break out of any active wizard.
        $isCommand = $text === '/start' || str_starts_with($text, '/start ')
            || $text === '/admin' || $text === "\u{2699} \u{41F}\u{430}\u{43D}\u{435}\u{43B}\u{44C}"
            || $text === '/cancel';
        if ($isCommand) {
            $this->store->clear($tid);
        }

        // Active admin dialog takes priority (unless a global command was sent)
        if (!$isCommand && $this->isAdmin($tid)) {
            $st = $this->store->get($tid);
            if ($st['state'] === 'set_channel') {
                $this->onSetChannel($chatId, $tid, $msg);
                return;
            }
            if ($this->aiFlow->handle($chatId, $tid, $msg)) {
                return;
            }
            if ($this->episodeFlow->handle($chatId, $tid, $msg)) {
                return;
            }
            if ($this->flow->handle($chatId, $tid, $msg)) {
                return;
            }
        }

        if ($text === '/cancel') {
            $this->api->sendMessage($chatId, "\u{274C} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{435}\u{43D}\u{43E}. \u{41D}\u{430}\u{43F}\u{438}\u{448}\u{438}\u{442}\u{435} /admin \u{434}\u{43B}\u{44F} \u{43C}\u{435}\u{43D}\u{44E}.", [
                'reply_markup' => json_encode(['remove_keyboard' => true]),
            ]);
            return;
        }

        if ($text === '/start' || str_starts_with($text, '/start ')) {
            // Deep link from the archive channel: /start movie_<id> or ep_<m>_<s>_<e>
            $param = trim((string) substr($text, 6));
            if ($param !== '' && $this->handleDeepLink($chatId, $param)) {
                return;
            }
            $this->sendWelcome($chatId, $from);
            return;
        }

        if ($text === '/admin' || $text === "\u{2699} \u{41F}\u{430}\u{43D}\u{435}\u{43B}\u{44C}") {
            $this->sendAdminPanel($chatId, $tid);
            return;
        }

        // User navigation (reply keyboard labels)
        switch ($text) {
            case "\u{1F3AC} \u{41E}\u{442}\u{43A}\u{440}\u{44B}\u{442}\u{44C} \u{43A}\u{438}\u{43D}\u{43E}":
                // Handled natively by the web_app keyboard button; nothing to do.
                return;
            case "\u{1F525} \u{41D}\u{43E}\u{432}\u{438}\u{43D}\u{43A}\u{438}":
                $this->openSection($chatId, 'new', "\u{1F525} \u{41D}\u{43E}\u{432}\u{438}\u{43D}\u{43A}\u{438}");
                return;
            case "\u{1F39E} \u{41A}\u{430}\u{442}\u{435}\u{433}\u{43E}\u{440}\u{438}\u{438}":
                $this->sendCategories($chatId);
                return;
            case "\u{2764}\u{FE0F} \u{418}\u{437}\u{431}\u{440}\u{430}\u{43D}\u{43D}\u{43E}\u{435}":
                $this->openSection($chatId, 'favorites', "\u{2764}\u{FE0F} \u{418}\u{437}\u{431}\u{440}\u{430}\u{43D}\u{43D}\u{43E}\u{435}");
                return;
            case "\u{1F552} \u{418}\u{441}\u{442}\u{43E}\u{440}\u{438}\u{44F}":
                $this->openSection($chatId, 'history', "\u{1F552} \u{418}\u{441}\u{442}\u{43E}\u{440}\u{438}\u{44F}");
                return;
            case "\u{2699} \u{41D}\u{430}\u{441}\u{442}\u{440}\u{43E}\u{439}\u{43A}\u{438}":
                $this->api->sendMessage($chatId, "\u{2699} <b>\u{41D}\u{430}\u{441}\u{442}\u{440}\u{43E}\u{439}\u{43A}\u{438}</b>\n\n\u{42F}\u{437}\u{44B}\u{43A} \u{438}\u{43D}\u{442}\u{435}\u{440}\u{444}\u{435}\u{439}\u{441}\u{430} \u{438} \u{442}\u{435}\u{43C}\u{430} \u{43E}\u{43F}\u{440}\u{435}\u{434}\u{435}\u{43B}\u{44F}\u{44E}\u{442}\u{441}\u{44F} \u{430}\u{432}\u{442}\u{43E}\u{43C}\u{430}\u{442}\u{438}\u{447}\u{435}\u{441}\u{43A}\u{438} \u{438}\u{437} Telegram. \u{423}\u{43F}\u{440}\u{430}\u{432}\u{43B}\u{44F}\u{439}\u{442}\u{435} \u{438}\u{437}\u{431}\u{440}\u{430}\u{43D}\u{43D}\u{44B}\u{43C} \u{438} \u{438}\u{441}\u{442}\u{43E}\u{440}\u{438}\u{435}\u{439} \u{43F}\u{440}\u{44F}\u{43C}\u{43E} \u{432} \u{43F}\u{440}\u{438}\u{43B}\u{43E}\u{436}\u{435}\u{43D}\u{438}\u{438}.", $this->openAppInline());
                return;
            case "\u{2753} \u{41F}\u{43E}\u{43C}\u{43E}\u{449}\u{44C}":
                $this->sendHelp($chatId);
                return;
        }

        // Fallback
        $this->api->sendMessage($chatId, "\u{41D}\u{430}\u{436}\u{43C}\u{438}\u{442}\u{435} \u{AB}\u{1F3AC} \u{41E}\u{442}\u{43A}\u{440}\u{44B}\u{442}\u{44C} \u{43A}\u{438}\u{43D}\u{43E}\u{BB}, \u{447}\u{442}\u{43E}\u{431}\u{44B} \u{43F}\u{435}\u{440}\u{435}\u{439}\u{442}\u{438} \u{432} \u{43A}\u{430}\u{442}\u{430}\u{43B}\u{43E}\u{433}.", $this->userKeyboard($tid));
    }

    private function sendWelcome(int $chatId, array $from): void
    {
        $name = htmlspecialchars($from['first_name'] ?? "\u{434}\u{440}\u{443}\u{433}", ENT_QUOTES);
        $app  = htmlspecialchars($this->cfg['app']['name']);
        $text = "\u{1F3AC} <b>{$app}</b>\n\n"
              . "\u{41F}\u{440}\u{438}\u{432}\u{435}\u{442}, {$name}! \u{414}\u{43E}\u{431}\u{440}\u{43E} \u{43F}\u{43E}\u{436}\u{430}\u{43B}\u{43E}\u{432}\u{430}\u{442}\u{44C} \u{432} \u{43A}\u{438}\u{43D}\u{43E}\u{442}\u{435}\u{43A}\u{443} \u{43D}\u{43E}\u{432}\u{43E}\u{433}\u{43E} \u{43F}\u{43E}\u{43A}\u{43E}\u{43B}\u{435}\u{43D}\u{438}\u{44F}.\n\n"
              . "\u{417}\u{434}\u{435}\u{441}\u{44C} \u{442}\u{435}\u{431}\u{44F} \u{436}\u{434}\u{443}\u{442}:\n"
              . "\u{1F525} \u{441}\u{432}\u{435}\u{436}\u{438}\u{435} \u{43D}\u{43E}\u{432}\u{438}\u{43D}\u{43A}\u{438} \u{438} \u{430}\u{43D}\u{43E}\u{43D}\u{441}\u{44B}\n"
              . "\u{1F3A5} \u{444}\u{438}\u{43B}\u{44C}\u{43C}\u{44B}, \u{441}\u{435}\u{440}\u{438}\u{430}\u{43B}\u{44B}, \u{430}\u{43D}\u{438}\u{43C}\u{435} \u{438} \u{43C}\u{443}\u{43B}\u{44C}\u{442}\u{444}\u{438}\u{43B}\u{44C}\u{43C}\u{44B}\n"
              . "\u{2B50} \u{43F}\u{43E}\u{434}\u{431}\u{43E}\u{440}\u{43A}\u{438} \u{438} \u{440}\u{435}\u{43A}\u{43E}\u{43C}\u{435}\u{43D}\u{434}\u{430}\u{446}\u{438}\u{438}\n"
              . "\u{2764}\u{FE0F} \u{438}\u{437}\u{431}\u{440}\u{430}\u{43D}\u{43D}\u{43E}\u{435} \u{438} \u{AB}\u{43F}\u{440}\u{43E}\u{434}\u{43E}\u{43B}\u{436}\u{438}\u{442}\u{44C} \u{43F}\u{440}\u{43E}\u{441}\u{43C}\u{43E}\u{442}\u{440}\u{BB}\n\n"
              . "\u{41D}\u{430}\u{436}\u{43C}\u{438} \u{43A}\u{43D}\u{43E}\u{43F}\u{43A}\u{443} \u{43D}\u{438}\u{436}\u{435}, \u{447}\u{442}\u{43E}\u{431}\u{44B} \u{43E}\u{442}\u{43A}\u{440}\u{44B}\u{442}\u{44C} \u{43A}\u{430}\u{442}\u{430}\u{43B}\u{43E}\u{433} \u{1F447}";

        $this->api->sendMessage($chatId, $text, $this->userKeyboard((int) ($from['id'] ?? 0)));
    }

    private function sendCategories(int $chatId): void
    {
        $url = $this->cfg['telegram']['miniapp_url'];
        $btn = static fn (string $label, string $frag) => ['text' => $label, 'web_app' => ['url' => $url . '#' . $frag]];
        $kb  = ['inline_keyboard' => [
            [$btn("\u{1F3A5} \u{424}\u{438}\u{43B}\u{44C}\u{43C}\u{44B}", 'movies'), $btn("\u{1F4FA} \u{421}\u{435}\u{440}\u{438}\u{430}\u{43B}\u{44B}", 'series')],
            [$btn("\u{1F38C} \u{410}\u{43D}\u{438}\u{43C}\u{435}", 'anime'), $btn("\u{1F476} \u{41C}\u{443}\u{43B}\u{44C}\u{442}\u{444}\u{438}\u{43B}\u{44C}\u{43C}\u{44B}", 'cartoons')],
            [$btn("\u{1F37F} \u{421}\u{435}\u{439}\u{447}\u{430}\u{441} \u{432} \u{43A}\u{438}\u{43D}\u{43E}", 'in_cinema'), $btn("\u{1F39E} \u{421}\u{43A}\u{43E}\u{440}\u{43E} \u{432}\u{44B}\u{439}\u{434}\u{435}\u{442}", 'coming_soon')],
        ]];
        $this->api->sendMessage($chatId, "\u{1F39E} <b>\u{41A}\u{430}\u{442}\u{435}\u{433}\u{43E}\u{440}\u{438}\u{438}</b>\\n\u{412}\u{44B}\u{431}\u{435}\u{440}\u{438}\u{442}\u{435} \u{440}\u{430}\u{437}\u{434}\u{435}\u{43B}:", ['reply_markup' => json_encode($kb)]);
    }

    private function sendHelp(int $chatId): void
    {
        $text = "\u{2753} <b>\u{41F}\u{43E}\u{43C}\u{43E}\u{449}\u{44C}</b>\n\n"
              . "\u{2022} \u{AB}\u{1F3AC} \u{41E}\u{442}\u{43A}\u{440}\u{44B}\u{442}\u{44C} \u{43A}\u{438}\u{43D}\u{43E}\u{BB} \u{2014} \u{43A}\u{430}\u{442}\u{430}\u{43B}\u{43E}\u{433} \u{444}\u{438}\u{43B}\u{44C}\u{43C}\u{43E}\u{432} \u{438} \u{430}\u{43D}\u{43E}\u{43D}\u{441}\u{43E}\u{432}.\n"
              . "\u{2022} \u{AB}\u{1F525} \u{41D}\u{43E}\u{432}\u{438}\u{43D}\u{43A}\u{438}\u{BB} \u{2014} \u{441}\u{430}\u{43C}\u{44B}\u{435} \u{441}\u{432}\u{435}\u{436}\u{438}\u{435} \u{43F}\u{43E}\u{441}\u{442}\u{443}\u{43F}\u{43B}\u{435}\u{43D}\u{438}\u{44F}.\n"
              . "\u{2022} \u{AB}\u{1F39E} \u{41A}\u{430}\u{442}\u{435}\u{433}\u{43E}\u{440}\u{438}\u{438}\u{BB} \u{2014} \u{444}\u{438}\u{43B}\u{44C}\u{43C}\u{44B}, \u{441}\u{435}\u{440}\u{438}\u{430}\u{43B}\u{44B}, \u{430}\u{43D}\u{438}\u{43C}\u{435}, \u{43C}\u{443}\u{43B}\u{44C}\u{442}\u{444}\u{438}\u{43B}\u{44C}\u{43C}\u{44B}.\n"
              . "\u{2022} \u{AB}\u{2764}\u{FE0F} \u{418}\u{437}\u{431}\u{440}\u{430}\u{43D}\u{43D}\u{43E}\u{435}\u{BB} \u{438} \u{AB}\u{1F552} \u{418}\u{441}\u{442}\u{43E}\u{440}\u{438}\u{44F}\u{BB} \u{2014} \u{441}\u{43E}\u{445}\u{440}\u{430}\u{43D}\u{451}\u{43D}\u{43D}\u{43E}\u{435} \u{438} \u{43F}\u{440}\u{43E}\u{441}\u{43C}\u{43E}\u{442}\u{440}\u{435}\u{43D}\u{43D}\u{43E}\u{435}.\n\n"
              . "\u{41F}\u{440}\u{438}\u{44F}\u{442}\u{43D}\u{43E}\u{433}\u{43E} \u{43F}\u{440}\u{43E}\u{441}\u{43C}\u{43E}\u{442}\u{440}\u{430}!";
        $this->api->sendMessage($chatId, $text, $this->openAppInline());
    }

    private function openSection(int $chatId, string $frag, string $title): void
    {
        $url = $this->cfg['telegram']['miniapp_url'] . '#' . $frag;
        $kb  = ['inline_keyboard' => [[['text' => "\u{41E}\u{442}\u{43A}\u{440}\u{44B}\u{442}\u{44C}: {$title}", 'web_app' => ['url' => $url]]]]];
        $this->api->sendMessage($chatId, "\u{41E}\u{442}\u{43A}\u{440}\u{44B}\u{432}\u{430}\u{44E} \u{440}\u{430}\u{437}\u{434}\u{435}\u{43B} <b>{$title}</b> \u{1F447}", ['reply_markup' => json_encode($kb)]);
    }

    // ---- Admin ----------------------------------------------------------

    private function sendAdminPanel(int $chatId, int $tid): void
    {
        if (!$this->isAdmin($tid)) {
            $this->api->sendMessage($chatId, "\u{26D4} \u{414}\u{43E}\u{441}\u{442}\u{443}\u{43F} \u{442}\u{43E}\u{43B}\u{44C}\u{43A}\u{43E} \u{434}\u{43B}\u{44F} \u{430}\u{434}\u{43C}\u{438}\u{43D}\u{438}\u{441}\u{442}\u{440}\u{430}\u{442}\u{43E}\u{440}\u{43E}\u{432}.");
            return;
        }
        $this->api->sendMessage($chatId, "\u{1F6E0} <b>\u{41F}\u{430}\u{43D}\u{435}\u{43B}\u{44C} \u{430}\u{434}\u{43C}\u{438}\u{43D}\u{438}\u{441}\u{442}\u{440}\u{430}\u{442}\u{43E}\u{440}\u{430}</b>\n\u{412}\u{44B}\u{431}\u{435}\u{440}\u{438}\u{442}\u{435} \u{434}\u{435}\u{439}\u{441}\u{442}\u{432}\u{438}\u{435}:", [
            'reply_markup' => json_encode($this->adminMenu()),
        ]);
    }

    private function adminMenu(): array
    {
        return ['inline_keyboard' => [
            [['text' => "\u{1F916} AI: \u{434}\u{43E}\u{431}\u{430}\u{432}\u{438}\u{442}\u{44C} \u{444}\u{438}\u{43B}\u{44C}\u{43C} \u{43F}\u{43E} \u{43F}\u{43E}\u{441}\u{442}\u{435}\u{440}\u{443}", 'callback_data' => 'ai:add']],
            [['text' => "\u{2795} \u{424}\u{438}\u{43B}\u{44C}\u{43C}", 'callback_data' => 'add:movie'], ['text' => "\u{2795} \u{421}\u{435}\u{440}\u{438}\u{430}\u{43B}", 'callback_data' => 'add:series']],
            [['text' => "\u{2795} \u{41C}\u{443}\u{43B}\u{44C}\u{442}\u{444}\u{438}\u{43B}\u{44C}\u{43C}", 'callback_data' => 'add:cartoon'], ['text' => "\u{2795} \u{410}\u{43D}\u{438}\u{43C}\u{435}", 'callback_data' => 'add:anime']],
            [['text' => "\u{1F4E3} \u{414}\u{43E}\u{431}\u{430}\u{432}\u{438}\u{442}\u{44C} \u{430}\u{43D}\u{43E}\u{43D}\u{441}", 'callback_data' => 'add:announcement']],
            [['text' => "\u{1F4FA} \u{421}\u{435}\u{440}\u{438}\u{438} \u{441}\u{435}\u{440}\u{438}\u{430}\u{43B}\u{430} (\u{441}\u{435}\u{437}\u{43E}\u{43D}\u{44B}/\u{441}\u{435}\u{440}\u{438}\u{438})", 'callback_data' => 'adm:series']],
            [['text' => "\u{1F4E1} \u{41A}\u{430}\u{43D}\u{430}\u{43B}-\u{430}\u{440}\u{445}\u{438}\u{432}", 'callback_data' => 'adm:channel']],
            [['text' => "\u{1F5D1} \u{423}\u{434}\u{430}\u{43B}\u{438}\u{442}\u{44C}", 'callback_data' => 'adm:list'], ['text' => "\u{1F4CA} \u{421}\u{442}\u{430}\u{442}\u{438}\u{441}\u{442}\u{438}\u{43A}\u{430}", 'callback_data' => 'adm:stats']],
            [['text' => "\u{1F4E2} \u{420}\u{430}\u{441}\u{441}\u{44B}\u{43B}\u{43A}\u{430}", 'callback_data' => 'adm:broadcast'], ['text' => "\u{2699} \u{41D}\u{430}\u{441}\u{442}\u{440}\u{43E}\u{439}\u{43A}\u{438}", 'callback_data' => 'adm:settings']],
        ]];
    }

    private function onCallback(array $cb): void
    {
        $data   = (string) ($cb['data'] ?? '');
        $chatId = (int) ($cb['message']['chat']['id'] ?? 0);
        $msgId  = (int) ($cb['message']['message_id'] ?? 0);
        $tid    = (int) ($cb['from']['id'] ?? 0);
        $cbId   = (string) ($cb['id'] ?? '');

        if (!$this->isAdmin($tid)) {
            $this->api->answerCallbackQuery($cbId, "\u{26D4} \u{422}\u{43E}\u{43B}\u{44C}\u{43A}\u{43E} \u{434}\u{43B}\u{44F} \u{430}\u{434}\u{43C}\u{438}\u{43D}\u{43E}\u{432}", true);
            return;
        }

        // AI wizard callbacks (each answers its own callback query)
        if ($this->aiFlow->handleCallback($chatId, $tid, $msgId, $data, $cbId)) {
            return;
        }
        // Episode wizard callbacks
        if ($this->episodeFlow->handleCallback($chatId, $tid, $data, $cbId)) {
            return;
        }

        $this->api->answerCallbackQuery($cbId);

        // Add wizards
        if (str_starts_with($data, 'add:')) {
            $type = substr($data, 4);
            if ($type === 'announcement') {
                $this->flow->start($chatId, $tid, 'announcement');
            } else {
                $this->flow->start($chatId, $tid, 'movie', $type);
            }
            return;
        }

        switch ($data) {
            case 'adm:stats':
                $s = $this->repo->stats();
                $text = "\u{1F4CA} <b>\u{421}\u{442}\u{430}\u{442}\u{438}\u{441}\u{442}\u{438}\u{43A}\u{430}</b>\n\n"
                      . "\u{1F465} \u{41F}\u{43E}\u{43B}\u{44C}\u{437}\u{43E}\u{432}\u{430}\u{442}\u{435}\u{43B}\u{435}\u{439}: <b>{$s['users']}</b>\n"
                      . "\u{1F3A5} \u{424}\u{438}\u{43B}\u{44C}\u{43C}\u{43E}\u{432}: <b>{$s['movies']}</b>\n"
                      . "\u{1F4FA} \u{421}\u{435}\u{440}\u{438}\u{430}\u{43B}\u{43E}\u{432}: <b>{$s['series']}</b>\n"
                      . "\u{1F38C} \u{410}\u{43D}\u{438}\u{43C}\u{435}: <b>{$s['anime']}</b>\n"
                      . "\u{1F476} \u{41C}\u{443}\u{43B}\u{44C}\u{442}\u{444}\u{438}\u{43B}\u{44C}\u{43C}\u{43E}\u{432}: <b>{$s['cartoons']}</b>\n"
                      . "\u{1F4E3} \u{410}\u{43D}\u{43E}\u{43D}\u{441}\u{43E}\u{432}: <b>{$s['announcements']}</b>\n"
                      . "\u{2764}\u{FE0F} \u{412} \u{438}\u{437}\u{431}\u{440}\u{430}\u{43D}\u{43D}\u{43E}\u{43C}: <b>{$s['favorites']}</b>\n"
                      . "\u{1F441} \u{41F}\u{440}\u{43E}\u{441}\u{43C}\u{43E}\u{442}\u{440}\u{43E}\u{432}: <b>{$s['views']}</b>";
                $this->api->editMessageText($chatId, $msgId, $text, ['reply_markup' => json_encode($this->backMenu())]);
                return;

            case 'adm:broadcast':
                $this->flow->startBroadcast($chatId, $tid);
                return;

            case 'adm:settings':
                $adminList = implode(', ', $this->cfg['telegram']['admin_ids']);
                $text = "\u{2699} <b>\u{41D}\u{430}\u{441}\u{442}\u{440}\u{43E}\u{439}\u{43A}\u{438} \u{431}\u{43E}\u{442}\u{430}</b>\n\n"
                      . "\u{41F}\u{440}\u{438}\u{43B}\u{43E}\u{436}\u{435}\u{43D}\u{438}\u{435}: <b>" . htmlspecialchars($this->cfg['app']['name']) . "</b>\n"
                      . "Mini App: <code>" . htmlspecialchars($this->cfg['telegram']['miniapp_url']) . "</code>\n"
                      . "\u{410}\u{434}\u{43C}\u{438}\u{43D}\u{438}\u{441}\u{442}\u{440}\u{430}\u{442}\u{43E}\u{440}\u{44B}: <code>{$adminList}</code>";
                $this->api->editMessageText($chatId, $msgId, $text, ['reply_markup' => json_encode($this->backMenu())]);
                return;

            case 'adm:list':
                $this->sendDeleteList($chatId, $msgId);
                return;

            case 'adm:series':
                $this->sendSeriesList($chatId, $msgId);
                return;

            case 'adm:channel':
                $this->sendChannelSetup($chatId, $msgId, $tid);
                return;

            case 'adm:home':
                $this->api->editMessageText($chatId, $msgId, "\u{1F6E0} <b>\u{41F}\u{430}\u{43D}\u{435}\u{43B}\u{44C} \u{430}\u{434}\u{43C}\u{438}\u{43D}\u{438}\u{441}\u{442}\u{440}\u{430}\u{442}\u{43E}\u{440}\u{430}</b>\n\u{412}\u{44B}\u{431}\u{435}\u{440}\u{438}\u{442}\u{435} \u{434}\u{435}\u{439}\u{441}\u{442}\u{432}\u{438}\u{435}:", [
                    'reply_markup' => json_encode($this->adminMenu()),
                ]);
                return;
        }

        if (str_starts_with($data, 'del:')) {
            $id = (int) substr($data, 4);
            if ($this->repo->deleteMovie($id)) {
                $this->api->answerCallbackQuery($cbId, "\u{423}\u{434}\u{430}\u{43B}\u{435}\u{43D}\u{43E} \u{2705}");
                $this->sendDeleteList($chatId, $msgId);
            }
            return;
        }
    }

    private function sendDeleteList(int $chatId, int $msgId): void
    {
        $movies = $this->repo->recentMovies(12);
        if (!$movies) {
            $this->api->editMessageText($chatId, $msgId, "\u{41A}\u{430}\u{442}\u{430}\u{43B}\u{43E}\u{433} \u{43F}\u{443}\u{441}\u{442} \u{2014} \u{434}\u{43E}\u{431}\u{430}\u{432}\u{44C}\u{442}\u{435} \u{43A}\u{43E}\u{43D}\u{442}\u{435}\u{43D}\u{442}.", ['reply_markup' => json_encode($this->backMenu())]);
            return;
        }
        $rows = [];
        foreach ($movies as $m) {
            $rows[] = [['text' => "\u{1F5D1} " . mb_strimwidth($m['title'], 0, 40, "\u{2026}"), 'callback_data' => 'del:' . $m['id']]];
        }
        $rows[] = [['text' => "\u{2B05}\u{FE0F} \u{41D}\u{430}\u{437}\u{430}\u{434}", 'callback_data' => 'adm:home']];
        $this->api->editMessageText($chatId, $msgId, "\u{1F5D1} <b>\u{423}\u{434}\u{430}\u{43B}\u{435}\u{43D}\u{438}\u{435} \u{43A}\u{43E}\u{43D}\u{442}\u{435}\u{43D}\u{442}\u{430}</b>\n\u{41D}\u{430}\u{436}\u{43C}\u{438}\u{442}\u{435} \u{43D}\u{430} \u{44D}\u{43B}\u{435}\u{43C}\u{435}\u{43D}\u{442}, \u{447}\u{442}\u{43E}\u{431}\u{44B} \u{443}\u{434}\u{430}\u{43B}\u{438}\u{442}\u{44C}:", [
            'reply_markup' => json_encode(['inline_keyboard' => $rows]),
        ]);
    }

    private function sendSeriesList(int $chatId, int $msgId): void
    {
        $series = $this->repo->recentSeries(15);
        if (!$series) {
            $this->api->editMessageText(
                $chatId,
                $msgId,
                "\u{421}\u{43D}\u{430}\u{447}\u{430}\u{43B}\u{430} \u{434}\u{43E}\u{431}\u{430}\u{432}\u{44C}\u{442}\u{435} \u{441}\u{435}\u{440}\u{438}\u{430}\u{43B} \u{438}\u{43B}\u{438} \u{430}\u{43D}\u{438}\u{43C}\u{435} (\u{1F916} AI \u{438}\u{43B}\u{438} \u{2795} \u{421}\u{435}\u{440}\u{438}\u{430}\u{43B}), \u{437}\u{430}\u{442}\u{435}\u{43C} \u{441}\u{44E}\u{434}\u{430} \u{2014} \u{434}\u{43E}\u{431}\u{430}\u{432}\u{43B}\u{44F}\u{442}\u{44C} \u{441}\u{435}\u{440}\u{438}\u{438}.",
                ['reply_markup' => json_encode($this->backMenu())]
            );
            return;
        }
        $rows = [];
        foreach ($series as $s) {
            $rows[] = [[
                'text' => "\u{1F4FA} " . mb_strimwidth($s['title'], 0, 40, "\u{2026}"),
                'callback_data' => 'ep:add:' . $s['id'],
            ]];
        }
        $rows[] = [['text' => "\u{2B05}\u{FE0F} \u{41D}\u{430}\u{437}\u{430}\u{434}", 'callback_data' => 'adm:home']];
        $this->api->editMessageText(
            $chatId,
            $msgId,
            "\u{1F4FA} <b>\u{421}\u{435}\u{440}\u{438}\u{438} \u{441}\u{435}\u{440}\u{438}\u{430}\u{43B}\u{430}</b>\n\u{412}\u{44B}\u{431}\u{435}\u{440}\u{438}\u{442}\u{435} \u{441}\u{435}\u{440}\u{438}\u{430}\u{43B}/\u{430}\u{43D}\u{438}\u{43C}\u{435}, \u{447}\u{442}\u{43E}\u{431}\u{44B} \u{434}\u{43E}\u{431}\u{430}\u{432}\u{438}\u{442}\u{44C} \u{441}\u{435}\u{437}\u{43E}\u{43D}\u{44B} \u{438} \u{441}\u{435}\u{440}\u{438}\u{438}:",
            ['reply_markup' => json_encode(['inline_keyboard' => $rows])]
        );
    }

    // ---- Deep links (from archive-channel buttons) ----------------------

    /**
     * Handles /start payloads: `movie_<id>` delivers the film, and
     * `ep_<movieId>_<season>_<episode>` delivers one series episode.
     * @return bool true when the payload was recognised and handled.
     */
    private function handleDeepLink(int $chatId, string $param): bool
    {
        if (preg_match('/^movie_(\d+)$/', $param, $m)) {
            $play = $this->repo->playable((int) $m[1]);
            if (!$play) {
                return false;
            }
            $title = htmlspecialchars((string) $play['title'], ENT_QUOTES);

            if (!empty($play['telegram_file_id'])) {
                $res = $this->api->sendVideo($chatId, (string) $play['telegram_file_id'], "\u{1F3AC} <b>{$title}</b>", $this->openAppInline());
                if (!empty($res['ok'])) {
                    (new \Models\Movie())->incrementViews((int) $m[1], null);
                    return true;
                }
            }
            if (!empty($play['watch_url'])) {
                $this->api->sendMessage($chatId, "\u{1F3AC} <b>{$title}</b>", ['reply_markup' => json_encode([
                    'inline_keyboard' => [[['text' => "\u{25B6}\u{FE0F} \u{421}\u{43C}\u{43E}\u{442}\u{440}\u{435}\u{442}\u{44C}", 'url' => (string) $play['watch_url']]]],
                ])]);
                return true;
            }
            $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{418}\u{441}\u{442}\u{43E}\u{447}\u{43D}\u{438}\u{43A} \u{444}\u{438}\u{43B}\u{44C}\u{43C}\u{430} \u{43F}\u{43E}\u{43A}\u{430} \u{43D}\u{435} \u{434}\u{43E}\u{431}\u{430}\u{432}\u{43B}\u{435}\u{43D}.", $this->openAppInline());
            return true;
        }

        if (preg_match('/^ep_(\d+)_(\d+)_(\d+)$/', $param, $m)) {
            $ep = $this->repo->episodePlayable((int) $m[1], (int) $m[2], (int) $m[3]);
            if (!$ep) {
                return false;
            }
            $title = htmlspecialchars((string) $ep['title'], ENT_QUOTES);
            $caption = "\u{1F4FA} <b>{$title}</b> \u{2014} \u{421}\u{435}\u{437}\u{43E}\u{43D} {$ep['season']}, \u{441}\u{435}\u{440}\u{438}\u{44F} {$ep['episode']}";

            if (!empty($ep['telegram_file_id'])) {
                $res = $this->api->sendVideo($chatId, (string) $ep['telegram_file_id'], $caption, $this->openAppInline());
                if (!empty($res['ok'])) {
                    return true;
                }
            }
            if (!empty($ep['watch_url'])) {
                $this->api->sendMessage($chatId, $caption, ['reply_markup' => json_encode([
                    'inline_keyboard' => [[['text' => "\u{25B6}\u{FE0F} \u{421}\u{43C}\u{43E}\u{442}\u{440}\u{435}\u{442}\u{44C}", 'url' => (string) $ep['watch_url']]]],
                ])]);
                return true;
            }
            return false;
        }

        return false;
    }

    // ---- Archive channel -------------------------------------------------

    /** Show archive-channel status and start the connect dialog. */
    private function sendChannelSetup(int $chatId, int $msgId, int $tid): void
    {
        $cid   = $this->repo->getSetting('archive_channel_id');
        $title = $this->repo->getSetting('archive_channel_title');
        $cur = $cid
            ? "\u{41F}\u{43E}\u{434}\u{43A}\u{43B}\u{44E}\u{447}\u{451}\u{43D}: <b>" . htmlspecialchars((string) $title, ENT_QUOTES) . '</b> (<code>' . htmlspecialchars((string) $cid, ENT_QUOTES) . '</code>)'
            : "\u{41D}\u{435} \u{43F}\u{43E}\u{434}\u{43A}\u{43B}\u{44E}\u{447}\u{451}\u{43D}";

        $this->store->set($tid, 'set_channel', []);
        $text = "\u{1F4E1} <b>\u{41A}\u{430}\u{43D}\u{430}\u{43B}-\u{430}\u{440}\u{445}\u{438}\u{432}</b>\n\n"
            . "\u{41A}\u{430}\u{436}\u{434}\u{44B}\u{439} \u{43E}\u{43F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{43E}\u{432}\u{430}\u{43D}\u{43D}\u{44B}\u{439} \u{444}\u{438}\u{43B}\u{44C}\u{43C} \u{431}\u{43E}\u{442} \u{431}\u{443}\u{434}\u{435}\u{442} \u{430}\u{432}\u{442}\u{43E}\u{43C}\u{430}\u{442}\u{438}\u{447}\u{435}\u{441}\u{43A}\u{438} \u{43E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{43B}\u{44F}\u{442}\u{44C} \u{432} \u{44D}\u{442}\u{43E}\u{442} \u{437}\u{430}\u{43A}\u{440}\u{44B}\u{442}\u{44B}\u{439} \u{43A}\u{430}\u{43D}\u{430}\u{43B} (\u{43A}\u{430}\u{440}\u{442}\u{43E}\u{447}\u{43A}\u{430} + \u{432}\u{438}\u{434}\u{435}\u{43E}).\n\n"
            . "\u{421}\u{435}\u{439}\u{447}\u{430}\u{441}: {$cur}\n\n"
            . "<b>\u{41A}\u{430}\u{43A} \u{43F}\u{43E}\u{434}\u{43A}\u{43B}\u{44E}\u{447}\u{438}\u{442}\u{44C}:</b>\n"
            . "1) \u{421}\u{43E}\u{437}\u{434}\u{430}\u{439}\u{442}\u{435} \u{437}\u{430}\u{43A}\u{440}\u{44B}\u{442}\u{44B}\u{439} \u{43A}\u{430}\u{43D}\u{430}\u{43B}\n"
            . "2) \u{414}\u{43E}\u{431}\u{430}\u{432}\u{44C}\u{442}\u{435} \u{44D}\u{442}\u{43E}\u{433}\u{43E} \u{431}\u{43E}\u{442}\u{430} \u{432} \u{43A}\u{430}\u{43D}\u{430}\u{43B} \u{43A}\u{430}\u{43A} <b>\u{430}\u{434}\u{43C}\u{438}\u{43D}\u{438}\u{441}\u{442}\u{440}\u{430}\u{442}\u{43E}\u{440}\u{430}</b>\n"
            . "3) \u{41F}\u{435}\u{440}\u{435}\u{448}\u{43B}\u{438}\u{442}\u{435} \u{441}\u{44E}\u{434}\u{430} \u{43B}\u{44E}\u{431}\u{43E}\u{435} \u{441}\u{43E}\u{43E}\u{431}\u{449}\u{435}\u{43D}\u{438}\u{435} \u{438}\u{437} \u{43A}\u{430}\u{43D}\u{430}\u{43B}\u{430}\n\n"
            . "\u{414}\u{43B}\u{44F} \u{43E}\u{442}\u{43C}\u{435}\u{43D}\u{44B} \u{2014} /cancel";
        $this->api->editMessageText($chatId, $msgId, $text, ['reply_markup' => json_encode($this->backMenu())]);
    }

    /** Receive a forwarded channel message and save the channel as archive. */
    private function onSetChannel(int $chatId, int $tid, array $msg): void
    {
        // New Bot API: forward_origin {type:'channel', chat:{...}}; legacy: forward_from_chat.
        $origin = $msg['forward_origin'] ?? null;
        $chat = null;
        if (is_array($origin) && ($origin['type'] ?? '') === 'channel' && !empty($origin['chat'])) {
            $chat = $origin['chat'];
        } elseif (!empty($msg['forward_from_chat']) && ($msg['forward_from_chat']['type'] ?? '') === 'channel') {
            $chat = $msg['forward_from_chat'];
        }

        if (!$chat || empty($chat['id'])) {
            $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{41D}\u{443}\u{436}\u{43D}\u{43E} \u{438}\u{43C}\u{435}\u{43D}\u{43D}\u{43E} <b>\u{43F}\u{435}\u{440}\u{435}\u{441}\u{43B}\u{430}\u{442}\u{44C}</b> \u{441}\u{43E}\u{43E}\u{431}\u{449}\u{435}\u{43D}\u{438}\u{435} \u{438}\u{437} \u{43A}\u{430}\u{43D}\u{430}\u{43B}\u{430}. \u{41F}\u{43E}\u{43F}\u{440}\u{43E}\u{431}\u{443}\u{439}\u{442}\u{435} \u{435}\u{449}\u{451} \u{440}\u{430}\u{437} (\u{438}\u{43B}\u{438} /cancel).");
            return;
        }

        $cid   = (string) $chat['id'];
        $title = (string) ($chat['title'] ?? "\u{43A}\u{430}\u{43D}\u{430}\u{43B}");

        // Verify the bot can post there (it must be a channel admin).
        $test = $this->api->sendMessage($cid, "\u{2705} \u{41A}\u{430}\u{43D}\u{430}\u{43B}-\u{430}\u{440}\u{445}\u{438}\u{432} \u{43F}\u{43E}\u{434}\u{43A}\u{43B}\u{44E}\u{447}\u{451}\u{43D} \u{43A} \u{431}\u{43E}\u{442}\u{443}.");
        if (empty($test['ok'])) {
            $this->api->sendMessage(
                $chatId,
                "\u{26A0}\u{FE0F} \u{41D}\u{435} \u{443}\u{434}\u{430}\u{43B}\u{43E}\u{441}\u{44C} \u{43D}\u{430}\u{43F}\u{438}\u{441}\u{430}\u{442}\u{44C} \u{432} \u{43A}\u{430}\u{43D}\u{430}\u{43B} \u{AB}" . htmlspecialchars($title, ENT_QUOTES) . "\u{BB}.\n"
                . "\u{423}\u{431}\u{435}\u{434}\u{438}\u{442}\u{435}\u{441}\u{44C}, \u{447}\u{442}\u{43E} \u{431}\u{43E}\u{442} \u{434}\u{43E}\u{431}\u{430}\u{432}\u{43B}\u{435}\u{43D} \u{432} \u{43A}\u{430}\u{43D}\u{430}\u{43B} \u{43A}\u{430}\u{43A} <b>\u{430}\u{434}\u{43C}\u{438}\u{43D}\u{438}\u{441}\u{442}\u{440}\u{430}\u{442}\u{43E}\u{440}</b> (\u{43F}\u{440}\u{430}\u{432}\u{43E} \u{43F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{43E}\u{432}\u{430}\u{442}\u{44C}), \u{438} \u{43F}\u{435}\u{440}\u{435}\u{448}\u{43B}\u{438}\u{442}\u{435} \u{441}\u{43E}\u{43E}\u{431}\u{449}\u{435}\u{43D}\u{438}\u{435} \u{435}\u{449}\u{451} \u{440}\u{430}\u{437}."
            );
            return;
        }

        $this->repo->setSetting('archive_channel_id', $cid);
        $this->repo->setSetting('archive_channel_title', $title);
        $this->store->clear($tid);
        $this->api->sendMessage(
            $chatId,
            "\u{2705} \u{41A}\u{430}\u{43D}\u{430}\u{43B}-\u{430}\u{440}\u{445}\u{438}\u{432} \u{43F}\u{43E}\u{434}\u{43A}\u{43B}\u{44E}\u{447}\u{451}\u{43D}: <b>" . htmlspecialchars($title, ENT_QUOTES) . "</b>\n"
            . "\u{422}\u{435}\u{43F}\u{435}\u{440}\u{44C} \u{43A}\u{430}\u{436}\u{434}\u{44B}\u{439} \u{43E}\u{43F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{43E}\u{432}\u{430}\u{43D}\u{43D}\u{44B}\u{439} \u{444}\u{438}\u{43B}\u{44C}\u{43C} \u{431}\u{443}\u{434}\u{435}\u{442} \u{430}\u{432}\u{442}\u{43E}\u{43C}\u{430}\u{442}\u{438}\u{447}\u{435}\u{441}\u{43A}\u{438} \u{43E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{43B}\u{44F}\u{442}\u{44C}\u{441}\u{44F} \u{432} \u{43A}\u{430}\u{43D}\u{430}\u{43B}."
        );
    }

    private function backMenu(): array
    {
        return ['inline_keyboard' => [[['text' => "\u{2B05}\u{FE0F} \u{41D}\u{430}\u{437}\u{430}\u{434}", 'callback_data' => 'adm:home']]]];
    }

    // ---- Keyboards ------------------------------------------------------

    private function userKeyboard(int $tid): array
    {
        $url  = $this->cfg['telegram']['miniapp_url'];
        $rows = [
            [['text' => "\u{1F3AC} \u{41E}\u{442}\u{43A}\u{440}\u{44B}\u{442}\u{44C} \u{43A}\u{438}\u{43D}\u{43E}", 'web_app' => ['url' => $url]]],
            [['text' => "\u{1F525} \u{41D}\u{43E}\u{432}\u{438}\u{43D}\u{43A}\u{438}"], ['text' => "\u{1F39E} \u{41A}\u{430}\u{442}\u{435}\u{433}\u{43E}\u{440}\u{438}\u{438}"]],
            [['text' => "\u{2764}\u{FE0F} \u{418}\u{437}\u{431}\u{440}\u{430}\u{43D}\u{43D}\u{43E}\u{435}"], ['text' => "\u{1F552} \u{418}\u{441}\u{442}\u{43E}\u{440}\u{438}\u{44F}"]],
            [['text' => "\u{2699} \u{41D}\u{430}\u{441}\u{442}\u{440}\u{43E}\u{439}\u{43A}\u{438}"], ['text' => "\u{2753} \u{41F}\u{43E}\u{43C}\u{43E}\u{449}\u{44C}"]],
        ];
        if ($this->isAdmin($tid)) {
            $rows[] = [['text' => "\u{2699} \u{41F}\u{430}\u{43D}\u{435}\u{43B}\u{44C}"]];
        }
        return ['reply_markup' => json_encode(['keyboard' => $rows, 'resize_keyboard' => true])];
    }

    private function openAppInline(): array
    {
        return ['reply_markup' => json_encode([
            'inline_keyboard' => [[['text' => "\u{1F3AC} \u{41E}\u{442}\u{43A}\u{440}\u{44B}\u{442}\u{44C} \u{43A}\u{438}\u{43D}\u{43E}", 'web_app' => ['url' => $this->cfg['telegram']['miniapp_url']]]]],
        ])];
    }

    private function isAdmin(int $tid): bool
    {
        return in_array($tid, $this->cfg['telegram']['admin_ids'], true);
    }
}
