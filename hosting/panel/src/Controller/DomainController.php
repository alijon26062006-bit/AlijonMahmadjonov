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
use Hosting\Model\DomainRepository;
use Hosting\Model\JobRepository;
use Hosting\Model\SiteRepository;
use Hosting\Service\Auth;
use Hosting\Support\Domain;
use Hosting\Support\DnsVerifier;
use Hosting\Support\Flash;
use Hosting\Support\View;

/**
 * Собственные домены клиента: добавление → проверка DNS (см. DnsVerifier — здесь же
 * и защита от SSRF/внутренних имён) → выпуск SSL (issue_ssl job) только после verified=1.
 */
final class DomainController
{
    public function __construct(
        private Config $config,
        private Database $db,
        private Auth $auth,
        private SiteRepository $sites,
        private DomainRepository $domains,
        private JobRepository $jobs,
        private View $view,
    ) {
    }

    public function index(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);

        return Response::html($this->view->page('domains/index', [
            'csrf'    => $this->auth->csrfToken(),
            'site'    => $site,
            'domains' => $this->domains->forSite((int) $site['id']),
        ]));
    }

    public function create(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела');
            return Response::redirect("/sites/{$siteId}/domains");
        }

        $domain = Domain::normalize($request->input('domain'));
        if (!Domain::isValidFqdn($domain)) {
            Flash::add('error', 'Некорректное доменное имя');
            return Response::redirect("/sites/{$siteId}/domains");
        }
        if ($this->domains->findByDomain($domain) !== null || $this->sites->findByDomain($domain) !== null) {
            Flash::add('error', 'Этот домен уже привязан в системе');
            return Response::redirect("/sites/{$siteId}/domains");
        }

        $record = $this->domains->create((int) $site['id'], $domain);
        $this->db->log((int) $user['id'], 'domain.added', 'domain', (int) $record['id']);
        Flash::add('success', "Домен {$domain} добавлен. Теперь направьте его A-запись на IP сервера и нажмите «Проверить DNS».");
        return Response::redirect("/sites/{$siteId}/domains");
    }

    public function verify(Request $request, int $siteId, int $domainId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        $domain = $this->ownedDomain($site, $domainId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return Response::redirect("/sites/{$siteId}/domains");
        }

        $result = DnsVerifier::pointsToServer((string) $domain['domain'], $this->config->str('server_ip'));

        if ($result['ok']) {
            $this->domains->markVerified((int) $domain['id']);
            $this->db->log((int) $user['id'], 'domain.verified', 'domain', (int) $domain['id']);
            Flash::add('success', 'DNS проверен — домен указывает на сервер. Теперь можно выпустить SSL.');
        } else {
            $this->domains->markVerificationFailed((int) $domain['id'], $result['error']);
            $this->db->recordSecurityEvent('domain_verify_failed', 'info', '', [
                'domain' => $domain['domain'], 'error' => $result['error'],
            ], (int) $user['id']);
            Flash::add('error', 'DNS-проверка не пройдена: ' . $result['error']);
        }

        return Response::redirect("/sites/{$siteId}/domains");
    }

    public function issueSsl(Request $request, int $siteId, int $domainId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        $domain = $this->ownedDomain($site, $domainId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return Response::redirect("/sites/{$siteId}/domains");
        }

        if (!$domain['verified']) {
            Flash::add('error', 'Сначала пройдите проверку DNS');
            return Response::redirect("/sites/{$siteId}/domains");
        }

        $this->jobs->enqueue('issue_ssl', (int) $user['id'], (int) $site['id'], [
            'site_id'   => $site['id'],
            'domain_id' => $domain['id'],
        ]);
        Flash::add('success', 'Выпуск SSL-сертификата запущен, обычно занимает меньше минуты.');
        return Response::redirect("/sites/{$siteId}/domains");
    }

    public function delete(Request $request, int $siteId, int $domainId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        $domain = $this->ownedDomain($site, $domainId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return Response::redirect("/sites/{$siteId}/domains");
        }

        $this->domains->delete((int) $domain['id']);
        $this->db->log((int) $user['id'], 'domain.deleted', 'domain', (int) $domain['id']);
        Flash::add('success', 'Домен отвязан');
        return Response::redirect("/sites/{$siteId}/domains");
    }

    private function requireUser(): array
    {
        $user = $this->auth->user();
        if ($user === null) {
            throw new UnauthorizedException();
        }
        return $user;
    }

    private function ownedSite(array $user, int $siteId): array
    {
        $site = $this->sites->findById($siteId);
        if ($site === null) {
            throw new NotFoundException('Сайт не найден');
        }
        if ((int) $site['user_id'] !== (int) $user['id'] && $user['role'] !== 'admin') {
            throw new ForbiddenException('Этот сайт вам не принадлежит');
        }
        return $site;
    }

    private function ownedDomain(array $site, int $domainId): array
    {
        $domain = $this->domains->findById($domainId);
        if ($domain === null || (int) $domain['site_id'] !== (int) $site['id']) {
            throw new NotFoundException('Домен не найден');
        }
        return $domain;
    }
}
