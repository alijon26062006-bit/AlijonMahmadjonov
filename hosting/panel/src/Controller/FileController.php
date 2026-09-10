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
use Hosting\Service\Quota;
use Hosting\Support\Flash;
use Hosting\Support\Path;
use Hosting\Support\View;

/**
 * Файловый менеджер клиента, ограниченный каталогом ОДНОГО сайта (home/sites/{slug}),
 * а не всем домашним каталогом — так чужой (в смысле «другой сайт того же клиента») код
 * не виден из менеджера другого сайта, и это же убирает риск случайно задеть /logs, /tmp клиента.
 */
final class FileController
{
    public function __construct(
        private Config $config,
        private Database $db,
        private Auth $auth,
        private SiteRepository $sites,
        private View $view,
    ) {
    }

    public function browse(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        $fm = $this->fileManagerFor($user, $site);

        $path = Path::normalize($request->input('path', ''));
        try {
            $entries = $fm->listDirectory($path);
        } catch (\RuntimeException $e) {
            Flash::add('error', $e->getMessage());
            $path = '';
            $entries = $fm->listDirectory('');
        }

        return Response::html($this->view->page('files/index', [
            'csrf'        => $this->auth->csrfToken(),
            'site'        => $site,
            'path'        => $path,
            'entries'     => $entries,
            'breadcrumbs' => $fm->breadcrumbs($path),
            'quota'       => Quota::usage($fm->home(), (int) $user['disk_quota_mb']),
        ]));
    }

    public function upload(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела');
            return $this->backToBrowse($siteId, $request);
        }

        $fm = $this->fileManagerFor($user, $site);
        $path = Path::normalize($request->input('path', ''));
        $upload = $_FILES['file'] ?? null;

        if (!is_array($upload)) {
            Flash::add('error', 'Файл не выбран');
            return $this->backToBrowse($siteId, $request, $path);
        }

        $quota = Quota::usage($fm->home(), (int) $user['disk_quota_mb']);
        if ($quota['exceeded']) {
            Flash::add('error', 'Дисковая квота исчерпана — освободите место, чтобы загружать файлы');
            return $this->backToBrowse($siteId, $request, $path);
        }

        try {
            $target = $fm->saveUpload($path, $upload);

            if (str_ends_with(strtolower($target), '.zip') && $request->input('extract') === '1') {
                $remaining = max(0, $quota['limit'] - $quota['used']);
                $relative = ltrim(substr($target, strlen($fm->home())), '/');
                $count = $fm->unzip($relative, $remaining);
                Flash::add('success', "Загружено и распаковано файлов: {$count}");
            } else {
                Flash::add('success', 'Файл загружен');
            }
        } catch (\Throwable $e) {
            Flash::add('error', $e->getMessage());
        }

        return $this->backToBrowse($siteId, $request, $path);
    }

    public function mkdir(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return $this->backToBrowse($siteId, $request);
        }
        $fm = $this->fileManagerFor($user, $site);
        $path = Path::normalize($request->input('path', ''));

        try {
            $fm->makeDirectory($path, $request->input('name'));
            Flash::add('success', 'Папка создана');
        } catch (\Throwable $e) {
            Flash::add('error', $e->getMessage());
        }
        return $this->backToBrowse($siteId, $request, $path);
    }

    public function newFile(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return $this->backToBrowse($siteId, $request);
        }
        $fm = $this->fileManagerFor($user, $site);
        $path = Path::normalize($request->input('path', ''));

        try {
            $fm->createFile($path, $request->input('name'));
            Flash::add('success', 'Файл создан');
        } catch (\Throwable $e) {
            Flash::add('error', $e->getMessage());
        }
        return $this->backToBrowse($siteId, $request, $path);
    }

    public function delete(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return $this->backToBrowse($siteId, $request);
        }
        $fm = $this->fileManagerFor($user, $site);
        $target = $request->input('target');
        $path = Path::normalize(dirname($target) === '.' ? '' : dirname($target));

        try {
            $fm->delete($target);
            Flash::add('success', 'Удалено');
        } catch (\Throwable $e) {
            Flash::add('error', $e->getMessage());
        }
        return $this->backToBrowse($siteId, $request, $path);
    }

    public function rename(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return $this->backToBrowse($siteId, $request);
        }
        $fm = $this->fileManagerFor($user, $site);
        $target = $request->input('target');
        $path = Path::normalize(dirname($target) === '.' ? '' : dirname($target));

        try {
            $fm->rename($target, $request->input('name'));
            Flash::add('success', 'Переименовано');
        } catch (\Throwable $e) {
            Flash::add('error', $e->getMessage());
        }
        return $this->backToBrowse($siteId, $request, $path);
    }

    public function edit(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        $fm = $this->fileManagerFor($user, $site);
        $path = Path::normalize($request->input('path', ''));

        try {
            $contents = $fm->read($path);
        } catch (\RuntimeException $e) {
            Flash::add('error', $e->getMessage());
            return Response::redirect('/sites/' . $siteId . '/files');
        }

        return Response::html($this->view->page('files/edit', [
            'csrf'     => $this->auth->csrfToken(),
            'site'     => $site,
            'path'     => $path,
            'contents' => $contents,
        ]));
    }

    public function save(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела');
            return Response::redirect('/sites/' . $siteId . '/files');
        }
        $fm = $this->fileManagerFor($user, $site);
        $path = Path::normalize($request->input('path', ''));

        try {
            $fm->write($path, $request->raw('contents'));
            Flash::add('success', 'Сохранено');
        } catch (\Throwable $e) {
            Flash::add('error', $e->getMessage());
        }

        return Response::redirect('/sites/' . $siteId . '/files/edit?path=' . rawurlencode($path));
    }

    private function fileManagerFor(array $user, array $site): FileManager
    {
        $home = rtrim($this->config->str('users_root'), '/') . '/' . $user['system_user']
            . '/sites/' . $site['slug'];
        if (!is_dir($home)) {
            throw new NotFoundException('Файлы сайта ещё не созданы — подождите завершения провижининга');
        }
        return new FileManager($home);
    }

    private function backToBrowse(int $siteId, Request $request, string $path = ''): Response
    {
        $qs = $path !== '' ? '?path=' . rawurlencode($path) : '';
        return Response::redirect('/sites/' . $siteId . '/files' . $qs);
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
}
