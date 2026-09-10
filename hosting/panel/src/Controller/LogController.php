<?php
declare(strict_types=1);

namespace Hosting\Controller;

use Hosting\Config;
use Hosting\Http\ForbiddenException;
use Hosting\Http\NotFoundException;
use Hosting\Http\Request;
use Hosting\Http\Response;
use Hosting\Http\UnauthorizedException;
use Hosting\Model\SiteRepository;
use Hosting\Service\Auth;
use Hosting\Support\View;

/**
 * Клиент видит только access/error лог СВОЕГО сайта — endpoint принимает site_id,
 * путь к файлу сервер строит сам (никаких произвольных /var/log/...). Отдаём
 * последние N строк, а не весь файл, чтобы гигабайтный лог не лёг в память PHP целиком.
 */
final class LogController
{
    private const MAX_LINES = 500;

    public function __construct(
        private Config $config,
        private Auth $auth,
        private SiteRepository $sites,
        private View $view,
    ) {
    }

    public function show(Request $request, int $siteId): Response
    {
        $user = $this->auth->user();
        if ($user === null) {
            throw new UnauthorizedException();
        }
        $site = $this->sites->findById($siteId);
        if ($site === null) {
            throw new NotFoundException('Сайт не найден');
        }
        if ((int) $site['user_id'] !== (int) $user['id'] && $user['role'] !== 'admin') {
            throw new ForbiddenException('Этот сайт вам не принадлежит');
        }

        $logDir = rtrim($this->config->str('users_root'), '/') . '/' . $user['system_user']
            . '/sites/' . $site['slug'] . '/logs';

        $type = $request->input('type', 'error') === 'access' ? 'access' : 'error';
        $lines = self::tail($logDir . '/' . $type . '.log', self::MAX_LINES);

        return Response::html($this->view->page('sites/logs', [
            'site'  => $site,
            'type'  => $type,
            'lines' => $lines,
        ]));
    }

    /** @return list<string> */
    private static function tail(string $path, int $maxLines): array
    {
        if (!is_file($path) || !is_readable($path)) {
            return [];
        }

        $handle = fopen($path, 'r');
        if ($handle === false) {
            return [];
        }

        $buffer = [];
        while (($line = fgets($handle)) !== false) {
            $buffer[] = rtrim($line, "\r\n");
            if (count($buffer) > $maxLines) {
                array_shift($buffer);
            }
        }
        fclose($handle);

        return $buffer;
    }
}
