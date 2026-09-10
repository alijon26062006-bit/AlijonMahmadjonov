<?php
declare(strict_types=1);

namespace Hosting\Controller;

use Hosting\Config;
use Hosting\Database;
use Hosting\Http\Request;
use Hosting\Http\Response;
use Hosting\Http\UnauthorizedException;
use Hosting\Model\DatabaseRepository;
use Hosting\Model\JobRepository;
use Hosting\Service\Auth;
use Hosting\Service\MysqlManager;
use Hosting\Support\Flash;
use Hosting\Support\View;

final class DatabaseController
{
    public function __construct(
        private Config $config,
        private Database $db,
        private Auth $auth,
        private DatabaseRepository $databases,
        private JobRepository $jobs,
        private View $view,
    ) {
    }

    public function index(Request $request): Response
    {
        $user = $this->requireUser();
        return Response::html($this->view->page('databases/index', [
            'csrf'       => $this->auth->csrfToken(),
            'databases'  => $this->databases->forUser((int) $user['id']),
            'user'       => $user,
            'rootDomain' => $this->config->str('root_domain'),
        ]));
    }

    public function create(Request $request): Response
    {
        $user = $this->requireUser();
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела');
            return Response::redirect('/databases');
        }

        $name = strtolower(trim($request->input('name')));
        if (!MysqlManager::isValidName($name)) {
            Flash::add('error', 'Имя базы: латиница в нижнем регистре, цифры, подчёркивание, 2–25 символов, начинается с буквы');
            return Response::redirect('/databases');
        }

        if ($this->databases->countActiveForUser((int) $user['id']) >= (int) $user['max_databases']) {
            Flash::add('error', 'Достигнут лимит баз данных по тарифу');
            return Response::redirect('/databases');
        }

        $fullName = MysqlManager::fullDatabaseName($user, $name);
        if ($this->databases->findByName($fullName) !== null) {
            Flash::add('error', 'База с таким именем уже есть');
            return Response::redirect('/databases');
        }

        $database = $this->databases->create((int) $user['id'], null, $fullName);
        $job = $this->jobs->enqueue('create_database', (int) $user['id'], null, ['database_id' => $database['id']]);

        // Создание базы — быстрая операция: недолго ждём воркер синхронно, чтобы сразу
        // показать одноразовый пароль, а не заставлять клиента обновлять страницу руками.
        $secret = $this->waitForSecret((int) $job['id']);

        if ($secret !== null) {
            Flash::add('success', "База {$fullName} создана.\nПользователь: {$user['system_user']}\nХост: localhost или 127.0.0.1 (работают оба)\nПароль (показывается один раз): {$secret}");
        } else {
            Flash::add('success', "База {$fullName} создаётся. Если пароль от пользователя базы вам уже известен по прошлой базе — он не меняется.");
        }

        return Response::redirect('/databases');
    }

    public function delete(Request $request, int $id): Response
    {
        $user = $this->requireUser();
        $database = $this->databases->findById($id);
        if (!DatabaseRepository::belongsToUser($database, (int) $user['id']) && $user['role'] !== 'admin') {
            Flash::add('error', 'База не найдена');
            return Response::redirect('/databases');
        }
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела');
            return Response::redirect('/databases');
        }

        $this->jobs->enqueue('delete_database', (int) $user['id'], null, ['database_id' => $database['id']]);
        $this->db->log((int) $user['id'], 'database.delete_requested', 'database', (int) $database['id']);
        Flash::add('success', 'База удаляется');
        return Response::redirect('/databases');
    }

    private function waitForSecret(int $jobId, int $maxMs = 6000): ?string
    {
        $elapsed = 0;
        $step = 200_000; // 200мс
        while ($elapsed < $maxMs * 1000) {
            $job = $this->jobs->findById($jobId);
            if ($job !== null && $job['status'] === 'success') {
                return $this->jobs->consumeResultSecret($jobId);
            }
            if ($job !== null && $job['status'] === 'failed') {
                return null;
            }
            usleep($step);
            $elapsed += $step;
        }
        return null;
    }

    private function requireUser(): array
    {
        $user = $this->auth->user();
        if ($user === null) {
            throw new UnauthorizedException();
        }
        return $user;
    }
}
