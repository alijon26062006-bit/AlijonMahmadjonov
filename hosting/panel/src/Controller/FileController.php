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
use Hosting\Service\PhpSyntax;
use Hosting\Service\SiteTemplates;
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
    /** Больше этого через панель не скачиваем — такие объёмы это работа для SFTP. */
    private const MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024;

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

        // По умолчанию открываем public/ — именно там лежит то, что видно в
        // браузере. Корень сайта (с .env, storage, logs) остаётся на шаг выше,
        // но начинать с него — значит показывать человеку служебные каталоги
        // вместо его страницы.
        if (!isset($request->query['path']) && is_dir($fm->home() . '/public')) {
            $path = 'public';
        }

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
            'templates'   => SiteTemplates::all(),
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

        // «index» → «index.php»: имя без точки почти всегда означает, что человек
        // просто не дописал расширение, а файл без .php веб-сервер отдаст текстом.
        $name = FileManager::suggestName($request->input('name'));

        try {
            $fm->createFile($path, $name);
            Flash::add('success', 'Файл создан: ' . $name);
            // Сразу открываем редактор — иначе следующий шаг («а где вписать код?»)
            // человеку приходится искать самому.
            $full = $path === '' ? $name : $path . '/' . $name;

            return Response::redirect('/sites/' . $siteId . '/files/edit?path=' . rawurlencode($full));
        } catch (\Throwable $e) {
            Flash::add('error', $e->getMessage());
        }
        return $this->backToBrowse($siteId, $request, $path);
    }

    /** Заготовка сайта или бота одним нажатием (см. Service\SiteTemplates). */
    public function fromTemplate(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return $this->backToBrowse($siteId, $request);
        }

        $template = SiteTemplates::get($request->input('template'));
        if ($template === null) {
            Flash::add('error', 'Неизвестный шаблон');
            return $this->backToBrowse($siteId, $request);
        }

        $fm = $this->fileManagerFor($user, $site);
        $overwrite = $request->input('overwrite') === '1';
        $created = [];
        $first = null;

        try {
            foreach ($template['files'] as $relative => $contents) {
                $fm->createFileDeep($relative, $contents, $overwrite);
                $created[] = $relative;
                $first ??= $relative;
            }
        } catch (\Throwable $e) {
            Flash::add('error', $e->getMessage() . ' — отметьте «перезаписать», если хотите заменить.');
            return $this->backToBrowse($siteId, $request, 'public');
        }

        Flash::add('success', 'Создано: ' . implode(', ', $created));

        return $first !== null
            ? Response::redirect('/sites/' . $siteId . '/files/edit?path=' . rawurlencode($first))
            : $this->backToBrowse($siteId, $request, 'public');
    }

    /** Распаковка уже загруженного архива (кнопка «Распаковать» в списке файлов). */
    public function extract(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            return $this->backToBrowse($siteId, $request);
        }

        $fm = $this->fileManagerFor($user, $site);
        $target = $request->input('target');
        $path = Path::normalize(dirname($target) === '.' ? '' : dirname($target));
        $quota = Quota::usage($fm->home(), (int) $user['disk_quota_mb']);

        try {
            $count = $fm->unzip($target, max(0, $quota['limit'] - $quota['used']));
            Flash::add('success', "Распаковано файлов: {$count}");
        } catch (\Throwable $e) {
            Flash::add('error', $e->getMessage());
        }

        return $this->backToBrowse($siteId, $request, $path);
    }

    /**
     * Скачивание файла.
     *
     * .env отдаём только с явным подтверждением: в нём лежат токен бота и секрет
     * webhook, и случайно утянуть его в «Загрузки» вместе с остальными файлами
     * не должно быть возможно.
     */
    public function download(Request $request, int $siteId): Response
    {
        $user = $this->requireUser();
        $site = $this->ownedSite($user, $siteId);
        $fm = $this->fileManagerFor($user, $site);
        $path = Path::normalize($request->input('path', ''));
        $name = basename($path);

        if (str_starts_with($name, '.env') && $request->input('confirm') !== 'yes') {
            Flash::add('error', 'В .env лежат секреты. Скачивание требует подтверждения — нажмите «Скачать .env» ещё раз.');
            return $this->backToBrowse($siteId, $request, Path::normalize(dirname($path)));
        }

        try {
            $absolute = $fm->fileForDownload($path);
        } catch (\Throwable $e) {
            Flash::add('error', $e->getMessage());
            return $this->backToBrowse($siteId, $request);
        }

        if (filesize($absolute) > self::MAX_DOWNLOAD_BYTES) {
            Flash::add('error', 'Файл слишком большой для скачивания через панель (больше 64 МБ) — используйте SFTP');
            return $this->backToBrowse($siteId, $request, Path::normalize(dirname($path)));
        }

        $this->db->log((int) $user['id'], 'file.downloaded', 'site', (int) $site['id'], 'success', ['path' => $path]);

        return Response::download((string) file_get_contents($absolute), $name);
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
            'syntax'   => null,
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

        $contents = $request->raw('contents');

        // Перед записью PHP-файла проверяем синтаксис. Сохранение с ошибкой
        // разбора — это белый экран на живом сайте, поэтому по умолчанию оно не
        // применяется; клиент видит строку и текст ошибки и решает сам.
        if (str_ends_with(strtolower($path), '.php')) {
            $check = PhpSyntax::check($contents);
            if (!$check['ok'] && $request->input('force') !== '1') {
                Flash::add('error', PhpSyntax::describe($check) . ' — файл НЕ сохранён.');

                return Response::html($this->view->page('files/edit', [
                    'csrf'      => $this->auth->csrfToken(),
                    'site'      => $site,
                    'path'      => $path,
                    'contents'  => $contents,
                    'syntax'    => $check,
                ]));
            }
        }

        try {
            $fm->write($path, $contents);
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
