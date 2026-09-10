<?php
declare(strict_types=1);

namespace Hosting\Controller;

use Hosting\Config;
use Hosting\Database;
use Hosting\Http\Request;
use Hosting\Http\Response;
use Hosting\Model\JobRepository;
use Hosting\Model\PlanRepository;
use Hosting\Model\TelegramAccountRepository;
use Hosting\Model\UserRepository;
use Hosting\Service\Auth;
use Hosting\Service\TelegramAuth;
use Hosting\Support\Flash;
use Hosting\Support\View;

final class AuthController
{
    public function __construct(
        private Config $config,
        private Database $db,
        private Auth $auth,
        private UserRepository $users,
        private PlanRepository $plans,
        private TelegramAccountRepository $telegramAccounts,
        private TelegramAuth $telegramAuth,
        private JobRepository $jobs,
        private View $view,
    ) {
    }

    public function showLogin(Request $request): Response
    {
        if ($this->auth->user() !== null) {
            return Response::redirect('/dashboard');
        }
        return Response::html($this->view->page('auth/login', ['csrf' => $this->auth->csrfToken()]));
    }

    public function login(Request $request): Response
    {
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела, попробуйте ещё раз');
            return Response::redirect('/login');
        }

        $email = strtolower($request->input('email'));
        $password = $request->raw('password');
        $ip = (string) ($request->server['REMOTE_ADDR'] ?? '');

        if ($this->auth->isLoginRateLimited($email, $ip)) {
            $this->db->recordSecurityEvent('login_rate_limited', 'warning', $ip, ['identifier' => $email]);
            Flash::add('error', 'Слишком много неудачных попыток входа. Попробуйте позже.');
            return Response::redirect('/login');
        }

        $user = $this->users->findByEmail($email);
        $ok = $user !== null && $this->users->verifyPassword($user, $password) && UserRepository::isActive($user);

        $this->auth->recordLoginAttempt($email, $ip, $ok);

        if (!$ok) {
            // Формат строки специально фиксированный — его матчит fail2ban jail
            // hosting-panel-login (см. etc/fail2ban/filter.d/hosting-panel-login.conf).
            error_log("[hosting-auth] failed login ip={$ip} identifier={$email}");
            Flash::add('error', 'Неверный e-mail или пароль');
            return Response::redirect('/login');
        }

        $this->auth->login($user, $ip, (string) $request->header('user-agent'));
        $this->db->log((int) $user['id'], 'auth.login', 'user', (int) $user['id'], 'success', [], $ip);
        return Response::redirect('/dashboard');
    }

    public function showRegister(Request $request): Response
    {
        if (!$this->config->bool('registration')) {
            Flash::add('error', 'Регистрация временно закрыта');
            return Response::redirect('/login');
        }
        if ($this->auth->user() !== null) {
            return Response::redirect('/dashboard');
        }
        return Response::html($this->view->page('auth/register', [
            'csrf'  => $this->auth->csrfToken(),
            'plans' => $this->plans->all(),
        ]));
    }

    public function register(Request $request): Response
    {
        if (!$this->config->bool('registration')) {
            Flash::add('error', 'Регистрация временно закрыта');
            return Response::redirect('/login');
        }
        if (!$this->auth->verifyCsrf($request->input('csrf'))) {
            Flash::add('error', 'Форма устарела, попробуйте ещё раз');
            return Response::redirect('/register');
        }

        $email = $request->input('email');
        $password = $request->raw('password');
        $planCode = $request->input('plan', $this->config->str('default_plan'));
        $ip = (string) ($request->server['REMOTE_ADDR'] ?? '');

        if (!$this->plans->exists($planCode)) {
            $planCode = $this->config->str('default_plan');
        }

        try {
            $user = $this->users->create($email, $password, $planCode);
        } catch (\InvalidArgumentException|\RuntimeException $e) {
            Flash::add('error', $e->getMessage());
            return Response::redirect('/register');
        }

        // unix-пользователь и домашний каталог создаются асинхронно root-воркером
        $this->jobs->enqueue('create_user', (int) $user['id'], null);

        $this->db->log((int) $user['id'], 'auth.register', 'user', (int) $user['id'], 'success', [], $ip);
        $this->auth->login($user, $ip, (string) $request->header('user-agent'));
        Flash::add('success', 'Добро пожаловать! Аккаунт создаётся, это займёт несколько секунд.');
        return Response::redirect('/dashboard');
    }

    public function logout(Request $request): Response
    {
        $user = $this->auth->user();
        if ($user !== null) {
            $this->db->log((int) $user['id'], 'auth.logout', 'user', (int) $user['id']);
        }
        $this->auth->logout();
        return Response::redirect('/login');
    }

    public function showTelegram(Request $request): Response
    {
        return Response::html($this->view->page('auth/telegram', []));
    }

    public function telegramCallback(Request $request): Response
    {
        $initData = $request->raw('init_data');
        $ip = (string) ($request->server['REMOTE_ADDR'] ?? '');

        if (!$this->telegramAuth->isConfigured()) {
            Flash::add('error', 'Вход через Telegram не настроен на этом сервере');
            return Response::redirect('/login');
        }

        try {
            $verified = $this->telegramAuth->verify($initData);
        } catch (\RuntimeException $e) {
            $this->db->recordSecurityEvent('telegram_auth_failed', 'warning', $ip, ['error' => $e->getMessage()]);
            Flash::add('error', 'Не удалось подтвердить вход через Telegram: ' . $e->getMessage());
            return Response::redirect('/telegram');
        }

        $tgUser = $verified['user'];
        $telegramId = (int) $tgUser['id'];
        $account = $this->telegramAccounts->findByTelegramId($telegramId);

        if ($account !== null) {
            $user = $this->users->findById((int) $account['user_id']);
            if ($user === null || !\Hosting\Model\UserRepository::isActive($user)) {
                Flash::add('error', 'Аккаунт заблокирован');
                return Response::redirect('/telegram');
            }
        } else {
            $planCode = $request->input('plan', $this->config->str('default_plan'));
            if (!$this->plans->exists($planCode)) {
                $planCode = $this->config->str('default_plan');
            }
            $user = $this->users->createFromTelegram($tgUser, $planCode);
            $this->telegramAccounts->link((int) $user['id'], $tgUser);
            $this->jobs->enqueue('create_user', (int) $user['id'], null);
            $this->db->log((int) $user['id'], 'auth.register_telegram', 'user', (int) $user['id'], 'success', [], $ip);
        }

        $this->auth->login($user, $ip, (string) $request->header('user-agent'));
        $this->db->log((int) $user['id'], 'auth.login_telegram', 'user', (int) $user['id'], 'success', [], $ip);
        return Response::redirect('/dashboard');
    }
}
