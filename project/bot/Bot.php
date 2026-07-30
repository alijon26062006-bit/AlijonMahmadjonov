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
            || $text === '/admin' || $text === '⚙ Панель'
            || $text === '/cancel';
        if ($isCommand) {
            $this->store->clear($tid);
        }

        // Active admin dialog takes priority (unless a global command was sent)
        if (!$isCommand && $this->isAdmin($tid)) {
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
            $this->api->sendMessage($chatId, '❌ Отменено. Напишите /admin для меню.', [
                'reply_markup' => json_encode(['remove_keyboard' => true]),
            ]);
            return;
        }

        if ($text === '/start' || str_starts_with($text, '/start ')) {
            $this->sendWelcome($chatId, $from);
            return;
        }

        if ($text === '/admin' || $text === '⚙ Панель') {
            $this->sendAdminPanel($chatId, $tid);
            return;
        }

        // User navigation (reply keyboard labels)
        switch ($text) {
            case '🎬 Открыть кино':
                // Handled natively by the web_app keyboard button; nothing to do.
                return;
            case '🔥 Новинки':
                $this->openSection($chatId, 'new', '🔥 Новинки');
                return;
            case '🎞 Категории':
                $this->sendCategories($chatId);
                return;
            case '❤️ Избранное':
                $this->openSection($chatId, 'favorites', '❤️ Избранное');
                return;
            case '🕒 История':
                $this->openSection($chatId, 'history', '🕒 История');
                return;
            case '⚙ Настройки':
                $this->api->sendMessage($chatId, "⚙ <b>Настройки</b>\n\nЯзык интерфейса и тема определяются автоматически из Telegram. Управляйте избранным и историей прямо в приложении.", $this->openAppInline());
                return;
            case '❓ Помощь':
                $this->sendHelp($chatId);
                return;
        }

        // Fallback
        $this->api->sendMessage($chatId, 'Нажмите «🎬 Открыть кино», чтобы перейти в каталог.', $this->userKeyboard($tid));
    }

    private function sendWelcome(int $chatId, array $from): void
    {
        $name = htmlspecialchars($from['first_name'] ?? 'друг', ENT_QUOTES);
        $app  = htmlspecialchars($this->cfg['app']['name']);
        $text = "🎬 <b>{$app}</b>\n\n"
              . "Привет, {$name}! Добро пожаловать в кинотеку нового поколения.\n\n"
              . "Здесь тебя ждут:\n"
              . "🔥 свежие новинки и анонсы\n"
              . "🎥 фильмы, сериалы, аниме и мультфильмы\n"
              . "⭐ подборки и рекомендации\n"
              . "❤️ избранное и «продолжить просмотр»\n\n"
              . "Нажми кнопку ниже, чтобы открыть каталог 👇";

        $this->api->sendMessage($chatId, $text, $this->userKeyboard((int) ($from['id'] ?? 0)));
    }

    private function sendCategories(int $chatId): void
    {
        $url = $this->cfg['telegram']['miniapp_url'];
        $btn = static fn (string $label, string $frag) => ['text' => $label, 'web_app' => ['url' => $url . '#' . $frag]];
        $kb  = ['inline_keyboard' => [
            [$btn('🎥 Фильмы', 'movies'), $btn('📺 Сериалы', 'series')],
            [$btn('🎌 Аниме', 'anime'), $btn('👶 Мультфильмы', 'cartoons')],
            [$btn('🍿 Сейчас в кино', 'in_cinema'), $btn('🎞 Скоро выйдет', 'coming_soon')],
        ]];
        $this->api->sendMessage($chatId, '🎞 <b>Категории</b>\nВыберите раздел:', ['reply_markup' => json_encode($kb)]);
    }

    private function sendHelp(int $chatId): void
    {
        $text = "❓ <b>Помощь</b>\n\n"
              . "• «🎬 Открыть кино» — каталог фильмов и анонсов.\n"
              . "• «🔥 Новинки» — самые свежие поступления.\n"
              . "• «🎞 Категории» — фильмы, сериалы, аниме, мультфильмы.\n"
              . "• «❤️ Избранное» и «🕒 История» — сохранённое и просмотренное.\n\n"
              . "Приятного просмотра!";
        $this->api->sendMessage($chatId, $text, $this->openAppInline());
    }

    private function openSection(int $chatId, string $frag, string $title): void
    {
        $url = $this->cfg['telegram']['miniapp_url'] . '#' . $frag;
        $kb  = ['inline_keyboard' => [[['text' => "Открыть: {$title}", 'web_app' => ['url' => $url]]]]];
        $this->api->sendMessage($chatId, "Открываю раздел <b>{$title}</b> 👇", ['reply_markup' => json_encode($kb)]);
    }

    // ---- Admin ----------------------------------------------------------

    private function sendAdminPanel(int $chatId, int $tid): void
    {
        if (!$this->isAdmin($tid)) {
            $this->api->sendMessage($chatId, '⛔ Доступ только для администраторов.');
            return;
        }
        $this->api->sendMessage($chatId, "🛠 <b>Панель администратора</b>\nВыберите действие:", [
            'reply_markup' => json_encode($this->adminMenu()),
        ]);
    }

    private function adminMenu(): array
    {
        return ['inline_keyboard' => [
            [['text' => '🤖 AI: добавить фильм по постеру', 'callback_data' => 'ai:add']],
            [['text' => '➕ Фильм', 'callback_data' => 'add:movie'], ['text' => '➕ Сериал', 'callback_data' => 'add:series']],
            [['text' => '➕ Мультфильм', 'callback_data' => 'add:cartoon'], ['text' => '➕ Аниме', 'callback_data' => 'add:anime']],
            [['text' => '📣 Добавить анонс', 'callback_data' => 'add:announcement']],
            [['text' => '📺 Серии сериала (сезоны/серии)', 'callback_data' => 'adm:series']],
            [['text' => '🗑 Удалить', 'callback_data' => 'adm:list'], ['text' => '📊 Статистика', 'callback_data' => 'adm:stats']],
            [['text' => '📢 Рассылка', 'callback_data' => 'adm:broadcast'], ['text' => '⚙ Настройки', 'callback_data' => 'adm:settings']],
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
            $this->api->answerCallbackQuery($cbId, '⛔ Только для админов', true);
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
                $text = "📊 <b>Статистика</b>\n\n"
                      . "👥 Пользователей: <b>{$s['users']}</b>\n"
                      . "🎥 Фильмов: <b>{$s['movies']}</b>\n"
                      . "📺 Сериалов: <b>{$s['series']}</b>\n"
                      . "🎌 Аниме: <b>{$s['anime']}</b>\n"
                      . "👶 Мультфильмов: <b>{$s['cartoons']}</b>\n"
                      . "📣 Анонсов: <b>{$s['announcements']}</b>\n"
                      . "❤️ В избранном: <b>{$s['favorites']}</b>\n"
                      . "👁 Просмотров: <b>{$s['views']}</b>";
                $this->api->editMessageText($chatId, $msgId, $text, ['reply_markup' => json_encode($this->backMenu())]);
                return;

            case 'adm:broadcast':
                $this->flow->startBroadcast($chatId, $tid);
                return;

            case 'adm:settings':
                $adminList = implode(', ', $this->cfg['telegram']['admin_ids']);
                $text = "⚙ <b>Настройки бота</b>\n\n"
                      . "Приложение: <b>" . htmlspecialchars($this->cfg['app']['name']) . "</b>\n"
                      . "Mini App: <code>" . htmlspecialchars($this->cfg['telegram']['miniapp_url']) . "</code>\n"
                      . "Администраторы: <code>{$adminList}</code>";
                $this->api->editMessageText($chatId, $msgId, $text, ['reply_markup' => json_encode($this->backMenu())]);
                return;

            case 'adm:list':
                $this->sendDeleteList($chatId, $msgId);
                return;

            case 'adm:series':
                $this->sendSeriesList($chatId, $msgId);
                return;

            case 'adm:home':
                $this->api->editMessageText($chatId, $msgId, "🛠 <b>Панель администратора</b>\nВыберите действие:", [
                    'reply_markup' => json_encode($this->adminMenu()),
                ]);
                return;
        }

        if (str_starts_with($data, 'del:')) {
            $id = (int) substr($data, 4);
            if ($this->repo->deleteMovie($id)) {
                $this->api->answerCallbackQuery($cbId, 'Удалено ✅');
                $this->sendDeleteList($chatId, $msgId);
            }
            return;
        }
    }

    private function sendDeleteList(int $chatId, int $msgId): void
    {
        $movies = $this->repo->recentMovies(12);
        if (!$movies) {
            $this->api->editMessageText($chatId, $msgId, 'Каталог пуст — добавьте контент.', ['reply_markup' => json_encode($this->backMenu())]);
            return;
        }
        $rows = [];
        foreach ($movies as $m) {
            $rows[] = [['text' => '🗑 ' . mb_strimwidth($m['title'], 0, 40, '…'), 'callback_data' => 'del:' . $m['id']]];
        }
        $rows[] = [['text' => '⬅️ Назад', 'callback_data' => 'adm:home']];
        $this->api->editMessageText($chatId, $msgId, "🗑 <b>Удаление контента</b>\nНажмите на элемент, чтобы удалить:", [
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
                'Сначала добавьте сериал или аниме (🤖 AI или ➕ Сериал), затем сюда — добавлять серии.',
                ['reply_markup' => json_encode($this->backMenu())]
            );
            return;
        }
        $rows = [];
        foreach ($series as $s) {
            $rows[] = [[
                'text' => '📺 ' . mb_strimwidth($s['title'], 0, 40, '…'),
                'callback_data' => 'ep:add:' . $s['id'],
            ]];
        }
        $rows[] = [['text' => '⬅️ Назад', 'callback_data' => 'adm:home']];
        $this->api->editMessageText(
            $chatId,
            $msgId,
            "📺 <b>Серии сериала</b>\nВыберите сериал/аниме, чтобы добавить сезоны и серии:",
            ['reply_markup' => json_encode(['inline_keyboard' => $rows])]
        );
    }

    private function backMenu(): array
    {
        return ['inline_keyboard' => [[['text' => '⬅️ Назад', 'callback_data' => 'adm:home']]]];
    }

    // ---- Keyboards ------------------------------------------------------

    private function userKeyboard(int $tid): array
    {
        $url  = $this->cfg['telegram']['miniapp_url'];
        $rows = [
            [['text' => '🎬 Открыть кино', 'web_app' => ['url' => $url]]],
            [['text' => '🔥 Новинки'], ['text' => '🎞 Категории']],
            [['text' => '❤️ Избранное'], ['text' => '🕒 История']],
            [['text' => '⚙ Настройки'], ['text' => '❓ Помощь']],
        ];
        if ($this->isAdmin($tid)) {
            $rows[] = [['text' => '⚙ Панель']];
        }
        return ['reply_markup' => json_encode(['keyboard' => $rows, 'resize_keyboard' => true])];
    }

    private function openAppInline(): array
    {
        return ['reply_markup' => json_encode([
            'inline_keyboard' => [[['text' => '🎬 Открыть кино', 'web_app' => ['url' => $this->cfg['telegram']['miniapp_url']]]]],
        ])];
    }

    private function isAdmin(int $tid): bool
    {
        return in_array($tid, $this->cfg['telegram']['admin_ids'], true);
    }
}
