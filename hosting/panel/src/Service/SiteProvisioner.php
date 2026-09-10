<?php
declare(strict_types=1);

namespace Hosting\Service;

use Hosting\Config;
use Hosting\Database;
use Hosting\Model\SiteRepository;
use Hosting\Model\UserRepository;
use Hosting\Support\Shell;

/**
 * Разворачивает сайты на диске и собирает конфиги nginx и php-fpm.
 *
 * Панель работает под непривилегированным пользователем и только пишет файлы
 * и ставит флаг «нужно применить». Перезагрузку nginx/php-fpm делает отдельный
 * root-скрипт bin/hosting-apply (см. install.sh и sudoers).
 */
final class SiteProvisioner
{
    public const STATE_NEEDS_APPLY = 'needs_apply';

    public function __construct(
        private Config $config,
        private Database $db,
        private UserRepository $users,
        private SiteRepository $sites,
        private string $templateDir,
    ) {
    }

    public function homeDir(array $user): string
    {
        return $this->config->str('users_dir') . '/' . $user['system_user'];
    }

    public function siteDir(array $user, string $domain): string
    {
        return $this->homeDir($user) . '/sites/' . strtolower($domain);
    }

    public function docRoot(array $user, array $site): string
    {
        return $this->siteDir($user, (string) $site['domain']) . '/' . $site['doc_root'];
    }

    public function logDir(array $user, array $site): string
    {
        return $this->siteDir($user, (string) $site['domain']) . '/logs';
    }

    public function fpmListen(array $user): string
    {
        return str_replace('{user}', (string) $user['system_user'], $this->config->str('fpm_listen_tpl'));
    }

    /** Домашний каталог клиента: sites/, logs/, tmp/. */
    public function ensureHome(array $user): void
    {
        $home = $this->homeDir($user);
        foreach ([$home, $home . '/sites', $home . '/logs', $home . '/tmp'] as $dir) {
            if (!is_dir($dir) && !@mkdir($dir, 0o750, true) && !is_dir($dir)) {
                throw new \RuntimeException('Не удалось создать каталог: ' . $dir);
            }
        }
    }

    /** Каталоги сайта и стартовая страница. Существующие файлы не трогаем. */
    public function provisionSite(array $user, array $site): void
    {
        $this->ensureHome($user);

        $docRoot = $this->docRoot($user, $site);
        $logDir = $this->logDir($user, $site);

        foreach ([$docRoot, $logDir] as $dir) {
            if (!is_dir($dir) && !@mkdir($dir, 0o750, true) && !is_dir($dir)) {
                throw new \RuntimeException('Не удалось создать каталог: ' . $dir);
            }
        }

        $skel = $this->templateDir . '/skel/public_html';
        if (is_dir($skel)) {
            foreach ((array) scandir($skel) as $entry) {
                if ($entry === '.' || $entry === '..') {
                    continue;
                }
                $target = $docRoot . '/' . $entry;
                if (!file_exists($target)) {
                    @copy($skel . '/' . $entry, $target);
                }
            }
        }

        $this->requestApply();
    }

    /** Полностью удаляет каталог сайта вместе с файлами клиента. */
    public function removeSiteFiles(array $user, array $site): void
    {
        $dir = $this->siteDir($user, (string) $site['domain']);
        $home = realpath($this->homeDir($user));
        $real = realpath($dir);

        if ($real !== false && $home !== false && str_starts_with($real, $home . '/')) {
            self::removeTree($real);
        }

        $this->requestApply();
    }

    public static function removeTree(string $path): void
    {
        if (is_link($path) || is_file($path)) {
            @unlink($path);
            return;
        }
        if (!is_dir($path)) {
            return;
        }
        foreach ((array) scandir($path) as $entry) {
            if ($entry === '.' || $entry === '..') {
                continue;
            }
            self::removeTree($path . '/' . $entry);
        }
        @rmdir($path);
    }

    /** Ставит флаг «конфиги изменились». Снимает его hosting-apply. */
    public function requestApply(): void
    {
        $this->db->setState(self::STATE_NEEDS_APPLY, '1');
    }

    public function needsApply(): bool
    {
        return $this->db->getState(self::STATE_NEEDS_APPLY, '0') === '1';
    }

    /**
     * Пересобирает конфиги всех сайтов и пулов php-fpm.
     * Возвращает список записанных файлов.
     *
     * @return array{nginx:list<string>,fpm:list<string>,removed:list<string>}
     */
    public function renderAll(): array
    {
        $nginxDir = $this->config->str('nginx_conf_dir');
        $fpmDir = $this->config->str('fpm_pool_dir');

        foreach ([$nginxDir, $fpmDir] as $dir) {
            if (!is_dir($dir) && !@mkdir($dir, 0o755, true) && !is_dir($dir)) {
                throw new \RuntimeException('Не удалось создать каталог конфигов: ' . $dir);
            }
        }

        $usersById = [];
        foreach ($this->users->all() as $user) {
            $usersById[(int) $user['id']] = $user;
        }

        $written = ['nginx' => [], 'fpm' => [], 'removed' => []];
        $expectedNginx = [];
        $expectedFpm = [];

        foreach ($this->sites->all() as $site) {
            $user = $usersById[(int) $site['user_id']] ?? null;
            if ($user === null || !$user['is_active'] || !$site['is_active']) {
                continue;
            }

            $path = $nginxDir . '/' . $site['domain'] . '.conf';
            $this->writeFile($path, $this->renderSiteConf($user, $site));
            $expectedNginx[basename($path)] = true;
            $written['nginx'][] = $path;
        }

        foreach ($usersById as $user) {
            if (!$user['is_active'] || $this->sites->countForUser((int) $user['id']) === 0) {
                continue;
            }
            $path = $fpmDir . '/' . $user['system_user'] . '.conf';
            $this->writeFile($path, $this->renderPoolConf($user));
            $expectedFpm[basename($path)] = true;
            $written['fpm'][] = $path;
        }

        // Конфиги удалённых/выключенных сайтов убираем, чужие файлы не трогаем.
        $written['removed'] = array_merge(
            $this->pruneStale($nginxDir, $expectedNginx),
            $this->pruneStale($fpmDir, $expectedFpm),
        );

        return $written;
    }

    /** @param array<string,true> $expected */
    private function pruneStale(string $dir, array $expected): array
    {
        $removed = [];
        foreach ((array) glob($dir . '/*.conf') as $file) {
            $name = basename((string) $file);
            if (!isset($expected[$name])) {
                @unlink((string) $file);
                $removed[] = (string) $file;
            }
        }
        return $removed;
    }

    public function renderSiteConf(array $user, array $site): string
    {
        return $this->render('nginx-site.conf.tpl', [
            'PANEL_NAME'     => $this->config->str('panel_name'),
            'DOMAIN'         => (string) $site['domain'],
            'SYSTEM_USER'    => (string) $user['system_user'],
            'PHP_VERSION'    => (string) $site['php_version'],
            'DOC_ROOT'       => $this->docRoot($user, $site),
            'LOG_DIR'        => $this->logDir($user, $site),
            'FPM_UPSTREAM'   => 'unix:' . $this->fpmListen($user),
            'UPLOAD_MAX_MB'  => (string) $this->config->int('upload_max_mb'),
        ]);
    }

    public function renderPoolConf(array $user): string
    {
        return $this->render('php-fpm-pool.conf.tpl', [
            'PANEL_NAME'    => $this->config->str('panel_name'),
            'SYSTEM_USER'   => (string) $user['system_user'],
            'EMAIL'         => (string) $user['email'],
            'LISTEN'        => $this->fpmListen($user),
            'WEB_USER'      => 'www-data',
            'HOME'          => $this->homeDir($user),
            'UPLOAD_MAX_MB' => (string) $this->config->int('upload_max_mb'),
        ]);
    }

    /** @param array<string,string> $vars */
    private function render(string $template, array $vars): string
    {
        $path = $this->templateDir . '/' . $template;
        $contents = @file_get_contents($path);
        if ($contents === false) {
            throw new \RuntimeException('Шаблон не найден: ' . $path);
        }

        foreach ($vars as $key => $value) {
            $contents = str_replace('{{' . $key . '}}', $value, $contents);
        }

        return $contents;
    }

    private function writeFile(string $path, string $contents): void
    {
        $tmp = $path . '.tmp';
        if (@file_put_contents($tmp, $contents) === false) {
            throw new \RuntimeException('Не удалось записать конфиг: ' . $path);
        }
        if (!@rename($tmp, $path)) {
            @unlink($tmp);
            throw new \RuntimeException('Не удалось обновить конфиг: ' . $path);
        }
    }

    /**
     * Просит систему применить конфиги (перезагрузить nginx и php-fpm).
     *
     * @return array{code:int,out:string,err:string}
     */
    public function apply(): array
    {
        $command = trim($this->config->str('apply_command'));
        if ($command === '') {
            return ['code' => 0, 'out' => 'Применение отключено', 'err' => ''];
        }
        return Shell::run($command);
    }
}
