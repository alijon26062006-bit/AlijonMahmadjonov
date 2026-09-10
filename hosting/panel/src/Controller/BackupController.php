<?php
declare(strict_types=1);

namespace Hosting\Controller;

use Hosting\Database;
use Hosting\Http\Request;
use Hosting\Http\Response;
use Hosting\Http\UnauthorizedException;
use Hosting\Model\BackupRepository;
use Hosting\Model\JobRepository;
use Hosting\Service\Auth;
use Hosting\Support\Flash;
use Hosting\Support\View;

/** Ручное создание и восстановление резервных копий (автоматические идут по расписанию, см. systemd timer). */
final class BackupController
{
    public function __construct(
        private Database $db,
        private Auth $auth,
        private BackupRepository $backups,
        private JobRepository $jobs,
        private View $view,
    ) {
    }

    public function index(Request $request): Response
    {
        $user = $this->requireUser();
        return Response::html($this->view->page('backups/index', [
            'csrf'    => $this->auth->csrfToken(),
            'backups' => $this->backups->forUser((int) $user['id'], 30),
        ]));
    }

    public function create(Request $request): Response
    {
        $user = $this->requireUser();
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела');
            return Response::redirect('/backups');
        }

        $backup = $this->backups->create((int) $user['id'], 'full');
        $this->jobs->enqueue('create_backup', (int) $user['id'], null, ['backup_id' => $backup['id']]);
        $this->db->log((int) $user['id'], 'backup.create_requested', 'backup', (int) $backup['id']);
        Flash::add('success', 'Резервная копия создаётся — обычно занимает от нескольких секунд до пары минут.');
        return Response::redirect('/backups');
    }

    public function restore(Request $request, int $id): Response
    {
        $user = $this->requireUser();
        $backup = $this->backups->findById($id);
        if ($backup === null || (int) $backup['user_id'] !== (int) $user['id']) {
            Flash::add('error', 'Резервная копия не найдена');
            return Response::redirect('/backups');
        }
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела');
            return Response::redirect('/backups');
        }
        if ($backup['status'] !== 'success') {
            Flash::add('error', 'Восстанавливать можно только успешно созданную копию');
            return Response::redirect('/backups');
        }

        $this->jobs->enqueue('restore_backup', (int) $user['id'], null, ['backup_id' => $backup['id']]);
        $this->db->log((int) $user['id'], 'backup.restore_requested', 'backup', (int) $backup['id']);
        Flash::add('success', 'Восстановление запущено. Текущее состояние сайтов будет заменено содержимым этой копии.');
        return Response::redirect('/backups');
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
