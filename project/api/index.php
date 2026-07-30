<?php
declare(strict_types=1);

/**
 * REST API front controller.
 *
 * All /api/* requests route here. Endpoints:
 *   GET  /movies         GET  /movie          GET /home
 *   GET  /genres         GET  /search         GET /announcements
 *   GET  /announcement   GET  /banners
 *   GET  /favorites      POST /favorites
 *   GET  /history        POST /history
 *   POST /watch
 *   GET  /profile        POST /profile
 */

use Core\Database;
use Core\Router;
use Core\Response;
use Core\Logger;
use Controllers\MovieController;
use Controllers\AnnouncementController;
use Controllers\GenreController;
use Controllers\SearchController;
use Controllers\FavoriteController;
use Controllers\HistoryController;
use Controllers\WatchController;
use Controllers\ProfileController;
use Models\Banner;

require __DIR__ . '/autoload.php';

$config = require __DIR__ . '/../config/config.php';
$GLOBALS['APP_CONFIG'] = $config;

// ---- Error handling ----
if ($config['app']['debug']) {
    ini_set('display_errors', '1');
    error_reporting(E_ALL);
} else {
    ini_set('display_errors', '0');
}
set_exception_handler(static function (Throwable $e) use ($config): void {
    Logger::error($e->getMessage() . ' @ ' . $e->getFile() . ':' . $e->getLine());
    $msg = $config['app']['debug'] ? $e->getMessage() : 'Internal server error';
    Response::error($msg, 500);
});

// ---- CORS (Telegram WebView) ----
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-Telegram-Init-Data, Authorization');
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'OPTIONS') {
    http_response_code(204);
    exit;
}

Database::connect($config['db']);

// ---- Resolve request path relative to the API base ----
$uri  = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
// Strip everything up to and including "/api"
if (($pos = strpos($uri, '/api')) !== false) {
    $uri = substr($uri, $pos + 4);
}
$uri = '/' . trim($uri, '/');
// Support ?route= fallback for hosts without URL rewriting
if (isset($_GET['route'])) {
    $uri = '/' . trim((string) $_GET['route'], '/');
}
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

// ---- Routes ----
$router = new Router();

$router->get('/home',          fn () => (new MovieController($config))->home());
$router->get('/movies',        fn () => (new MovieController($config))->index());
$router->get('/movie',         fn () => (new MovieController($config))->show());
$router->get('/genres',        fn () => (new GenreController($config))->index());
$router->get('/search',        fn () => (new SearchController($config))->index());
$router->get('/announcements', fn () => (new AnnouncementController($config))->index());
$router->get('/announcement',  fn () => (new AnnouncementController($config))->show());
$router->get('/banners',       fn () => Response::ok((new Banner())->active(8)));

$router->get('/favorites',     fn () => (new FavoriteController($config))->index());
$router->post('/favorites',    fn () => (new FavoriteController($config))->toggle());

$router->get('/history',       fn () => (new HistoryController($config))->index());
$router->post('/history',      fn () => (new HistoryController($config))->store());

$router->post('/watch',        fn () => (new WatchController($config))->store());

$router->get('/profile',       fn () => (new ProfileController($config))->show());
$router->post('/profile',      fn () => (new ProfileController($config))->store());

$router->get('/',              fn () => Response::ok(['name' => $config['app']['name'], 'status' => 'ok']));

$router->dispatch($method, $uri);
