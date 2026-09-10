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
use Hosting\Service\Auth;
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
        private SiteRepository $sites,
        private PlanRepository $plans,
        private JobRepository $jobs,
        private View $view,
    ) {
    }

    public function index(Request $request): Response
    {
        $user = $this->requireUser();
        return Response::html($this->view->page('sites/index', [
            'csrf'       => $this->auth->csrfToken(),
            'sites'      => $this->sites->forUser((int) $user['id']),
            'user'       => $user,
            'rootDomain' => $this->config->str('root_domain'),
        ]));
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
        return Response::redirect('/sites');
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
