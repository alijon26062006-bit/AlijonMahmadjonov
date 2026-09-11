<?php
declare(strict_types=1);

namespace Hosting\Controller;

use Hosting\Config;
use Hosting\Database;
use Hosting\Http\ForbiddenException;
use Hosting\Http\NotFoundException;
use Hosting\Http\Request;
use Hosting\Http\Response;
use Hosting\Http\UnauthorizedException;
use Hosting\Model\SiteRepository;
use Hosting\Service\Auth;
use Hosting\Service\FileManager;
use Hosting\Service\SiteEnv;
use Hosting\Service\SiteTemplates;
use Hosting\Service\TelegramWebhook;
use Hosting\Support\Flash;

/**
 * Telegram-бот на сайте клиента: токен, webhook.php, подключение и проверка webhook.
 *
 * Токен клиента живёт только в .env его сайта (над public/), в базу панели не
 * попадает и обратно в интерфейс не возвращается — показывается маска.
 */
final class TelegramSiteController
{
    public function __construct(
        private Config $config,
        private Database $db,
        private Auth $auth,
        private SiteRepository $sites,
        private TelegramWebhook $telegram,
    ) {
    }

    /** Сохранить/заменить токен бота. */
    public function saveToken(Request $request, int $siteId): Response
    {
        [$user, $site] = $this->context($request, $siteId);
        $token = trim($request->raw('token'));

        if ($token === '') {
            Flash::add('error', 'Токен пустой');
            return $this->back($siteId);
        }
        if (preg_match('~^\d{5,}:[A-Za-z0-9_-]{30,}$~', $token) !== 1) {
            Flash::add('error', 'Это не похоже на токен бота. Он выглядит так: 123456789:AAE… — возьмите его в @BotFather.');
            return $this->back($siteId);
        }

        // Проверяем токен у самого Telegram: опечатку лучше поймать здесь, чем
        // потом гадать, почему webhook не подключается.
        $me = $this->telegram->getMe($token);
        if (!$me['ok']) {
            Flash::add('error', 'Telegram не принял токен: ' . ($me['error'] ?? 'неизвестная ошибка'));
            return $this->back($siteId);
        }

        $env = $this->envFor($user, $site);
        $secret = $env->get('TELEGRAM_WEBHOOK_SECRET');
        if ($secret === '') {
            $secret = TelegramWebhook::generateSecret();
        }

        $env->set([
            'TELEGRAM_BOT_TOKEN'      => $token,
            'TELEGRAM_BOT_USERNAME'   => $me['username'],
            'TELEGRAM_WEBHOOK_SECRET' => $secret,
        ]);

        // В журнал пишем факт, но не токен.
        $this->db->log((int) $user['id'], 'telegram.token_saved', 'site', (int) $site['id'], 'success', [
            'bot' => $me['username'],
        ]);
        Flash::add('success', 'Токен сохранён. Бот: @' . $me['username']);

        return $this->back($siteId);
    }

    /** Создать webhook.php из шаблона. */
    public function createWebhookFile(Request $request, int $siteId): Response
    {
        [$user, $site] = $this->context($request, $siteId);
        $template = SiteTemplates::get('telegram');

        try {
            $fm = new FileManager($this->siteDir($user, $site));
            foreach ($template['files'] as $relative => $contents) {
                $fm->createFileDeep($relative, $contents, $request->input('overwrite') === '1');
            }
            Flash::add('success', 'Создан public/webhook.php — откройте его в файловом менеджере, чтобы добавить свою логику.');
        } catch (\Throwable $e) {
            Flash::add('error', $e->getMessage());
        }

        return $this->back($siteId);
    }

    /** Подключить webhook: setWebhook с секретом. */
    public function connect(Request $request, int $siteId): Response
    {
        [$user, $site] = $this->context($request, $siteId);
        $env = $this->envFor($user, $site);
        $token = $env->get('TELEGRAM_BOT_TOKEN');

        if ($token === '') {
            Flash::add('error', 'Сначала сохраните токен бота');
            return $this->back($siteId);
        }
        if (!is_file($this->siteDir($user, $site) . '/public/webhook.php')) {
            Flash::add('error', 'Нет файла public/webhook.php — создайте его кнопкой выше');
            return $this->back($siteId);
        }

        // Секрет пересоздаём при каждом подключении: так «Подключить ещё раз»
        // чинит рассинхрон, когда в .env один секрет, а у Telegram другой.
        $secret = TelegramWebhook::generateSecret();
        $env->set(['TELEGRAM_WEBHOOK_SECRET' => $secret]);

        $url = 'https://' . $site['domain'] . '/webhook.php';
        $result = $this->telegram->setWebhook($token, $url, $secret);

        if ($result['ok']) {
            $this->db->log((int) $user['id'], 'telegram.webhook_connected', 'site', (int) $site['id']);
            Flash::add('success', 'Webhook успешно подключён: ' . $url);
        } else {
            Flash::add('error', 'Telegram отказался подключать webhook: ' . ($result['error'] ?? ''));
        }

        return $this->back($siteId);
    }

    /** Проверить webhook: getWebhookInfo. */
    public function check(Request $request, int $siteId): Response
    {
        [$user, $site] = $this->context($request, $siteId);
        $token = $this->envFor($user, $site)->get('TELEGRAM_BOT_TOKEN');

        if ($token === '') {
            Flash::add('error', 'Сначала сохраните токен бота');
            return $this->back($siteId);
        }

        $this->auth->ensureSession();
        $result = $this->telegram->getInfo($token);
        if (!$result['ok']) {
            Flash::add('error', 'Telegram не ответил: ' . ($result['error'] ?? ''));
            return $this->back($siteId);
        }

        // Результат кладём во flash-сессию — страница сайта его покажет.
        Flash::add('success', 'Проверка выполнена');
        $_SESSION['telegram_webhook_info'][$siteId] = $result['info'];

        return $this->back($siteId);
    }

    /** Отключить webhook: deleteWebhook. */
    public function disconnect(Request $request, int $siteId): Response
    {
        [$user, $site] = $this->context($request, $siteId);
        $token = $this->envFor($user, $site)->get('TELEGRAM_BOT_TOKEN');

        if ($token === '') {
            Flash::add('error', 'Токен не задан');
            return $this->back($siteId);
        }

        $this->auth->ensureSession();
        $result = $this->telegram->deleteWebhook($token);
        unset($_SESSION['telegram_webhook_info'][$siteId]);

        if ($result['ok']) {
            $this->db->log((int) $user['id'], 'telegram.webhook_disconnected', 'site', (int) $site['id']);
            Flash::add('success', 'Webhook отключён');
        } else {
            Flash::add('error', 'Не удалось отключить: ' . ($result['error'] ?? ''));
        }

        return $this->back($siteId);
    }

    private function siteDir(array $user, array $site): string
    {
        return rtrim($this->config->str('users_root'), '/') . '/' . $user['system_user']
            . '/sites/' . $site['slug'];
    }

    private function envFor(array $user, array $site): SiteEnv
    {
        return new SiteEnv($this->siteDir($user, $site));
    }

    private function back(int $siteId): Response
    {
        return Response::redirect('/sites/' . $siteId . '#telegram');
    }

    /** @return array{0:array<string,mixed>,1:array<string,mixed>} */
    private function context(Request $request, int $siteId): array
    {
        $user = $this->auth->user();
        if ($user === null) {
            throw new UnauthorizedException();
        }
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела, попробуйте ещё раз');
            throw new ForbiddenException('Форма устарела');
        }

        $site = $this->sites->findById($siteId);
        if ($site === null) {
            throw new NotFoundException('Сайт не найден');
        }
        if ((int) $site['user_id'] !== (int) $user['id'] && $user['role'] !== 'admin') {
            throw new ForbiddenException('Этот сайт вам не принадлежит');
        }

        return [$user, $site];
    }
}
