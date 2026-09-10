<?php

declare(strict_types=1);

/**
 * Единая точка входа панели. Документ-рут vhost'а панели должен указывать сюда
 * (см. templates/nginx-panel.conf.tpl — генерируется install.sh на HOSTING_ROOT_DOMAIN
 * и panel.HOSTING_ROOT_DOMAIN). Собирает контейнер зависимостей руками — PHP дешёвый,
 * отдельный DI-контейнер для одного маленького приложения был бы лишней сложностью.
 */

$root = dirname(__DIR__, 3); // panel/public -> hosting -> repo root
require $root . '/hosting/autoload.php';

use Hosting\Config;
use Hosting\Controller\AdminController;
use Hosting\Controller\AuthController;
use Hosting\Controller\BackupController;
use Hosting\Controller\DashboardController;
use Hosting\Controller\DatabaseController;
use Hosting\Controller\DomainController;
use Hosting\Controller\FileController;
use Hosting\Controller\LogController;
use Hosting\Controller\SiteController;
use Hosting\Database;
use Hosting\Http\ForbiddenException;
use Hosting\Http\HttpException;
use Hosting\Http\NotFoundException;
use Hosting\Http\Request;
use Hosting\Http\Response;
use Hosting\Http\Router;
use Hosting\Http\UnauthorizedException;
use Hosting\Model\BackupRepository;
use Hosting\Model\DatabaseRepository as DatabaseModelRepository;
use Hosting\Model\DomainRepository;
use Hosting\Model\JobRepository;
use Hosting\Model\LoginAttemptRepository;
use Hosting\Model\NotificationRepository;
use Hosting\Model\PlanRepository;
use Hosting\Model\SessionRepository;
use Hosting\Model\SiteRepository;
use Hosting\Model\TelegramAccountRepository;
use Hosting\Model\UserRepository;
use Hosting\Service\Auth;
use Hosting\Service\TelegramAuth;
use Hosting\Support\Env;
use Hosting\Support\Flash;
use Hosting\Support\View;

Env::load($root . '/.env');

$config = Config::fromEnv();
$isHttps = ($_SERVER['HTTPS'] ?? '') !== '' || ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https';

// ── защитные заголовки на каждый ответ ──────────────────────────────────────
// frame-ancestors разрешает встраивание в Telegram (Mini App открывается в их WebView/iframe),
// но не в произвольный сторонний сайт — только web.telegram.org и сам себя.
header("Content-Security-Policy: default-src 'self'; script-src 'self' https://telegram.org; "
    . "style-src 'self' 'unsafe-inline'; img-src 'self' data: https://t.me https://*.telegram.org; "
    // frame-src нужен кнопке «Войти через Telegram»: виджет открывает окно
    // авторизации в iframe с oauth.telegram.org.
    . "frame-src https://oauth.telegram.org https://*.telegram.org; "
    . "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org;");
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: strict-origin-when-cross-origin');
if ($isHttps) {
    header('Strict-Transport-Security: max-age=31536000; includeSubDomains');
}

try {
    $db = new Database($config);
} catch (\Throwable $e) {
    http_response_code(500);
    echo 'Панель временно недоступна (нет соединения с базой данных панели).';
    exit;
}

// ── репозитории ──────────────────────────────────────────────────────────
$plans = new PlanRepository($db);
$users = new UserRepository($db, $plans);
$sessions = new SessionRepository($db, $config->int('session_ttl'));
$loginAttempts = new LoginAttemptRepository($db);
$telegramAccounts = new TelegramAccountRepository($db);
$sites = new SiteRepository($db);
$domains = new DomainRepository($db);
$databases = new DatabaseModelRepository($db);
$jobs = new JobRepository($db);
$backups = new BackupRepository($db);
$notifications = new NotificationRepository($db);

$auth = new Auth($config, $sessions, $users, $loginAttempts, $isHttps);
$telegramAuth = new TelegramAuth($config->str('telegram_bot_token'));
$view = new View($root . '/hosting/panel/views', static function () use ($auth, $config): array {
    return [
        'currentUser' => $auth->user(),
        'flashes'     => Flash::pull(),
        'panelName'   => $config->str('panel_name'),
    ];
});

// ── контроллеры ──────────────────────────────────────────────────────────
$authController = new AuthController($config, $db, $auth, $users, $plans, $telegramAccounts, $telegramAuth, $jobs, $view);
$dashboardController = new DashboardController($config, $auth, $sites, $databases, $plans, $jobs, $backups, $notifications, $view);
$siteController = new SiteController($config, $db, $auth, $sites, $plans, $jobs, $view);
$fileController = new FileController($config, $db, $auth, $sites, $view);
$logController = new LogController($config, $auth, $sites, $view);
$databaseController = new DatabaseController($config, $db, $auth, $databases, $jobs, $view);
$domainController = new DomainController($config, $db, $auth, $sites, $domains, $jobs, $view);
$adminController = new AdminController($db, $auth, $users, $sites, $jobs, $view);
$backupController = new BackupController($db, $auth, $backups, $jobs, $view);

// ── маршруты ─────────────────────────────────────────────────────────────
$router = new Router();

$router->get('/', [$authController, 'landing']);

// Публичный health-check — без аутентификации и без секретов в ответе (см. спецификацию
// HEALTH CHECKS: "Никаких секретов в public health endpoint"). Используется внешним
// мониторингом/балансировщиком. Раздельные проверки nginx/php-fpm/MariaDB как сервисов
// делает scripts/monitor.sh (systemctl-уровень); этот endpoint проверяет то, что видно
// изнутри самого PHP-процесса — соединение с панельной БД и очередь воркера.
$router->get('/health', function () use ($db, $jobs, $config): Response {
    $checks = ['db' => false, 'queue_backlog_ok' => false];
    $httpStatus = 503;

    try {
        $db->pdo()->query('SELECT 1');
        $checks['db'] = true;

        $pending = $jobs->countPending();
        $checks['queue_backlog_ok'] = $pending < 200;
        $checks['queue_pending'] = $pending;

        $httpStatus = ($checks['db'] && $checks['queue_backlog_ok']) ? 200 : 503;
    } catch (\Throwable) {
        // Ничего из исключения наружу не отдаём — только факт, что БД недоступна.
    }

    return Response::json(['status' => $httpStatus === 200 ? 'ok' : 'degraded', 'checks' => $checks], $httpStatus);
});

$router->get('/login', [$authController, 'showLogin']);
$router->post('/login', [$authController, 'login']);
$router->get('/register', [$authController, 'showRegister']);
$router->post('/register', [$authController, 'register']);
$router->get('/logout', [$authController, 'logout']);
$router->post('/logout', [$authController, 'logout']);
$router->get('/telegram', [$authController, 'showTelegram']);
$router->post('/telegram/callback', [$authController, 'telegramCallback']);
$router->get('/telegram/widget', [$authController, 'telegramWidget']);

$router->get('/dashboard', [$dashboardController, 'index']);

$router->get('/sites', [$siteController, 'index']);
$router->post('/sites', [$siteController, 'create']);
$router->post('/sites/{id}/delete', [$siteController, 'delete']);
$router->post('/sites/{id}/suspend', [$siteController, 'suspend']);
$router->post('/sites/{id}/unsuspend', [$siteController, 'unsuspend']);

$router->get('/sites/{id}/files', [$fileController, 'browse']);
$router->post('/sites/{id}/files/upload', [$fileController, 'upload']);
$router->post('/sites/{id}/files/mkdir', [$fileController, 'mkdir']);
$router->post('/sites/{id}/files/newfile', [$fileController, 'newFile']);
$router->post('/sites/{id}/files/delete', [$fileController, 'delete']);
$router->post('/sites/{id}/files/rename', [$fileController, 'rename']);
$router->get('/sites/{id}/files/edit', [$fileController, 'edit']);
$router->post('/sites/{id}/files/save', [$fileController, 'save']);

$router->get('/sites/{id}/logs', [$logController, 'show']);

$router->get('/sites/{id}/domains', [$domainController, 'index']);
$router->post('/sites/{id}/domains', [$domainController, 'create']);
$router->post('/sites/{id}/domains/{id2}/verify', [$domainController, 'verify']);
$router->post('/sites/{id}/domains/{id2}/ssl', [$domainController, 'issueSsl']);
$router->post('/sites/{id}/domains/{id2}/delete', [$domainController, 'delete']);

$router->get('/databases', [$databaseController, 'index']);
$router->post('/databases', [$databaseController, 'create']);
$router->post('/databases/{id}/delete', [$databaseController, 'delete']);

$router->get('/backups', [$backupController, 'index']);
$router->post('/backups', [$backupController, 'create']);
$router->post('/backups/{id}/restore', [$backupController, 'restore']);

$router->get('/admin', [$adminController, 'index']);
$router->post('/admin/users/{id}/suspend', [$adminController, 'suspendUser']);
$router->post('/admin/users/{id}/activate', [$adminController, 'activateUser']);

// ── диспетчеризация ──────────────────────────────────────────────────────
$request = Request::fromGlobals();
$match = $router->match($request->method, $request->path);

if ($match === null) {
    http_response_code(404);
    echo renderError($view, 404, 'Страница не найдена');
    exit;
}

$params = array_map('intval', $match['params']);

try {
    /** @var Response $response */
    $response = ($match['handler'])($request, ...$params);
} catch (UnauthorizedException) {
    $response = Response::redirect('/login');
} catch (ForbiddenException $e) {
    http_response_code(403);
    echo renderError($view, 403, $e->getMessage());
    exit;
} catch (NotFoundException $e) {
    http_response_code(404);
    echo renderError($view, 404, $e->getMessage());
    exit;
} catch (HttpException $e) {
    http_response_code($e->status());
    echo renderError($view, $e->status(), $e->getMessage());
    exit;
} catch (\Throwable $e) {
    // Ни стектрейс, ни сообщение исключения (может содержать детали SQL/путей) наружу не идут.
    error_log('[panel] ' . $e->getMessage() . ' at ' . $e->getFile() . ':' . $e->getLine());
    http_response_code(500);
    echo renderError($view, 500, 'Внутренняя ошибка. Мы уже знаем о проблеме.');
    exit;
}

$response->send();

/** Рендерит страницу ошибки в общем layout, без утечки деталей исключения. */
function renderError(View $view, int $status, string $message): string
{
    return $view->page('errors/generic', ['status' => $status, 'message' => $message]);
}
