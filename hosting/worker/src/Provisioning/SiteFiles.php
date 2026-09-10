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

        // Стартовая страница создаётся ВСЕГДА, а не только если найден каталог
        // заготовки: без index.php свежесозданный сайт отдаёт 404, и человек
        // видит ошибку там, где ожидал увидеть результат.
        if (is_dir($skelDir)) {
            self::copyTree($skelDir, $publicDir);
        }
        $index = $publicDir . '/index.php';
        if (!file_exists($index) && !file_exists($publicDir . '/index.html')) {
            file_put_contents($index, \Hosting\Service\SiteTemplates::defaultIndex());
        }

        // .env сайта — над public/, поэтому из браузера недоступен. Секрет для
        // Telegram-webhook кладём сразу: он нужен ещё до того, как клиент введёт
        // токен, и генерировать его должен сервер, а не человек.
        $envFile = $siteDir . '/.env';
        if (!file_exists($envFile)) {
            file_put_contents($envFile, implode("\n", [
                '# Настройки сайта. Файл лежит НАД public/ и через браузер не открывается.',
                '# Читать его из PHP: см. пример в public/webhook.php.',
                'TELEGRAM_BOT_TOKEN=',
                'TELEGRAM_WEBHOOK_SECRET=' . \Hosting\Service\TelegramWebhook::generateSecret(),
                '',
            ]));
        }

        $this->applyPermissions($siteDir, $systemUser);
    }

    /**
     * Права на каталог сайта.
     *
     * Владелец — клиент (под ним работает его php-fpm), группа — hosting-panel
     * (под ней работает панель). Без общей группы файловый менеджер панели не мог
     * бы ни прочитать, ни изменить ни один файл клиента — а именно это он и должен
     * делать. «Остальные» не получают ничего, поэтому клиенты по-прежнему не видят
     * файлы друг друга.
     *
     * Каталоги 2770 — setgid: всё созданное внутри (и клиентом, и панелью)
     * наследует группу, иначе доступ терялся бы на первом же новом подкаталоге.
     * Файлы 0664: их создаёт то панель (пользователь hosting-panel), то воркер
     * (от имени клиента), а выполняет php-fpm клиента. При 0660 сторона, не
     * попавшая ни во владельца, ни в группу, получает «Permission denied» — и
     * сайт отдаёт 403 на собственный файл. Изоляцию клиентов обеспечивает
     * каталог 2770, а не биты файлов: зайти в чужой каталог посторонний не может.
     */
    public function applyPermissions(string $siteDir, string $systemUser): void
    {
        Shell::run(sprintf(
            'chown -R %s:%s %s',
            escapeshellarg($systemUser),
            escapeshellarg(UnixProvisioner::PANEL_GROUP),
            escapeshellarg($siteDir)
        ), 30);
        Shell::run(sprintf(
            "find %s -type d -exec chmod 2770 {} \; -o -type f -exec chmod 0664 {} \;",
            escapeshellarg($siteDir)
        ), 60);

        // .env лежит вне public/ — из браузера он недоступен, и nginx отдельно
        // запрещает *.env. Читать его должен php-fpm клиента (webhook.php), а
        // писать — панель, поэтому режим тот же 0644, а закрывает файл каталог.
        $env = $siteDir . '/.env';
        if (is_file($env)) {
            Shell::run(sprintf('chmod 0644 %s', escapeshellarg($env)), 10);
        }
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
