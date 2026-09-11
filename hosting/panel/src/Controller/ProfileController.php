<?php
declare(strict_types=1);

namespace Hosting\Controller;

use Hosting\Config;
use Hosting\Database;
use Hosting\Http\Request;
use Hosting\Http\Response;
use Hosting\Http\UnauthorizedException;
use Hosting\Model\UserRepository;
use Hosting\Service\Auth;
use Hosting\Service\Billing;
use Hosting\Support\Flash;
use Hosting\Support\View;

/** Профиль клиента: имя, смена пароля входа, сводка по тарифу. */
final class ProfileController
{
    public function __construct(
        private Config $config,
        private Database $db,
        private Auth $auth,
        private UserRepository $users,
        private Billing $billing,
        private View $view,
    ) {
    }

    public function index(Request $request): Response
    {
        $user = $this->requireUser();

        return Response::html($this->view->page('profile/index', [
            'csrf'    => $this->auth->csrfToken(),
            'user'    => $user,
            'summary' => $this->billing->summary($user),
        ]));
    }

    public function save(Request $request): Response
    {
        $user = $this->requireUser();
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела');
            return Response::redirect('/profile');
        }

        $name = trim($request->input('display_name'));
        if (mb_strlen($name) > 60) {
            Flash::add('error', 'Имя слишком длинное');
            return Response::redirect('/profile');
        }
        $this->db->pdo()->prepare('UPDATE users SET display_name = ? WHERE id = ?')
            ->execute([$name, $user['id']]);

        $new = $request->raw('password');
        if ($new !== '') {
            if (mb_strlen($new) < 8) {
                Flash::add('error', 'Пароль должен быть не короче 8 символов');
                return Response::redirect('/profile');
            }
            // Пароль входа хранится хешем и никогда не показывается обратно —
            // в отличие от пароля базы, который клиенту нужно видеть.
            $this->db->pdo()->prepare('UPDATE users SET password_hash = ? WHERE id = ?')
                ->execute([password_hash($new, PASSWORD_DEFAULT), $user['id']]);
            $this->db->log((int) $user['id'], 'profile.password_changed', 'user', (int) $user['id']);
        }

        Flash::add('success', 'Сохранено');
        return Response::redirect('/profile');
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
