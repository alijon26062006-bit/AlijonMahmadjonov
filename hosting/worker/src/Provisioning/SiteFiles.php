<?php
declare(strict_types=1);

namespace Hosting\Worker\Provisioning;

use Hosting\Support\Path;
use Hosting\Support\Shell;

/**
 * Каталоги сайта на диске и права на них. Никогда chmod 777 — владелец всегда
 * сам клиент, каталоги 0750, файлы 0640 (см. spec «ПРАВА ФАЙЛОВ»).
 */
final class SiteFiles
{
    public function siteDir(string $home, string $slug): string
    {
        return $home . '/sites/' . $slug;
    }

    public function docRoot(string $home, string $slug, string $docRoot): string
    {
        return $this->siteDir($home, $slug) . '/' . $docRoot;
    }

    public function logDir(string $home, string $slug): string
    {
        return $this->siteDir($home, $slug) . '/logs';
    }

    public function create(string $home, string $slug, string $docRoot, string $systemUser, string $skelDir): void
    {
        $siteDir = $this->siteDir($home, $slug);
        $publicDir = $this->docRoot($home, $slug, $docRoot);
        $storageDir = $siteDir . '/storage';
        $logDir = $this->logDir($home, $slug);

        foreach ([$siteDir, $publicDir, $storageDir, $logDir] as $dir) {
            if (!is_dir($dir) && !@mkdir($dir, 0o750, true) && !is_dir($dir)) {
                throw new \RuntimeException('Не удалось создать каталог: ' . $dir);
            }
        }

        if (is_dir($skelDir)) {
            self::copyTree($skelDir, $publicDir);
        }

        $this->applyPermissions($siteDir, $systemUser);
    }

    public function applyPermissions(string $siteDir, string $systemUser): void
    {
        Shell::run(sprintf('chown -R %1$s:%1$s %2$s', escapeshellarg($systemUser), escapeshellarg($siteDir)), 30);
        Shell::run(sprintf(
            "find %s -type d -exec chmod 0750 {} \; -o -type f -exec chmod 0640 {} \;",
            escapeshellarg($siteDir)
        ), 60);
    }

    public function remove(string $home, string $slug): void
    {
        $siteDir = $this->siteDir($home, $slug);
        $homeReal = realpath($home);
        $siteReal = realpath($siteDir);

        // Двухэтапная защита от «rm -rf с пользовательским путём»: путь строится только
        // из доверенных значений (home из БД по id, slug — уже провалидированный), и мы
        // ещё раз проверяем, что итоговый realpath остался строго внутри дома клиента.
        if ($siteReal === false || $homeReal === false || !str_starts_with($siteReal, $homeReal . '/')) {
            throw new \RuntimeException('Отказ: путь удаления вне домашнего каталога клиента');
        }

        Path::removeTree($siteReal);
    }

    private static function copyTree(string $from, string $to): void
    {
        foreach ((array) scandir($from) as $entry) {
            if ($entry === '.' || $entry === '..') {
                continue;
            }
            $src = $from . '/' . $entry;
            $dst = $to . '/' . $entry;
            if (is_dir($src)) {
                if (!is_dir($dst)) {
                    mkdir($dst, 0o750, true);
                }
                self::copyTree($src, $dst);
            } elseif (!file_exists($dst)) {
                copy($src, $dst);
            }
        }
    }

}
