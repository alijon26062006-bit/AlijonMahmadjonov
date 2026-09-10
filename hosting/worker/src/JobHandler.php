<?php
declare(strict_types=1);

namespace Hosting\Worker;

use Hosting\Config;
use Hosting\Database;
use Hosting\Model\DatabaseRepository;
use Hosting\Model\DatabaseUserRepository;
use Hosting\Model\DomainRepository;
use Hosting\Model\NotificationRepository;
use Hosting\Model\PlanRepository;
use Hosting\Model\SiteRepository;
use Hosting\Model\UserRepository;
use Hosting\Service\MysqlManager;
use Hosting\Support\Shell;
use Hosting\Worker\Provisioning\NginxManager;
use Hosting\Worker\Provisioning\PhpFpmManager;
use Hosting\Worker\Provisioning\SiteFiles;
use Hosting\Worker\Provisioning\TemplateRenderer;
use Hosting\Worker\Provisioning\UnixProvisioner;

/**
 * Единственное место, где панель (через очередь jobs) добирается до системных команд.
 * Каждый job.type обязан быть в TYPES — никаких «выполнить произвольную команду».
 * Все ID из payload приходят из БД, а не от пользователя напрямую, но всё равно
 * прогоняются через строгую числовую проверку перед использованием где-либо в shell.
 */
final class JobHandler
{
    public const TYPES = [
        'create_user', 'create_site', 'delete_site', 'suspend_site', 'unsuspend_site',
        'create_database', 'delete_database', 'apply_nginx', 'apply_php_fpm',
        'issue_ssl', 'create_backup', 'restore_backup', 'apply_quota',
    ];

    private UnixProvisioner $unix;
    private SiteFiles $files;
    private NginxManager $nginx;
    private PhpFpmManager $fpm;
    private TemplateRenderer $renderer;
    private MysqlManager $mysql;

    private UserRepository $users;
    private PlanRepository $plans;
    private SiteRepository $sites;
    private DomainRepository $domains;
    private DatabaseRepository $databases;
    private DatabaseUserRepository $databaseUsers;
    private NotificationRepository $notifications;

    public function __construct(private Database $db, private Config $config, private string $templateDir)
    {
        $this->unix = new UnixProvisioner($config->str('users_root'));
        $this->files = new SiteFiles();
        $this->nginx = new NginxManager($config->str('nginx_available_dir'), $config->str('nginx_enabled_dir'));
        $this->fpm = new PhpFpmManager($config->str('fpm_pool_dir'), $config->defaultPhpVersion());
        $this->renderer = new TemplateRenderer($templateDir);
        $this->mysql = new MysqlManager($config);

        $this->plans = new PlanRepository($db);
        $this->users = new UserRepository($db, $this->plans);
        $this->sites = new SiteRepository($db);
        $this->domains = new DomainRepository($db);
        $this->databases = new DatabaseRepository($db);
        $this->databaseUsers = new DatabaseUserRepository($db);
        $this->notifications = new NotificationRepository($db);
    }

    /**
     * @param array<string,mixed> $job
     * @return string|null одноразовый секрет (например, пароль новой БД), если задание его породило
     */
    public function handle(array $job): ?string
    {
        $type = (string) $job['type'];
        if (!in_array($type, self::TYPES, true)) {
            throw new \RuntimeException('Задание не в белом списке: ' . $type);
        }

        $payload = $job['payload'] !== null ? (json_decode((string) $job['payload'], true) ?? []) : [];
        $method = 'handle' . str_replace('_', '', ucwords($type, '_'));

        return $this->{$method}($job, $payload);
    }

    // ── create_user ─────────────────────────────────────────────────────────────

    private function handleCreateUser(array $job, array $payload): ?string
    {
        $user = $this->requireUser($job);
        $this->unix->createUser((string) $user['system_user']);
        $this->db->log((int) $user['id'], 'user.provisioned', 'user', (int) $user['id']);
        return null;
    }

    // ── create_site / delete_site / suspend / unsuspend ────────────────────────

    private function handleCreateSite(array $job, array $payload): ?string
    {
        $user = $this->requireUser($job);
        $site = $this->requireSite($job, $payload);

        $this->unix->createUser((string) $user['system_user']);
        $home = $this->unix->homeDir((string) $user['system_user']);

        $this->files->create(
            $home,
            (string) $site['slug'],
            (string) $site['doc_root'],
            (string) $user['system_user'],
            $this->templateDir . '/skel/public_html',
        );

        $plan = $this->plans->findById((int) $user['plan_id']) ?? throw new \RuntimeException('У клиента не задан тариф');
        $this->applyFpmPool($user, $plan);
        $this->applySiteNginxConf($user, $site);

        $this->sites->setStatus((int) $site['id'], 'active');
        $this->db->log((int) $user['id'], 'site.created', 'site', (int) $site['id']);
        return null;
    }

    private function handleDeleteSite(array $job, array $payload): ?string
    {
        $user = $this->requireUser($job);
        $site = $this->requireSite($job, $payload);
        $home = $this->unix->homeDir((string) $user['system_user']);

        $this->nginx->remove($site['domain'] . '.conf');
        $this->files->remove($home, (string) $site['slug']);

        // Пул php-fpm клиента общий на все его сайты — удаляем, только если сайтов не осталось.
        if ($this->sites->countActiveForUser((int) $user['id']) <= 1) {
            $this->fpm->remove($user['system_user'] . '.conf');
        }

        $this->sites->delete((int) $site['id']);
        $this->db->log((int) $user['id'], 'site.deleted', 'site', (int) $site['id']);
        return null;
    }

    private function handleSuspendSite(array $job, array $payload): ?string
    {
        $site = $this->requireSite($job, $payload);
        $rendered = $this->renderer->render('nginx-site-suspended.conf.tpl', [
            'PANEL_NAME' => $this->config->str('panel_name'),
            'DOMAIN'     => (string) $site['domain'],
        ]);
        $this->nginx->writeAndApply($site['domain'] . '.conf', $rendered);
        $this->sites->setStatus((int) $site['id'], 'suspended');
        $this->db->log((int) $job['user_id'], 'site.suspended', 'site', (int) $site['id']);
        return null;
    }

    private function handleUnsuspendSite(array $job, array $payload): ?string
    {
        $user = $this->requireUser($job);
        $site = $this->requireSite($job, $payload);
        $this->applySiteNginxConf($user, $site);
        $this->sites->setStatus((int) $site['id'], 'active');
        $this->db->log((int) $user['id'], 'site.unsuspended', 'site', (int) $site['id']);
        return null;
    }

    private function applySiteNginxConf(array $user, array $site): void
    {
        $home = $this->unix->homeDir((string) $user['system_user']);
        $docRoot = $this->files->docRoot($home, (string) $site['slug'], (string) $site['doc_root']);
        $logDir = $this->files->logDir($home, (string) $site['slug']);
        $fpmUpstream = 'unix:' . str_replace('{user}', (string) $user['system_user'], $this->config->str('fpm_listen_tpl'));
        $rootDomain = $this->config->str('root_domain');
        $isSubdomain = str_ends_with((string) $site['domain'], '.' . $rootDomain);
        $wildcardCert = "/etc/letsencrypt/live/{$rootDomain}/fullchain.pem";
        $wildcardKey = "/etc/letsencrypt/live/{$rootDomain}/privkey.pem";

        $common = [
            'PANEL_NAME'    => $this->config->str('panel_name'),
            'SYSTEM_USER'   => (string) $user['system_user'],
            'DOMAIN'        => (string) $site['domain'],
            'PHP_VERSION'   => (string) $site['php_version'],
            'DOC_ROOT'      => $docRoot,
            'LOG_DIR'       => $logDir,
            'FPM_UPSTREAM'  => $fpmUpstream,
            'UPLOAD_MAX_MB' => (string) $this->config->int('upload_max_mb'),
            'XMLRPC_RULE'   => "limit_req zone=login_req burst=5 nodelay;\n        try_files \$uri =404;\n        include fastcgi_params;\n        fastcgi_param SCRIPT_FILENAME \$document_root\$fastcgi_script_name;\n        fastcgi_pass {$fpmUpstream};",
        ];

        // Поддомены сразу покрыты wildcard-сертификатом базового домена (если он уже выпущен).
        // Свои домены получают TLS отдельно через issue_ssl (HTTP-01), пока просто HTTP-vhost.
        if ($isSubdomain && is_file($wildcardCert)) {
            $rendered = $this->renderer->render('nginx-site-ssl.conf.tpl', $common + [
                'SSL_CERT'     => $wildcardCert,
                'SSL_KEY'      => $wildcardKey,
                'ACME_WEBROOT' => $docRoot,
            ]);
        } else {
            $rendered = $this->renderer->render('nginx-site.conf.tpl', $common);
        }

        $this->nginx->writeAndApply($site['domain'] . '.conf', $rendered);
    }

    private function applyFpmPool(array $user, array $plan): void
    {
        $home = $this->unix->homeDir((string) $user['system_user']);
        $rendered = $this->renderer->render('php-fpm-pool.conf.tpl', [
            'PANEL_NAME'      => $this->config->str('panel_name'),
            'SYSTEM_USER'     => (string) $user['system_user'],
            'EMAIL'           => (string) ($user['email'] ?? ''),
            'PLAN_TITLE'      => (string) $plan['title'],
            'LISTEN'          => str_replace('{user}', (string) $user['system_user'], $this->config->str('fpm_listen_tpl')),
            'HOME'            => $home,
            'PM_MAX_CHILDREN' => (string) $plan['pm_max_children'],
            'MEMORY_LIMIT_MB' => (string) $plan['memory_limit_mb'],
            'UPLOAD_MAX_MB'   => (string) $this->config->int('upload_max_mb'),
        ]);
        $this->fpm->writeAndApply($user['system_user'] . '.conf', $rendered);
    }

    // ── create_database / delete_database ───────────────────────────────────────

    private function handleCreateDatabase(array $job, array $payload): ?string
    {
        $user = $this->requireUser($job);
        $databaseId = (int) ($payload['database_id'] ?? 0);
        $database = $this->databases->findById($databaseId);
        if (!DatabaseRepository::belongsToUser($database, (int) $user['id'])) {
            throw new \RuntimeException('database_id не принадлежит клиенту задания');
        }

        $plan = $this->plans->findById((int) $user['plan_id']) ?? throw new \RuntimeException('У клиента не задан тариф');
        $dbUserRow = $this->databaseUsers->getOrCreateForUser($user, (int) $plan['db_max_user_connections']);

        $newPassword = $this->mysql->ensureUser((string) $dbUserRow['db_user'], (int) $plan['db_max_user_connections']);
        $this->mysql->createDatabase((string) $database['db_name'], (string) $dbUserRow['db_user']);
        $this->databases->setStatus($databaseId, 'active');

        $this->db->log((int) $user['id'], 'database.created', 'database', $databaseId);

        if ($newPassword !== null) {
            $this->notifications->create(
                (int) $user['id'],
                'panel',
                'Доступ к базам данных создан',
                "Пользователь: {$dbUserRow['db_user']}\nХост: localhost или 127.0.0.1 — работают оба\n"
                . "Пароль показан один раз в панели сразу после создания базы — если вы его не сохранили, сбросьте через «Сменить пароль базы»."
            );
        }

        // Пароль возвращается наверх (а не хранится в свойстве) — воркер положит его
        // в одноразовое поле jobs.result_secret, панель прочитает и сразу сотрёт.
        return $newPassword;
    }

    private function handleDeleteDatabase(array $job, array $payload): ?string
    {
        $user = $this->requireUser($job);
        $databaseId = (int) ($payload['database_id'] ?? 0);
        $database = $this->databases->findById($databaseId);
        if (!DatabaseRepository::belongsToUser($database, (int) $user['id'])) {
            throw new \RuntimeException('database_id не принадлежит клиенту задания');
        }

        $this->mysql->dropDatabase((string) $database['db_name']);
        $this->databases->delete($databaseId);

        if ($this->databases->countActiveForUser((int) $user['id']) === 0) {
            $dbUserRow = $this->databaseUsers->findForUser((int) $user['id']);
            if ($dbUserRow !== null) {
                $this->mysql->dropUser((string) $dbUserRow['db_user']);
            }
        }

        $this->db->log((int) $user['id'], 'database.deleted', 'database', $databaseId);
        return null;
    }

    // ── apply_nginx / apply_php_fpm — переприменить всё для клиента (например, после смены тарифа) ──

    private function handleApplyNginx(array $job, array $payload): ?string
    {
        $user = $this->requireUser($job);
        foreach ($this->sites->forUser((int) $user['id']) as $site) {
            if ($site['status'] === 'active') {
                $this->applySiteNginxConf($user, $site);
            }
        }
        return null;
    }

    private function handleApplyPhpFpm(array $job, array $payload): ?string
    {
        $user = $this->requireUser($job);
        $plan = $this->plans->findById((int) $user['plan_id']) ?? throw new \RuntimeException('У клиента не задан тариф');
        $this->applyFpmPool($user, $plan);
        return null;
    }

    // ── issue_ssl — свой домен клиента, HTTP-01 через certbot webroot ──────────

    private function handleIssueSsl(array $job, array $payload): ?string
    {
        $user = $this->requireUser($job);
        $site = $this->requireSite($job, $payload);
        $domainId = (int) ($payload['domain_id'] ?? 0);
        $domain = $this->domains->findById($domainId);
        if ($domain === null || (int) $domain['site_id'] !== (int) $site['id']) {
            throw new \RuntimeException('domain_id не принадлежит сайту задания');
        }
        if (!$domain['verified']) {
            throw new \RuntimeException('Домен не прошёл DNS-проверку — SSL не выпускается');
        }

        $home = $this->unix->homeDir((string) $user['system_user']);
        $docRoot = $this->files->docRoot($home, (string) $site['slug'], (string) $site['doc_root']);
        $acmeEmail = $this->config->str('acme_email');

        $this->domains->setSslStatus($domainId, 'pending');

        $cmd = sprintf(
            'certbot certonly --non-interactive --agree-tos --webroot -w %s -d %s %s',
            escapeshellarg($docRoot),
            escapeshellarg((string) $domain['domain']),
            $acmeEmail !== '' ? '-m ' . escapeshellarg($acmeEmail) : '--register-unsafely-without-email',
        );
        $result = Shell::run($cmd, 60);

        if ($result['code'] !== 0) {
            $this->domains->setSslStatus($domainId, 'failed');
            throw new \RuntimeException('certbot не смог выпустить сертификат: ' . $result['err']);
        }

        $certDir = "/etc/letsencrypt/live/{$domain['domain']}";
        $rendered = $this->renderer->render('nginx-site-ssl.conf.tpl', [
            'PANEL_NAME'   => $this->config->str('panel_name'),
            'SYSTEM_USER'  => (string) $user['system_user'],
            'DOMAIN'       => (string) $domain['domain'],
            'PHP_VERSION'  => (string) $site['php_version'],
            'DOC_ROOT'     => $docRoot,
            'LOG_DIR'      => $this->files->logDir($home, (string) $site['slug']),
            'FPM_UPSTREAM' => 'unix:' . str_replace('{user}', (string) $user['system_user'], $this->config->str('fpm_listen_tpl')),
            'UPLOAD_MAX_MB' => (string) $this->config->int('upload_max_mb'),
            'SSL_CERT'     => $certDir . '/fullchain.pem',
            'SSL_KEY'      => $certDir . '/privkey.pem',
            'ACME_WEBROOT' => $docRoot,
            'XMLRPC_RULE'  => 'deny all;',
        ]);
        $this->nginx->writeAndApply($domain['domain'] . '.conf', $rendered);

        $this->domains->setSslStatus($domainId, 'issued');
        $this->db->log((int) $user['id'], 'domain.ssl_issued', 'domain', $domainId);
        return null;
    }

    // ── backups ──────────────────────────────────────────────────────────────

    private function handleCreateBackup(array $job, array $payload): ?string
    {
        $user = $this->requireUser($job);
        $backupId = (int) ($payload['backup_id'] ?? 0);
        $script = $this->config->str('hosting_root') . '/scripts/backup.sh';

        $result = Shell::run(sprintf(
            '%s --user %s --backup-id %d',
            escapeshellarg($script),
            escapeshellarg((string) $user['system_user']),
            $backupId,
        ), 600);

        if ($result['code'] !== 0) {
            throw new \RuntimeException('backup.sh завершился с ошибкой: ' . $result['err']);
        }
        $this->db->log((int) $user['id'], 'backup.created', 'backup', $backupId);
        return null;
    }

    private function handleRestoreBackup(array $job, array $payload): ?string
    {
        $user = $this->requireUser($job);
        $backupId = (int) ($payload['backup_id'] ?? 0);
        $script = $this->config->str('hosting_root') . '/scripts/restore.sh';

        $result = Shell::run(sprintf(
            '%s --user %s --backup-id %d',
            escapeshellarg($script),
            escapeshellarg((string) $user['system_user']),
            $backupId,
        ), 600);

        if ($result['code'] !== 0) {
            throw new \RuntimeException('restore.sh завершился с ошибкой: ' . $result['err']);
        }
        $this->db->log((int) $user['id'], 'backup.restored', 'backup', $backupId);
        return null;
    }

    // ── quota ────────────────────────────────────────────────────────────────

    private function handleApplyQuota(array $job, array $payload): ?string
    {
        $user = $this->requireUser($job);
        $script = $this->config->str('hosting_root') . '/scripts/apply-quota.sh';

        $result = Shell::run(sprintf(
            '%s %s %d %d',
            escapeshellarg($script),
            escapeshellarg((string) $user['system_user']),
            (int) $user['disk_quota_mb'],
            (int) $user['inode_limit'],
        ), 30);

        if ($result['code'] !== 0) {
            throw new \RuntimeException('apply-quota.sh завершился с ошибкой: ' . $result['err']);
        }
        return null;
    }

    // ── helpers ──────────────────────────────────────────────────────────────

    private function requireUser(array $job): array
    {
        $userId = (int) ($job['user_id'] ?? 0);
        if ($userId <= 0) {
            throw new \RuntimeException('У задания не указан user_id');
        }
        return $this->users->findById($userId) ?? throw new \RuntimeException('Клиент не найден: ' . $userId);
    }

    private function requireSite(array $job, array $payload): array
    {
        $siteId = (int) ($job['site_id'] ?? $payload['site_id'] ?? 0);
        if ($siteId <= 0) {
            throw new \RuntimeException('У задания не указан site_id');
        }
        $site = $this->sites->findById($siteId);
        if (!SiteRepository::belongsToUser($site, (int) $job['user_id'])) {
            throw new \RuntimeException('site_id не принадлежит клиенту задания');
        }
        return $site;
    }
}
