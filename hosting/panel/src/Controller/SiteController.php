<?php
declare(strict_types=1);

namespace Hosting\Controller;

use Hosting\Config;
use Hosting\Database;
use Hosting\Http\Request;
use Hosting\Http\Response;
use Hosting\Model\JobRepository;
use Hosting\Model\PlanRepository;
use Hosting\Model\SiteRepository;
use Hosting\Http\ForbiddenException;
use Hosting\Http\NotFoundException;
use Hosting\Http\UnauthorizedException;
use Hosting\Service\Auth;
use Hosting\Service\Billing;
use Hosting\Service\Quota;
use Hosting\Service\SiteEnv;
use Hosting\Service\SiteHealth;
use Hosting\Service\TelegramWebhook;
use Hosting\Support\Domain;
use Hosting\Support\Flash;
use Hosting\Support\View;

/** Создание и управление сайтами клиента. Каждый доступ к чужому сайту — 403, не 404 с утечкой. */
final class SiteController
{
    public function __construct(
        private Config $config,
        private Database $db,
        private Auth $auth,
        private Billing $billing,
        private SiteRepository $sites,
        private PlanRepository $plans,
        private JobRepository $jobs,
        private View $view,
    ) {
    }

    public function index(Request $request): Response
    {
        $user = $this->requireUser();

        // Тариф, место на диске и баланс показываем прямо здесь: клиент приходит
        // на эту страницу создавать сайт, и лимит «2 из 2» должен быть виден
        // до нажатия кнопки, а не в виде ошибки после.
        $home = rtrim($this->config->str('users_root'), '/') . '/' . $user['system_user'];
        $quota = is_dir($home)
            ? Quota::usage($home, (int) $user['disk_quota_mb'])
            : ['used' => 0, 'limit' => (int) $user['disk_quota_mb'] * 1024 * 1024, 'percent' => 0, 'exceeded' => false];

        return Response::html($this->view->page('sites/index', [
            'csrf'       => $this->auth->csrfToken(),
            'sites'      => $this->sites->forUser((int) $user['id']),
            'user'       => $user,
            'rootDomain' => $this->config->str('root_domain'),
            'plan'       => $this->plans->findById((int) $user['plan_id']),
            'quota'      => $quota,
            'summary'    => $this->billing->summary($user),
        ]));
    }

    /** Страница одного сайта: всё управление им в одном месте. */
    public function show(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        $this->auth->ensureSession();

        $siteDir = rtrim($this->config->str('users_root'), '/') . '/' . $user['system_user']
            . '/sites/' . $site['slug'];
        $env = new SiteEnv($siteDir);
        $token = $env->get('TELEGRAM_BOT_TOKEN');

        // Информацию о webhook показываем только сразу после нажатия «Проверить»,
        // чтобы не дёргать Telegram на каждое открытие страницы.
        $webhookInfo = $_SESSION['telegram_webhook_info'][$siteId] ?? null;
        unset($_SESSION['telegram_webhook_info'][$siteId]);

        return Response::html($this->view->page('sites/show', [
            'csrf'         => $this->auth->csrfToken(),
            'site'         => $site,
            'jobs'         => $this->jobs->recentForSite((int) $site['id'], 6),
            'hasWebhookFile' => is_file($siteDir . '/public/webhook.php'),
            'botToken'     => $token,
            'botMasked'    => SiteEnv::maskToken($token),
            'botUsername'  => $env->get('TELEGRAM_BOT_USERNAME'),
            'webhookUrl'   => 'https://' . $site['domain'] . '/webhook.php',
            'webhookInfo'  => is_array($webhookInfo) ? $webhookInfo : null,
            'webhookHint'  => is_array($webhookInfo) ? TelegramWebhook::explain($webhookInfo) : null,
            'health'       => $_SESSION['site_health'][$siteId] ?? null,
        ]));
    }

    /** Кнопка «Проверить сайт»: обычный HTTP-запрос по публичному адресу. */
    public function health(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела');
            return Response::redirect('/sites/' . $siteId);
        }

        $this->auth->ensureSession();
        $_SESSION['site_health'][$siteId] = (new SiteHealth())->check((string) $site['domain']);

        return Response::redirect('/sites/' . $siteId);
    }

    public function create(Request $request): Response
    {
        $user = $this->requireUser();
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела, попробуйте ещё раз');
            return Response::redirect('/sites');
        }

        $slug = strtolower(trim($request->input('slug')));

        if (!Domain::isValidLabel($slug)) {
            Flash::add('error', 'Недопустимое имя поддомена: 3–30 символов, латиница/цифры/дефис, не зарезервировано');
            return Response::redirect('/sites');
        }

        if ($this->sites->countActiveForUser((int) $user['id']) >= (int) $user['max_sites']) {
            Flash::add('error', 'Достигнут лимит сайтов по тарифу. Смените тариф, чтобы создать ещё один сайт.');
            return Response::redirect('/sites');
        }

        if ($this->sites->findBySlugForUser((int) $user['id'], $slug) !== null) {
            Flash::add('error', 'У вас уже есть сайт с таким именем');
            return Response::redirect('/sites');
        }

        $domain = $slug . '.' . $this->config->str('root_domain');
        if ($this->sites->findByDomain($domain) !== null) {
            Flash::add('error', 'Этот адрес уже занят');
            return Response::redirect('/sites');
        }

        $site = $this->sites->create((int) $user['id'], $slug, $domain, $this->config->defaultPhpVersion());
        $this->jobs->enqueue('create_site', (int) $user['id'], (int) $site['id'], ['site_id' => $site['id']]);

        $this->db->log((int) $user['id'], 'site.create_requested', 'site', (int) $site['id']);
        Flash::add('success', "Сайт {$domain} создаётся — обычно это занимает несколько секунд.");

        // На страницу сайта, а не в общий список: там показан прогресс создания
        // и страница сама обновляется, пока провижининг не закончится.
        return Response::redirect('/sites/' . (int) $site['id']);
    }

    public function delete(Request $request, int $id): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $id);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела, попробуйте ещё раз');
            return Response::redirect('/sites');
        }

        $this->jobs->enqueue('delete_site', (int) $user['id'], (int) $site['id'], ['site_id' => $site['id']]);
        $this->db->log((int) $user['id'], 'site.delete_requested', 'site', (int) $site['id']);
        Flash::add('success', 'Сайт удаляется');
        return Response::redirect('/sites');
    }

    public function suspend(Request $request, int $id): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $id);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return Response::redirect('/sites');
        }
        $this->jobs->enqueue('suspend_site', (int) $user['id'], (int) $site['id'], ['site_id' => $site['id']]);
        Flash::add('success', 'Сайт приостанавливается');
        return Response::redirect('/sites');
    }

    public function unsuspend(Request $request, int $id): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $id);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return Response::redirect('/sites');
        }
        $this->jobs->enqueue('unsuspend_site', (int) $user['id'], (int) $site['id'], ['site_id' => $site['id']]);
        Flash::add('success', 'Сайт возобновляется');
        return Response::redirect('/sites');
    }

    private function requireUser(): array
    {
        $user = $this->auth->user();
        if ($user === null) {
            throw new \Hosting\Http\UnauthorizedException();
        }
        return $user;
    }

    /** IDOR-защита: сайт должен существовать И принадлежать текущему клиенту (админ — исключение). */
    private function ownedSite(array $user, int $siteId): array
    {
        $site = $this->sites->findById($siteId);
        if ($site === null) {
            throw new \Hosting\Http\NotFoundException('Сайт не найден');
        }
        if ((int) $site['user_id'] !== (int) $user['id'] && $user['role'] !== 'admin') {
            throw new \Hosting\Http\ForbiddenException('Этот сайт вам не принадлежит');
        }
        return $site;
    }
}
