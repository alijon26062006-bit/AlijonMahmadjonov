<?php
declare(strict_types=1);

namespace Hosting\Controller;

use Hosting\Config;
use Hosting\Database;
use Hosting\Http\Request;
use Hosting\Http\Response;
use Hosting\Http\UnauthorizedException;
use Hosting\Model\DatabaseRepository;
use Hosting\Model\DatabaseUserRepository;
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
        private DatabaseUserRepository $databaseUsers,
        private JobRepository $jobs,
        private View $view,
    ) {
    }

    public function index(Request $request): Response
    {
        $user = $this->requireUser();
        $this->auth->ensureSession();

        // Пароль показываем ровно один раз — сразу после создания базы или смены
        // пароля. Он нигде не хранится: ни в базе панели, ни в логах, ни в сессии
        // дольше одного показа.
        $freshPassword = $_SESSION['db_password_once'] ?? null;
        unset($_SESSION['db_password_once']);

        $dbUser = $this->databaseUsers->findForUser((int) $user['id']);

        return Response::html($this->view->page('databases/index', [
            'csrf'          => $this->auth->csrfToken(),
            'databases'     => $this->databases->forUser((int) $user['id']),
            'user'          => $user,
            'rootDomain'    => $this->config->str('root_domain'),
            'dbUser'        => $dbUser['db_user'] ?? $user['system_user'],
            'freshPassword' => is_string($freshPassword) ? $freshPassword : null,
            // Сохранённый пароль показываем по кнопке «глаз»: без этого клиент,
            // однажды закрывший страницу, не мог узнать его иначе как сменой,
            // а смена ломает все уже настроенные сайты.
            'storedPassword' => $this->databaseUsers->revealPassword((int) $user['id'], $this->config->str('app_key')),
        ]));
    }

    /** «Сменить пароль базы»: показанный один раз пароль иначе не вернуть. */
    public function resetPassword(Request $request): Response
    {
        $user = $this->requireUser();
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела');
            return Response::redirect('/databases');
        }

        $job = $this->jobs->enqueue('reset_db_password', (int) $user['id'], null, []);
        $secret = $this->waitForSecret((int) $job['id']);

        $this->auth->ensureSession();
        if ($secret !== null) {
            $_SESSION['db_password_once'] = $secret;
            Flash::add('success', 'Пароль изменён. Старый больше не работает — обновите его в настройках сайтов.');
        } else {
            Flash::add('error', 'Не удалось сменить пароль, попробуйте ещё раз через минуту');
        }

        return Response::redirect('/databases');
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

        // Пароль не кладём во flash: там он схлопывается в одну строку без
        // переносов, его неудобно выделить и легко потерять. Показываем
        // отдельным блоком на странице — один раз.
        $this->auth->ensureSession();
        if ($secret !== null) {
            $_SESSION['db_password_once'] = $secret;
            Flash::add('success', "База {$fullName} создана");
        } else {
            Flash::add('success', "База {$fullName} создана. Логин и пароль — те же, что у прошлой базы: учётная запись MariaDB у вас одна на все базы.");
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
