<?php
declare(strict_types=1);
/**
 * CodeTJ — платформаи омӯзиши HTML, CSS ва JavaScript бо забони тоҷикӣ.
 * index.php — тамоми фронтенд ва логика. Роутинг: ?p=...
 * Қисми 1: каркас, бақайдгирӣ/воруд, 4 курс, харитаи дарсҳо, ду забон.
 */

require __DIR__ . '/db.php';
codetj_session_start();

/* ============================================================
 *  ЗАБОНҲО — ҳамаи навиштаҷоти интерфейс дар як ҷо.
 *  Забони сеюм = боз як массив дар ҳамин ҷо.
 * ============================================================ */
$LANG = [
'tj' => [
    'site_name'      => 'CodeTJ',
    'tagline'        => 'Барномасозиро бо забони тоҷикӣ омӯз',
    'hero_text'      => 'HTML, CSS ва JavaScript — бо забони модарӣ, бо мисолҳои зинда. Кодро дар браузер менависӣ, коратро зеҳни сунъӣ месанҷад.',
    'start_free'     => 'Оғоз кун — ройгон',
    'have_account'   => 'Аллакай ҳисоб дорӣ? Ворид шав',
    'nav_home'       => 'Асосӣ',
    'nav_courses'    => 'Курсҳо',
    'nav_rating'     => 'Рейтинг',
    'nav_profile'    => 'Профил',
    'nav_admin'      => 'Админка',
    'login'          => 'Воридшавӣ',
    'register'       => 'Бақайдгирӣ',
    'logout'         => 'Баромадан',
    'username'       => 'Логин',
    'password'       => 'Парол',
    'password2'      => 'Парол (такрор)',
    'name'           => 'Ном',
    'city'           => 'Шаҳр ё ноҳия',
    'city_ph'        => 'Масалан: Душанбе, Хуҷанд, Кӯлоб…',
    'login_ph'       => 'ҳарфҳои лотинӣ, рақам, _',
    'do_login'       => 'Ворид шудан',
    'do_register'    => 'Сабти ном кардан',
    'no_account'     => 'Ҳисоб надорӣ? Сабти ном кун',
    'setup_title'    => 'Насбкунии CodeTJ',
    'setup_note'     => 'Ин аввалин воридшавӣ ба сайт аст. Ҳисоби администраторро соз — баъд ҳамаи танзимот дар дасти ту.',
    'create_admin'   => 'Сохтани администратор',
    'welcome'        => 'Хуш омадӣ',
    'points'         => 'балл',
    'streak'         => 'рӯз пай дар пай',
    'day'            => 'рӯз',
    'lessons_word'   => 'дарс',
    'of'             => 'аз',
    'done_word'      => 'супорида шуд',
    'continue'       => 'Давом додан',
    'open_course'    => 'Кушодан',
    'locked'         => 'Пӯшида',
    'full_locked_hint' => 'Ин курс кушода мешавад, вақте ки дар HTML, CSS ва JavaScript ҳар кадомашро на кам аз 60% мегузаронӣ. Ту метавонӣ!',
    'level'          => 'Сатҳ',
    'level_exam'     => 'Имтиҳони сатҳ',
    'exam_hint'      => 'Барои кушодани сатҳи оянда имтиҳонро супор: 15 савол + лоиҳаи амалӣ. Балли гузариш — 70%.',
    'exam_passed'    => 'Имтиҳон супорида шуд',
    'exam_soon'      => 'Имтиҳон дар навсозии оянда фаъол мешавад',
    'level_locked_hint' => 'Ин сатҳ пӯшида аст. Аввал имтиҳони сатҳи пешинаро супор.',
    'lesson'         => 'Дарс',
    'lesson_not_ready' => 'Ин дарс ҳанӯз тайёр мешавад. Ба зудӣ пайдо мешавад!',
    'back'           => 'Бозгашт',
    'theory'         => 'Назария',
    'example'        => 'Намуна',
    'practice'       => 'Амалия',
    'ai_check'       => 'Санҷиши AI',
    'test'           => 'Тест',
    'practice_soon'  => 'Муҳаррири код, санҷиши AI ва тест дар навсозии оянда фаъол мешаванд. Ҳоло назарияро хон ва намунаро омӯз.',
    'my_progress'    => 'Пешрафти ман',
    'top_students'   => 'Беҳтарин шогирдон',
    'no_students'    => 'Ҳанӯз касе нест — аввалин шав!',
    'rank'           => 'Ҷой дар рейтинг',
    'guest'          => 'Меҳмон',
    'courses_title'  => 'Курсҳо',
    'lessons_50'     => '50 дарс',
    'levels_5'       => '5 сатҳ',
    'footer_note'    => 'CodeTJ — барои ҳамаи онҳое, ки мехоҳанд барномасоз шаванд.',
    'theme_toggle'   => 'Мавзӯъ: торик/равшан',
    'err_csrf'       => 'Форма кӯҳна шудааст. Саҳифаро нав кун ва боз кӯшиш кун.',
    'err_rate'       => 'Хеле зуд-зуд кӯшиш кардӣ. Якчанд дақиқа сабр кун.',
    'err_login_taken'=> 'Ин логин банд аст. Дигарашро интихоб кун.',
    'err_login_format' => 'Логин аз 3 то 32 аломат: ҳарфҳои лотинӣ, рақамҳо ва _.',
    'err_name_empty' => 'Номатро нависед.',
    'err_pass_short' => 'Парол на кам аз 6 аломат бошад.',
    'err_pass_mismatch' => 'Паролҳо якхела набаромаданд.',
    'err_wrong_creds'=> 'Логин ё парол нодуруст аст.',
    'err_banned'     => 'Ҳисоби ту баста шудааст. Бо администратор дар тамос шав.',
    'err_reg_off'    => 'Ҳоло бақайдгирии нав пӯшида аст.',
    'err_not_found'  => 'Чунин саҳифа ёфт нашуд.',
    'err_need_login' => 'Барои ин амал аввал ворид шав.',
    'ok_registered'  => 'Табрик! Ҳисобат сохта шуд. Акнун омӯзишро сар кун!',
    'ok_admin_created' => 'Администратор сохта шуд. Хуш омадӣ ба CodeTJ!',
    'lang_tj'        => 'ТҶ',
    'lang_ru'        => 'РУ',
    'home_title'     => 'Курсҳои ту',
    'total_progress' => 'Пешрафти умумӣ',
    'medal_1'        => '🥇',
    'medal_2'        => '🥈',
    'medal_3'        => '🥉',
    'stat_lessons'   => 'дарси тайёр',
    'stat_free'      => 'ройгон',
    'stat_lang'      => 'бо тоҷикӣ',
    'why_title'      => 'Чаро CodeTJ?',
    'why_1_t'        => 'Бо забони худат',
    'why_1_d'        => 'Ҳамаи дарсҳо бо тоҷикии зинда навишта шудаанд — фаҳмо, бе тарҷумаи хушк.',
    'why_2_t'        => 'Код дар браузер',
    'why_2_d'        => 'Ҳеҷ чиз насб кардан лозим нест: менависӣ ва дарҳол натиҷаро мебинӣ.',
    'why_3_t'        => 'Санҷиши AI',
    'why_3_d'        => 'Зеҳни сунъӣ коратро месанҷад, хатоятро мефаҳмонад ва маслиҳат медиҳад.',
    'why_4_t'        => 'Бозӣ барин',
    'why_4_d'        => 'Балл, сатҳ, значок ва рейтинг — омӯзиш мисли бозии шавқовар.',
],
'ru' => [
    'site_name'      => 'CodeTJ',
    'tagline'        => 'Учи программирование на таджикском',
    'hero_text'      => 'HTML, CSS и JavaScript — на родном языке, с живыми примерами. Пишешь код прямо в браузере, а работу проверяет искусственный интеллект.',
    'start_free'     => 'Начать — бесплатно',
    'have_account'   => 'Уже есть аккаунт? Войти',
    'nav_home'       => 'Главная',
    'nav_courses'    => 'Курсы',
    'nav_rating'     => 'Рейтинг',
    'nav_profile'    => 'Профиль',
    'nav_admin'      => 'Админка',
    'login'          => 'Вход',
    'register'       => 'Регистрация',
    'logout'         => 'Выйти',
    'username'       => 'Логин',
    'password'       => 'Пароль',
    'password2'      => 'Пароль (ещё раз)',
    'name'           => 'Имя',
    'city'           => 'Город или район',
    'city_ph'        => 'Например: Душанбе, Худжанд, Куляб…',
    'login_ph'       => 'латинские буквы, цифры, _',
    'do_login'       => 'Войти',
    'do_register'    => 'Зарегистрироваться',
    'no_account'     => 'Нет аккаунта? Зарегистрируйся',
    'setup_title'    => 'Установка CodeTJ',
    'setup_note'     => 'Это первый запуск сайта. Создай аккаунт администратора — дальше все настройки будут в твоих руках.',
    'create_admin'   => 'Создать администратора',
    'welcome'        => 'С возвращением',
    'points'         => 'баллов',
    'streak'         => 'дней подряд',
    'day'            => 'день',
    'lessons_word'   => 'уроков',
    'of'             => 'из',
    'done_word'      => 'пройдено',
    'continue'       => 'Продолжить',
    'open_course'    => 'Открыть',
    'locked'         => 'Закрыто',
    'full_locked_hint' => 'Этот курс откроется, когда в HTML, CSS и JavaScript будет пройдено не меньше 60% уроков. У тебя получится!',
    'level'          => 'Уровень',
    'level_exam'     => 'Экзамен уровня',
    'exam_hint'      => 'Чтобы открыть следующий уровень, сдай экзамен: 15 вопросов + практический проект. Проходной балл — 70%.',
    'exam_passed'    => 'Экзамен сдан',
    'exam_soon'      => 'Экзамен включится в следующем обновлении',
    'level_locked_hint' => 'Этот уровень закрыт. Сначала сдай экзамен предыдущего уровня.',
    'lesson'         => 'Урок',
    'lesson_not_ready' => 'Этот урок ещё готовится. Скоро появится!',
    'back'           => 'Назад',
    'theory'         => 'Теория',
    'example'        => 'Пример',
    'practice'       => 'Практика',
    'ai_check'       => 'Проверка AI',
    'test'           => 'Тест',
    'practice_soon'  => 'Редактор кода, проверка AI и тест включатся в следующем обновлении. А пока читай теорию и разбирай пример.',
    'my_progress'    => 'Мой прогресс',
    'top_students'   => 'Лучшие ученики',
    'no_students'    => 'Пока никого нет — стань первым!',
    'rank'           => 'Место в рейтинге',
    'guest'          => 'Гость',
    'courses_title'  => 'Курсы',
    'lessons_50'     => '50 уроков',
    'levels_5'       => '5 уровней',
    'footer_note'    => 'CodeTJ — для всех, кто хочет стать программистом.',
    'theme_toggle'   => 'Тема: тёмная/светлая',
    'err_csrf'       => 'Форма устарела. Обнови страницу и попробуй ещё раз.',
    'err_rate'       => 'Слишком много попыток. Подожди несколько минут.',
    'err_login_taken'=> 'Этот логин занят. Выбери другой.',
    'err_login_format' => 'Логин от 3 до 32 символов: латинские буквы, цифры и _.',
    'err_name_empty' => 'Напиши своё имя.',
    'err_pass_short' => 'Пароль — минимум 6 символов.',
    'err_pass_mismatch' => 'Пароли не совпали.',
    'err_wrong_creds'=> 'Неверный логин или пароль.',
    'err_banned'     => 'Твой аккаунт заблокирован. Свяжись с администратором.',
    'err_reg_off'    => 'Регистрация сейчас закрыта.',
    'err_not_found'  => 'Такая страница не найдена.',
    'err_need_login' => 'Сначала войди в аккаунт.',
    'ok_registered'  => 'Поздравляем! Аккаунт создан. Начинай учиться!',
    'ok_admin_created' => 'Администратор создан. Добро пожаловать в CodeTJ!',
    'lang_tj'        => 'ТҶ',
    'lang_ru'        => 'РУ',
    'home_title'     => 'Твои курсы',
    'total_progress' => 'Общий прогресс',
    'medal_1'        => '🥇',
    'medal_2'        => '🥈',
    'medal_3'        => '🥉',
    'stat_lessons'   => 'уроков готовится',
    'stat_free'      => 'бесплатно',
    'stat_lang'      => 'на таджикском',
    'why_title'      => 'Почему CodeTJ?',
    'why_1_t'        => 'На твоём языке',
    'why_1_d'        => 'Все уроки написаны живым таджикским — понятно, без сухого перевода.',
    'why_2_t'        => 'Код в браузере',
    'why_2_d'        => 'Ничего не нужно устанавливать: пишешь и сразу видишь результат.',
    'why_3_t'        => 'Проверка AI',
    'why_3_d'        => 'Искусственный интеллект проверяет работу, объясняет ошибки и даёт советы.',
    'why_4_t'        => 'Как игра',
    'why_4_d'        => 'Баллы, уровни, значки и рейтинг — учёба превращается в увлекательную игру.',
],
];

/* ============================================================
 *  ОМОДАСОЗӢ: база, корбар, забон, мавзӯъ
 * ============================================================ */

db(); // пайвастшавӣ + автомиграция

$p = isset($_GET['p']) && is_string($_GET['p']) ? $_GET['p'] : 'home';

$userCount = (int)db()->query('SELECT COUNT(*) FROM users')->fetchColumn();
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { // POST-ро коркарди худаш идора мекунад
    if ($userCount === 0 && $p !== 'setup') {
        redirect('?p=setup');
    }
    if ($userCount > 0 && $p === 'setup') {
        redirect('?p=home');
    }
}

$user = current_user();
if ($user !== null) {
    update_streak($user);
    maybe_reset_week();
}

$lang = 'tj';
if ($user !== null && in_array($user['lang'], ['tj', 'ru'], true)) {
    $lang = $user['lang'];
} elseif (isset($_COOKIE['codetj_lang']) && in_array($_COOKIE['codetj_lang'], ['tj', 'ru'], true)) {
    $lang = $_COOKIE['codetj_lang'];
}

$theme = 'dark';
if ($user !== null && in_array($user['theme'], ['dark', 'light'], true)) {
    $theme = $user['theme'];
} elseif (isset($_COOKIE['codetj_theme']) && in_array($_COOKIE['codetj_theme'], ['dark', 'light'], true)) {
    $theme = $_COOKIE['codetj_theme'];
}

/** Навиштаҷоти интерфейс аз рӯи калид. */
function t(string $key): string
{
    global $LANG, $lang;
    return $LANG[$lang][$key] ?? ($LANG['tj'][$key] ?? $key);
}

/** Майдони дузабона аз сатри база: fld('title', $lesson) → title_tj ё title_ru. */
function fld(string $base, array $row): string
{
    global $lang;
    $v = (string)($row[$base . '_' . $lang] ?? '');
    if ($v === '') { // агар тарҷума холӣ бошад — тоҷикӣ нишон медиҳем
        $v = (string)($row[$base . '_tj'] ?? '');
    }
    return $v;
}

function flash_set(string $type, string $key): void
{
    $_SESSION['flash'] = ['type' => $type, 'key' => $key];
}

function flash_get(): ?array
{
    if (empty($_SESSION['flash'])) {
        return null;
    }
    $f = $_SESSION['flash'];
    unset($_SESSION['flash']);
    return $f;
}

/** Суроғаи бозгашти бехатар (танҳо дохилӣ, бе open redirect). */
function safe_back(): string
{
    $b = $_POST['back'] ?? '';
    if (is_string($b) && preg_match('/^\?p=[a-z_]+(&[a-z]+=[a-zA-Z0-9_]+){0,3}$/', $b)) {
        return $b;
    }
    return '?p=home';
}

/* ============================================================
 *  КОРКАРДИ POST
 * ============================================================ */

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = isset($_POST['action']) && is_string($_POST['action']) ? $_POST['action'] : '';

    if (!csrf_ok()) {
        if ($action === 'settheme') {
            json_out(['ok' => false], 403);
        }
        flash_set('err', 'err_csrf');
        redirect(safe_back());
    }

    switch ($action) {

        /* --- Сохтани администратор (танҳо ҳангоми базаи холӣ) --- */
        case 'setup':
            if ($userCount > 0) {
                redirect('?p=home');
            }
            $loginV = trim((string)($_POST['login'] ?? ''));
            $nameV  = trim((string)($_POST['name'] ?? ''));
            $pass1  = (string)($_POST['password'] ?? '');
            $pass2  = (string)($_POST['password2'] ?? '');
            $err = validate_credentials($loginV, $nameV, $pass1, $pass2, false);
            if ($err !== null) {
                flash_set('err', $err);
                redirect('?p=setup');
            }
            $st = db()->prepare(
                "INSERT INTO users (login, pass_hash, name, role, lang) VALUES (?, ?, ?, 'admin', ?)"
            );
            $st->execute([$loginV, password_hash($pass1, PASSWORD_DEFAULT), $nameV, $lang]);
            session_regenerate_id(true);
            $_SESSION['uid'] = (int)db()->lastInsertId();
            flash_set('ok', 'ok_admin_created');
            redirect('?p=home');

        /* --- Бақайдгирӣ --- */
        case 'register':
            if ($user !== null) {
                redirect('?p=home');
            }
            if (setting_get('reg_enabled', '1') !== '1') {
                flash_set('err', 'err_reg_off');
                redirect('?p=register');
            }
            if (!rate_limit('register', 5, 3600)) {
                flash_set('err', 'err_rate');
                redirect('?p=register');
            }
            $loginV = trim((string)($_POST['login'] ?? ''));
            $nameV  = trim((string)($_POST['name'] ?? ''));
            $cityV  = mb_substr(trim((string)($_POST['city'] ?? '')), 0, 64);
            $pass1  = (string)($_POST['password'] ?? '');
            $pass2  = (string)($_POST['password2'] ?? '');
            $err = validate_credentials($loginV, $nameV, $pass1, $pass2, true);
            if ($err !== null) {
                flash_set('err', $err);
                redirect('?p=register');
            }
            $st = db()->prepare(
                'INSERT INTO users (login, pass_hash, name, city, lang) VALUES (?, ?, ?, ?, ?)'
            );
            $st->execute([$loginV, password_hash($pass1, PASSWORD_DEFAULT), $nameV, $cityV, $lang]);
            session_regenerate_id(true);
            $_SESSION['uid'] = (int)db()->lastInsertId();
            flash_set('ok', 'ok_registered');
            redirect('?p=home');

        /* --- Воридшавӣ --- */
        case 'login':
            if ($user !== null) {
                redirect('?p=home');
            }
            if (!rate_limit('login', 10, 600)) {
                flash_set('err', 'err_rate');
                redirect('?p=login');
            }
            $loginV = trim((string)($_POST['login'] ?? ''));
            $pass1  = (string)($_POST['password'] ?? '');
            $st = db()->prepare('SELECT * FROM users WHERE login = ?');
            $st->execute([$loginV]);
            $u = $st->fetch();
            if (!$u || !password_verify($pass1, $u['pass_hash'])) {
                flash_set('err', 'err_wrong_creds');
                redirect('?p=login');
            }
            if ((int)$u['banned'] === 1) {
                flash_set('err', 'err_banned');
                redirect('?p=login');
            }
            session_regenerate_id(true);
            $_SESSION['uid'] = (int)$u['id'];
            redirect('?p=home');

        /* --- Баромадан --- */
        case 'logout':
            $_SESSION = [];
            if (ini_get('session.use_cookies')) {
                $cp = session_get_cookie_params();
                setcookie(session_name(), '', [
                    'expires' => time() - 42000, 'path' => $cp['path'],
                    'httponly' => true, 'samesite' => 'Lax',
                ]);
            }
            session_destroy();
            redirect('?p=home');

        /* --- Иваз кардани забон --- */
        case 'setlang':
            $newLang = ($_POST['lang'] ?? '') === 'ru' ? 'ru' : 'tj';
            setcookie('codetj_lang', $newLang, [
                'expires' => time() + 60 * 60 * 24 * 365, 'path' => '/', 'samesite' => 'Lax',
            ]);
            if ($user !== null) {
                db()->prepare('UPDATE users SET lang = ? WHERE id = ?')
                    ->execute([$newLang, (int)$user['id']]);
            }
            redirect(safe_back());

        /* --- Захираи мавзӯъ дар профил (аз JS, fetch) --- */
        case 'settheme':
            $newTheme = ($_POST['theme'] ?? '') === 'light' ? 'light' : 'dark';
            if ($user !== null) {
                db()->prepare('UPDATE users SET theme = ? WHERE id = ?')
                    ->execute([$newTheme, (int)$user['id']]);
            }
            json_out(['ok' => true]);

        default:
            redirect('?p=home');
    }
}

/** Тафтиши логин/ном/парол. null = ҳама дуруст, вагарна калиди хато. */
function validate_credentials(string $login, string $name, string $p1, string $p2, bool $checkTaken): ?string
{
    if (!preg_match('/^[a-zA-Z0-9_]{3,32}$/', $login)) {
        return 'err_login_format';
    }
    if ($name === '' || mb_strlen($name) > 64) {
        return 'err_name_empty';
    }
    if (strlen($p1) < 6) {
        return 'err_pass_short';
    }
    if ($p1 !== $p2) {
        return 'err_pass_mismatch';
    }
    if ($checkTaken) {
        $st = db()->prepare('SELECT COUNT(*) FROM users WHERE login = ?');
        $st->execute([$login]);
        if ((int)$st->fetchColumn() > 0) {
            return 'err_login_taken';
        }
    }
    return null;
}

/* ============================================================
 *  РОУТИНГИ GET
 * ============================================================ */

switch ($p) {
    case 'home':
        page_home();
        break;
    case 'login':
        $user === null ? page_login() : redirect('?p=home');
        break;
    case 'register':
        $user === null ? page_register() : redirect('?p=home');
        break;
    case 'setup':
        page_setup();
        break;
    case 'course':
        page_course();
        break;
    case 'lesson':
        page_lesson();
        break;
    case 'profile':
        $user !== null ? page_profile() : redirect('?p=login');
        break;
    default:
        page_404();
}
exit;

/* ============================================================
 *  САҲИФАҲО
 * ============================================================ */

function page_home(): void
{
    global $user;
    render_header(t('nav_home'));

    if ($user === null) {
        render_hero_guest();
    } else {
        render_dashboard();
    }
    render_top3();
    render_footer();
}

function render_hero_guest(): void
{
    ?>
    <section class="hero">
      <h1><?= e(t('tagline')) ?></h1>
      <p class="hero-sub"><?= e(t('hero_text')) ?></p>
      <div class="hero-actions">
        <a class="btn btn-primary btn-lg" href="?p=register"><?= e(t('start_free')) ?></a>
        <a class="btn btn-ghost" href="?p=login"><?= e(t('have_account')) ?></a>
      </div>
      <div class="hero-stats">
        <div class="hstat"><b>200</b><span><?= e(t('stat_lessons')) ?></span></div>
        <div class="hstat"><b>100%</b><span><?= e(t('stat_free')) ?></span></div>
        <div class="hstat"><b>ТҶ</b><span><?= e(t('stat_lang')) ?></span></div>
      </div>
    </section>

    <section class="why">
      <h2><?= e(t('why_title')) ?></h2>
      <div class="why-grid">
        <div class="why-card"><div class="why-ic">🗣</div><h3><?= e(t('why_1_t')) ?></h3><p><?= e(t('why_1_d')) ?></p></div>
        <div class="why-card"><div class="why-ic">💻</div><h3><?= e(t('why_2_t')) ?></h3><p><?= e(t('why_2_d')) ?></p></div>
        <div class="why-card"><div class="why-ic">🤖</div><h3><?= e(t('why_3_t')) ?></h3><p><?= e(t('why_3_d')) ?></p></div>
        <div class="why-card"><div class="why-ic">🏆</div><h3><?= e(t('why_4_t')) ?></h3><p><?= e(t('why_4_d')) ?></p></div>
      </div>
    </section>
    <?php
    render_course_cards(null);
}

function render_dashboard(): void
{
    global $user;
    $streak = (int)$user['streak_days'];
    ?>
    <section class="dash-head">
      <div>
        <h1><?= e(t('welcome')) ?>, <?= e($user['name']) ?>! 👋</h1>
        <div class="dash-stats">
          <span class="chip">⭐ <?= (int)$user['points'] ?> <?= e(t('points')) ?></span>
          <span class="chip">🔥 <?= $streak ?> <?= e(t('streak')) ?></span>
        </div>
      </div>
    </section>
    <h2 class="sec-title"><?= e(t('home_title')) ?></h2>
    <?php
    render_course_cards((int)$user['id']);
}

/** Кортҳои 4 курс. $userId=null → барои меҳмон, бе пешрафт. */
function render_course_cards(?int $userId): void
{
    $fullOpen = $userId !== null ? full_course_unlocked($userId) : false;
    ?>
    <section class="courses-grid">
    <?php foreach (courses() as $slug => $c):
        $locked = ($slug === 'full') && ($userId === null || !$fullOpen);
        $done = $userId !== null ? course_done_count($userId, $slug) : 0;
        $pct = (int)round($done / LESSONS_PER_COURSE * 100);
        ?>
        <div class="course-card <?= $locked ? 'is-locked' : '' ?>" style="--cc:<?= e($c['color']) ?>">
          <div class="cc-top">
            <span class="cc-icon"><?= $c['icon'] ?></span>
            <span class="cc-name"><?= e(fld('name', $c)) ?></span>
            <?php if ($locked): ?><span class="cc-lock">🔒</span><?php endif; ?>
          </div>
          <p class="cc-desc"><?= e(fld('desc', $c)) ?></p>
          <div class="cc-meta"><?= e(t('lessons_50')) ?> · <?= e(t('levels_5')) ?></div>
          <?php if ($userId !== null && !$locked): ?>
            <div class="cc-bar"><div class="cc-bar-in" style="width:<?= $pct ?>%"></div></div>
            <div class="cc-progress"><?= $done ?> <?= e(t('of')) ?> <?= LESSONS_PER_COURSE ?> <?= e(t('done_word')) ?></div>
          <?php endif; ?>
          <?php if ($locked): ?>
            <p class="cc-hint"><?= e(t('full_locked_hint')) ?></p>
          <?php else: ?>
            <a class="btn btn-course" href="?p=course&c=<?= e($slug) ?>">
              <?= e($userId !== null && $done > 0 ? t('continue') : t('open_course')) ?> →
            </a>
          <?php endif; ?>
        </div>
    <?php endforeach; ?>
    </section>
    <?php
}

/** Топ-3 аз рӯи балли умумӣ. */
function render_top3(): void
{
    $rows = db()->query(
        "SELECT name, city, points FROM users WHERE banned = 0 AND role = 'student' AND points > 0
         ORDER BY points DESC, id ASC LIMIT 3"
    )->fetchAll();
    ?>
    <section class="top3">
      <h2 class="sec-title"><?= e(t('top_students')) ?></h2>
      <?php if (!$rows): ?>
        <p class="muted"><?= e(t('no_students')) ?></p>
      <?php else: ?>
        <div class="top3-grid">
        <?php foreach ($rows as $i => $r): ?>
          <div class="top3-card">
            <div class="top3-medal"><?= e(t('medal_' . ($i + 1))) ?></div>
            <div class="top3-name"><?= e($r['name']) ?></div>
            <?php if ($r['city'] !== ''): ?><div class="top3-city"><?= e($r['city']) ?></div><?php endif; ?>
            <div class="top3-pts">⭐ <?= (int)$r['points'] ?></div>
          </div>
        <?php endforeach; ?>
        </div>
      <?php endif; ?>
    </section>
    <?php
}

function page_login(): void
{
    render_header(t('login'));
    ?>
    <section class="auth-box">
      <h1><?= e(t('login')) ?></h1>
      <form method="post" action="index.php">
        <?= csrf_field() ?>
        <input type="hidden" name="action" value="login">
        <label><?= e(t('username')) ?>
          <input type="text" name="login" required maxlength="32" autocomplete="username">
        </label>
        <label><?= e(t('password')) ?>
          <input type="password" name="password" required autocomplete="current-password">
        </label>
        <button class="btn btn-primary btn-block" type="submit"><?= e(t('do_login')) ?></button>
      </form>
      <p class="auth-alt"><a href="?p=register"><?= e(t('no_account')) ?></a></p>
    </section>
    <?php
    render_footer();
}

function page_register(): void
{
    render_header(t('register'));
    ?>
    <section class="auth-box">
      <h1><?= e(t('register')) ?></h1>
      <form method="post" action="index.php">
        <?= csrf_field() ?>
        <input type="hidden" name="action" value="register">
        <label><?= e(t('name')) ?>
          <input type="text" name="name" required maxlength="64">
        </label>
        <label><?= e(t('city')) ?>
          <input type="text" name="city" maxlength="64" placeholder="<?= e(t('city_ph')) ?>">
        </label>
        <label><?= e(t('username')) ?>
          <input type="text" name="login" required maxlength="32" pattern="[a-zA-Z0-9_]{3,32}"
                 placeholder="<?= e(t('login_ph')) ?>" autocomplete="username">
        </label>
        <label><?= e(t('password')) ?>
          <input type="password" name="password" required minlength="6" autocomplete="new-password">
        </label>
        <label><?= e(t('password2')) ?>
          <input type="password" name="password2" required minlength="6" autocomplete="new-password">
        </label>
        <button class="btn btn-primary btn-block" type="submit"><?= e(t('do_register')) ?></button>
      </form>
      <p class="auth-alt"><a href="?p=login"><?= e(t('have_account')) ?></a></p>
    </section>
    <?php
    render_footer();
}

function page_setup(): void
{
    render_header(t('setup_title'));
    ?>
    <section class="auth-box">
      <h1>🛠 <?= e(t('setup_title')) ?></h1>
      <p class="muted"><?= e(t('setup_note')) ?></p>
      <form method="post" action="index.php">
        <?= csrf_field() ?>
        <input type="hidden" name="action" value="setup">
        <label><?= e(t('name')) ?>
          <input type="text" name="name" required maxlength="64">
        </label>
        <label><?= e(t('username')) ?>
          <input type="text" name="login" required maxlength="32" pattern="[a-zA-Z0-9_]{3,32}"
                 placeholder="<?= e(t('login_ph')) ?>" autocomplete="username">
        </label>
        <label><?= e(t('password')) ?>
          <input type="password" name="password" required minlength="6" autocomplete="new-password">
        </label>
        <label><?= e(t('password2')) ?>
          <input type="password" name="password2" required minlength="6" autocomplete="new-password">
        </label>
        <button class="btn btn-primary btn-block" type="submit"><?= e(t('create_admin')) ?></button>
      </form>
    </section>
    <?php
    render_footer();
}

/** Харитаи дарсҳои курс: 5 сатҳ × 10 дарс, бо қулфҳо. */
function page_course(): void
{
    global $user;
    $slug = isset($_GET['c']) && is_string($_GET['c']) ? $_GET['c'] : '';
    $all = courses();
    if (!isset($all[$slug])) {
        page_404();
        return;
    }
    if ($user === null) {
        flash_set('err', 'err_need_login');
        redirect('?p=login');
    }
    if ($slug === 'full' && !full_course_unlocked((int)$user['id'])) {
        flash_set('err', 'err_not_found');
        redirect('?p=home');
    }
    $c = $all[$slug];
    $uid = (int)$user['id'];

    // дарсҳои мавҷуда дар база: num → [id, title]
    $st = db()->prepare('SELECT id, num, title_tj, title_ru FROM lessons WHERE course = ? AND published = 1');
    $st->execute([$slug]);
    $lessons = [];
    foreach ($st->fetchAll() as $row) {
        $lessons[(int)$row['num']] = $row;
    }
    $doneMap = course_done_map($uid, $slug);
    $doneCnt = count($doneMap);
    $pct = (int)round($doneCnt / LESSONS_PER_COURSE * 100);

    render_header(fld('name', $c));
    ?>
    <section class="course-head" style="--cc:<?= e($c['color']) ?>">
      <a class="back-link" href="?p=home">← <?= e(t('back')) ?></a>
      <h1><span class="ch-icon"><?= $c['icon'] ?></span> <?= e(fld('name', $c)) ?></h1>
      <p class="muted"><?= e(fld('desc', $c)) ?></p>
      <div class="cc-bar big"><div class="cc-bar-in" style="width:<?= $pct ?>%"></div></div>
      <div class="cc-progress"><?= $doneCnt ?> <?= e(t('of')) ?> <?= LESSONS_PER_COURSE ?> <?= e(t('done_word')) ?> (<?= $pct ?>%)</div>
    </section>

    <?php foreach (levels() as $lvl => $lname):
        $unlocked = level_unlocked($uid, $slug, $lvl);
        $from = ($lvl - 1) * LESSONS_PER_LEVEL + 1;
        $to = $lvl * LESSONS_PER_LEVEL;
        ?>
        <section class="level-block <?= $unlocked ? '' : 'is-locked' ?>" style="--cc:<?= e($c['color']) ?>">
          <div class="level-head">
            <h2><?= $unlocked ? '📗' : '🔒' ?> <?= e(t('level')) ?> <?= $lvl ?> — <?= e($lname[$GLOBALS['lang']] ?? $lname['tj']) ?></h2>
            <span class="level-range"><?= e(t('lesson')) ?> <?= $from ?>–<?= $to ?></span>
          </div>
          <?php if (!$unlocked): ?>
            <p class="muted"><?= e(t('level_locked_hint')) ?></p>
          <?php endif; ?>
          <div class="lesson-map">
            <?php for ($n = $from; $n <= $to; $n++):
                $L = $lessons[$n] ?? null;
                $isDone = isset($doneMap[$n]);
                $title = $L !== null ? fld('title', $L) : t('lesson_not_ready');
                if ($unlocked && $L !== null): ?>
                  <a class="lcell <?= $isDone ? 'done' : 'open' ?>" href="?p=lesson&id=<?= (int)$L['id'] ?>" title="<?= e($title) ?>">
                    <span class="lnum"><?= $isDone ? '✓' : $n ?></span>
                  </a>
                <?php else: ?>
                  <span class="lcell <?= $unlocked ? 'soon' : 'lock' ?>" title="<?= e($title) ?>">
                    <span class="lnum"><?= $unlocked ? $n : '🔒' ?></span>
                  </span>
                <?php endif;
            endfor; ?>
          </div>
          <?php if ($unlocked && $lvl < 5): ?>
            <div class="exam-row">
              <?php if (exam_passed($uid, $slug, $lvl)): ?>
                <span class="exam-badge ok">✅ <?= e(t('exam_passed')) ?></span>
              <?php else: ?>
                <span class="exam-badge"><?= e(t('level_exam')) ?> — <?= e(t('exam_soon')) ?></span>
                <p class="muted small"><?= e(t('exam_hint')) ?></p>
              <?php endif; ?>
            </div>
          <?php endif; ?>
        </section>
    <?php endforeach; ?>
    <?php
    render_footer();
}

/** Саҳифаи дарс — дар Қисми 1: назария + намуна. */
function page_lesson(): void
{
    global $user;
    if ($user === null) {
        flash_set('err', 'err_need_login');
        redirect('?p=login');
    }
    $id = (int)($_GET['id'] ?? 0);
    $st = db()->prepare('SELECT * FROM lessons WHERE id = ? AND published = 1');
    $st->execute([$id]);
    $L = $st->fetch();
    if (!$L) {
        page_404();
        return;
    }
    $uid = (int)$user['id'];
    $slug = (string)$L['course'];
    $num = (int)$L['num'];
    $lvl = (int)ceil($num / LESSONS_PER_LEVEL);
    if (($slug === 'full' && !full_course_unlocked($uid)) || !level_unlocked($uid, $slug, $lvl)) {
        redirect('?p=course&c=' . $slug);
    }
    $c = courses()[$slug];
    $theory = fld('theory', $L);
    $taskText = fld('task_text', $L);

    render_header(fld('title', $L));
    ?>
    <section class="lesson-page" style="--cc:<?= e($c['color']) ?>">
      <a class="back-link" href="?p=course&c=<?= e($slug) ?>">← <?= e(t('back')) ?></a>
      <h1><span class="lesson-tag"><?= e(fld('name', $c)) ?> · <?= e(t('lesson')) ?> <?= $num ?></span><br><?= e(fld('title', $L)) ?></h1>

      <div class="lesson-block">
        <h2>📖 <?= e(t('theory')) ?></h2>
        <div class="theory-body">
          <?php
          // Назарияро админ/импорт менависад (HTML-и боэътимод аз база).
          echo $theory !== '' ? $theory : '<p class="muted">' . e(t('lesson_not_ready')) . '</p>';
          ?>
        </div>
      </div>

      <?php if (!empty($L['example_code'])): ?>
      <div class="lesson-block">
        <h2>💡 <?= e(t('example')) ?></h2>
        <pre class="code-view"><code><?= e((string)$L['example_code']) ?></code></pre>
      </div>
      <?php endif; ?>

      <?php if ($taskText !== ''): ?>
      <div class="lesson-block">
        <h2>✍️ <?= e(t('practice')) ?></h2>
        <div class="theory-body"><?= $taskText ?></div>
      </div>
      <?php endif; ?>

      <div class="lesson-block soon-note">
        <p>🚧 <?= e(t('practice_soon')) ?></p>
      </div>
    </section>
    <?php
    render_footer();
}

function page_profile(): void
{
    global $user;
    $uid = (int)$user['id'];

    $st = db()->prepare("SELECT COUNT(*) + 1 FROM users WHERE banned = 0 AND points > ? AND role = 'student'");
    $st->execute([(int)$user['points']]);
    $rank = (int)$st->fetchColumn();

    render_header(t('nav_profile'));
    ?>
    <section class="profile-head">
      <div class="avatar"><?= e(mb_strtoupper(mb_substr($user['name'], 0, 1))) ?></div>
      <div>
        <h1><?= e($user['name']) ?></h1>
        <?php if ($user['city'] !== ''): ?><p class="muted">📍 <?= e($user['city']) ?></p><?php endif; ?>
        <div class="dash-stats">
          <span class="chip">⭐ <?= (int)$user['points'] ?> <?= e(t('points')) ?></span>
          <span class="chip">🔥 <?= (int)$user['streak_days'] ?> <?= e(t('streak')) ?></span>
          <span class="chip">🏅 <?= e(t('rank')) ?>: <?= $rank ?></span>
        </div>
      </div>
    </section>

    <h2 class="sec-title"><?= e(t('my_progress')) ?></h2>
    <section class="prof-progress">
      <?php foreach (courses() as $slug => $c):
          $done = course_done_count($uid, $slug);
          $pct = (int)round($done / LESSONS_PER_COURSE * 100);
          ?>
          <div class="prof-row" style="--cc:<?= e($c['color']) ?>">
            <span class="prof-course"><?= $c['icon'] ?> <?= e(fld('name', $c)) ?></span>
            <div class="cc-bar"><div class="cc-bar-in" style="width:<?= $pct ?>%"></div></div>
            <span class="prof-pct"><?= $done ?>/<?= LESSONS_PER_COURSE ?></span>
          </div>
      <?php endforeach; ?>
    </section>
    <?php
    render_footer();
}

function page_404(): void
{
    http_response_code(404);
    render_header('404');
    ?>
    <section class="auth-box" style="text-align:center">
      <h1 style="font-size:3rem">🤷</h1>
      <p><?= e(t('err_not_found')) ?></p>
      <a class="btn btn-primary" href="?p=home"><?= e(t('nav_home')) ?></a>
    </section>
    <?php
    render_footer();
}

/* ============================================================
 *  ҚОЛИБ: сарлавҳа, поён, услуб
 * ============================================================ */

function render_header(string $title): void
{
    global $user, $lang, $theme, $p;
    $backUrl = '?p=' . preg_replace('/[^a-z_]/', '', $p);
    if ($p === 'course' && isset($_GET['c']) && is_string($_GET['c']) && preg_match('/^[a-z]+$/', $_GET['c'])) {
        $backUrl .= '&c=' . $_GET['c'];
    } elseif ($p === 'lesson' && isset($_GET['id'])) {
        $backUrl .= '&id=' . (int)$_GET['id'];
    }
    $flash = flash_get();
    ?>
<!doctype html>
<html lang="<?= $lang === 'ru' ? 'ru' : 'tg' ?>" class="<?= $theme === 'light' ? 'light' : '' ?>">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= e($title) ?> — CodeTJ</title>
<meta name="description" content="<?= e(t('tagline')) ?>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans:ital,wght@0,400;0,600;0,800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style><?php render_css(); ?></style>
</head>
<body>
<header class="topbar">
  <a class="logo" href="?p=home">Code<span>TJ</span></a>
  <nav class="topnav">
    <a href="?p=home" class="<?= $p === 'home' ? 'act' : '' ?>"><?= e(t('nav_home')) ?></a>
    <?php if ($user !== null): ?>
      <a href="?p=profile" class="<?= $p === 'profile' ? 'act' : '' ?>"><?= e(t('nav_profile')) ?></a>
    <?php endif; ?>
  </nav>
  <div class="topbar-right">
    <form method="post" action="index.php" class="lang-form">
      <?= csrf_field() ?>
      <input type="hidden" name="action" value="setlang">
      <input type="hidden" name="back" value="<?= e($backUrl) ?>">
      <button type="submit" name="lang" value="tj" class="lang-btn <?= $lang === 'tj' ? 'act' : '' ?>"><?= e(t('lang_tj')) ?></button>
      <button type="submit" name="lang" value="ru" class="lang-btn <?= $lang === 'ru' ? 'act' : '' ?>"><?= e(t('lang_ru')) ?></button>
    </form>
    <button id="themeBtn" class="icon-btn" title="<?= e(t('theme_toggle')) ?>"><?= $theme === 'light' ? '🌙' : '☀️' ?></button>
    <?php if ($user !== null): ?>
      <form method="post" action="index.php" class="inline-form">
        <?= csrf_field() ?>
        <input type="hidden" name="action" value="logout">
        <button type="submit" class="btn btn-sm btn-ghost"><?= e(t('logout')) ?></button>
      </form>
    <?php else: ?>
      <a class="btn btn-sm btn-primary" href="?p=login"><?= e(t('login')) ?></a>
    <?php endif; ?>
  </div>
</header>
<main class="wrap">
<?php if ($flash !== null): ?>
  <div class="flash <?= $flash['type'] === 'ok' ? 'flash-ok' : 'flash-err' ?>"><?= e(t($flash['key'])) ?></div>
<?php endif; ?>
    <?php
}

function render_footer(): void
{
    global $theme;
    ?>
</main>
<footer class="footer">
  <p><b>CodeTJ</b> © <?= date('Y') ?> · <?= e(t('footer_note')) ?></p>
</footer>
<script>
(function () {
  var btn = document.getElementById('themeBtn');
  if (!btn) return;
  btn.addEventListener('click', function () {
    var html = document.documentElement;
    var light = html.classList.toggle('light');
    var theme = light ? 'light' : 'dark';
    btn.textContent = light ? '🌙' : '☀️';
    document.cookie = 'codetj_theme=' + theme + ';path=/;max-age=31536000;samesite=Lax';
    // агар корбар ворид шуда бошад — дар профил ҳам захира мекунем
    var csrf = document.querySelector('input[name="csrf"]');
    if (csrf) {
      var fd = new FormData();
      fd.append('action', 'settheme');
      fd.append('theme', theme);
      fd.append('csrf', csrf.value);
      fetch('index.php', { method: 'POST', body: fd }).catch(function () {});
    }
  });
})();
</script>
</body>
</html>
    <?php
}

function render_css(): void
{
    ?>
:root{
  --bg:#0b1120;--bg2:#111a2e;--card:#16223a;--card2:#1c2a45;--line:#243350;
  --txt:#e7edf7;--muted:#8fa0bd;--accent:#38bdf8;--accent2:#818cf8;
  --ok:#22c55e;--err:#ef4444;--radius:16px;
  --shadow:0 10px 30px rgba(0,0,0,.35);
}
html.light{
  --bg:#f2f5fa;--bg2:#e8edf5;--card:#ffffff;--card2:#f6f8fc;--line:#dbe3ef;
  --txt:#17233b;--muted:#5b6b88;--shadow:0 8px 24px rgba(23,35,59,.10);
}
*{margin:0;padding:0;box-sizing:border-box}
body{
  font-family:'Noto Sans',system-ui,-apple-system,'Segoe UI',sans-serif;
  background:var(--bg);color:var(--txt);min-height:100vh;
  display:flex;flex-direction:column;line-height:1.65;
  -webkit-font-smoothing:antialiased;
}
a{color:var(--accent);text-decoration:none}
h1,h2,h3{line-height:1.3;font-weight:800}
.wrap{width:100%;max-width:1080px;margin:0 auto;padding:24px 16px;flex:1}

/* ---- шапка ---- */
.topbar{
  position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:16px;
  padding:10px 16px;background:color-mix(in srgb,var(--bg) 82%,transparent);
  backdrop-filter:blur(12px);border-bottom:1px solid var(--line);
}
.logo{font-size:1.35rem;font-weight:800;color:var(--txt);letter-spacing:-.5px}
.logo span{color:var(--accent)}
.topnav{display:flex;gap:4px;flex:1}
.topnav a{color:var(--muted);padding:6px 12px;border-radius:10px;font-weight:600;font-size:.95rem}
.topnav a.act,.topnav a:hover{color:var(--txt);background:var(--card)}
.topbar-right{display:flex;align-items:center;gap:8px}
.lang-form{display:flex;border:1px solid var(--line);border-radius:10px;overflow:hidden}
.lang-btn{background:transparent;border:0;color:var(--muted);padding:6px 10px;font-weight:700;cursor:pointer;font-size:.85rem}
.lang-btn.act{background:var(--accent);color:#04121f}
.icon-btn{background:transparent;border:1px solid var(--line);border-radius:10px;padding:5px 9px;cursor:pointer;font-size:1rem}
.inline-form{display:inline}

/* ---- тугмаҳо ---- */
.btn{
  display:inline-block;border:0;border-radius:12px;cursor:pointer;
  font-weight:700;font-family:inherit;font-size:1rem;padding:12px 22px;
  transition:transform .15s,opacity .15s;color:var(--txt);
}
.btn:hover{transform:translateY(-1px)}
.btn:active{transform:translateY(0)}
.btn-primary{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#04121f}
html.light .btn-primary{color:#fff}
.btn-ghost{background:var(--card);border:1px solid var(--line)}
.btn-sm{padding:7px 14px;font-size:.9rem}
.btn-lg{padding:15px 30px;font-size:1.1rem}
.btn-block{width:100%}
.btn-course{background:var(--cc);color:#fff;padding:10px 18px;font-size:.95rem}

/* ---- flash ---- */
.flash{padding:13px 18px;border-radius:12px;margin-bottom:18px;font-weight:600}
.flash-ok{background:color-mix(in srgb,var(--ok) 18%,transparent);border:1px solid var(--ok)}
.flash-err{background:color-mix(in srgb,var(--err) 18%,transparent);border:1px solid var(--err)}

/* ---- герой ---- */
.hero{text-align:center;padding:56px 8px 40px}
.hero h1{
  font-size:clamp(1.8rem,5.5vw,3.2rem);
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;
}
.hero-sub{max-width:620px;margin:16px auto 0;color:var(--muted);font-size:1.08rem}
.hero-actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:28px}
.hero-stats{display:flex;gap:14px;justify-content:center;flex-wrap:wrap;margin-top:40px}
.hstat{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:14px 26px;min-width:120px}
.hstat b{display:block;font-size:1.5rem;color:var(--accent)}
.hstat span{color:var(--muted);font-size:.85rem}

/* ---- чаро мо ---- */
.why{padding:24px 0}
.why h2{text-align:center;margin-bottom:24px;font-size:1.6rem}
.why-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
.why-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px}
.why-ic{font-size:1.9rem;margin-bottom:8px}
.why-card h3{font-size:1.05rem;margin-bottom:6px}
.why-card p{color:var(--muted);font-size:.92rem}

/* ---- дашборд ---- */
.dash-head{padding:16px 0 4px}
.dash-head h1{font-size:clamp(1.4rem,4vw,2rem)}
.dash-stats{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.chip{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:6px 14px;font-size:.9rem;font-weight:600}
.sec-title{margin:28px 0 16px;font-size:1.35rem}

/* ---- кортҳои курс ---- */
.courses-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;padding:8px 0 24px}
.course-card{
  background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:22px;display:flex;flex-direction:column;gap:10px;position:relative;
  border-top:3px solid var(--cc);box-shadow:var(--shadow);
}
.course-card.is-locked{opacity:.75}
.cc-top{display:flex;align-items:center;gap:10px}
.cc-icon{font-size:1.6rem}
.cc-name{font-size:1.25rem;font-weight:800;flex:1}
.cc-lock{font-size:1.1rem}
.cc-desc{color:var(--muted);font-size:.92rem;flex:1}
.cc-meta{color:var(--muted);font-size:.8rem;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.cc-bar{height:8px;background:var(--bg2);border-radius:99px;overflow:hidden}
.cc-bar.big{height:12px;margin-top:14px}
.cc-bar-in{height:100%;background:var(--cc);border-radius:99px;transition:width .4s}
.cc-progress{color:var(--muted);font-size:.85rem}
.cc-hint{color:var(--muted);font-size:.85rem;background:var(--bg2);border-radius:10px;padding:10px 12px}

/* ---- топ-3 ---- */
.top3{padding-bottom:24px}
.top3-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;max-width:640px}
.top3-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px;text-align:center}
.top3-medal{font-size:2rem}
.top3-name{font-weight:800;margin-top:6px}
.top3-city{color:var(--muted);font-size:.85rem}
.top3-pts{margin-top:6px;font-weight:700;color:var(--accent)}

/* ---- саҳифаи курс ---- */
.course-head{padding:12px 0 8px}
.course-head h1{font-size:clamp(1.5rem,4.5vw,2.2rem);margin-top:10px}
.ch-icon{font-size:1.8rem}
.back-link{color:var(--muted);font-weight:600;font-size:.9rem}
.level-block{
  background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:20px;margin-top:18px;
}
.level-block.is-locked{opacity:.6}
.level-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.level-head h2{font-size:1.15rem}
.level-range{color:var(--muted);font-size:.85rem;font-weight:600}
.lesson-map{display:grid;grid-template-columns:repeat(auto-fill,minmax(52px,1fr));gap:8px}
.lcell{
  aspect-ratio:1;display:flex;align-items:center;justify-content:center;
  border-radius:12px;background:var(--bg2);border:1px solid var(--line);
  font-weight:800;font-size:1rem;color:var(--muted);transition:transform .12s;
}
.lcell.open{color:var(--txt);border-color:var(--cc);cursor:pointer}
.lcell.open:hover{transform:scale(1.08);background:var(--cc);color:#fff}
.lcell.done{background:var(--cc);border-color:var(--cc);color:#fff}
.lcell.lock{opacity:.55;font-size:.8rem}
.lcell.soon{opacity:.5}
.exam-row{margin-top:14px}
.exam-badge{
  display:inline-block;background:var(--bg2);border:1px dashed var(--line);
  border-radius:10px;padding:8px 14px;font-size:.88rem;font-weight:600;color:var(--muted);
}
.exam-badge.ok{border-style:solid;border-color:var(--ok);color:var(--ok)}
.small{font-size:.82rem;margin-top:6px}

/* ---- саҳифаи дарс ---- */
.lesson-page h1{font-size:clamp(1.3rem,4vw,1.9rem);margin:12px 0 6px}
.lesson-tag{
  display:inline-block;font-size:.78rem;font-weight:700;letter-spacing:.5px;
  color:var(--cc);text-transform:uppercase;margin-bottom:4px;
}
.lesson-block{
  background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:22px;margin-top:16px;
}
.lesson-block h2{font-size:1.1rem;margin-bottom:12px}
.theory-body{color:var(--txt)}
.theory-body p{margin:10px 0}
.theory-body h3{margin:16px 0 8px}
.theory-body ul,.theory-body ol{padding-left:22px;margin:10px 0}
.theory-body code{
  font-family:'JetBrains Mono',monospace;font-size:.88em;
  background:var(--bg2);padding:2px 6px;border-radius:6px;color:var(--accent);
}
.code-view{
  background:#0d1526;border:1px solid var(--line);border-radius:12px;
  padding:16px;overflow-x:auto;
}
html.light .code-view{background:#1c2a45}
.code-view code{font-family:'JetBrains Mono',monospace;font-size:.86rem;color:#c9d8f0;white-space:pre}
.soon-note{border-style:dashed;text-align:center;color:var(--muted)}

/* ---- профил ---- */
.profile-head{display:flex;gap:18px;align-items:center;padding:16px 0;flex-wrap:wrap}
.avatar{
  width:84px;height:84px;border-radius:50%;flex-shrink:0;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  display:flex;align-items:center;justify-content:center;
  font-size:2.2rem;font-weight:800;color:#04121f;
}
html.light .avatar{color:#fff}
.prof-progress{display:flex;flex-direction:column;gap:12px}
.prof-row{display:grid;grid-template-columns:150px 1fr 60px;gap:12px;align-items:center}
.prof-course{font-weight:700;font-size:.95rem}
.prof-pct{color:var(--muted);font-size:.85rem;text-align:right}

/* ---- аутентификация ---- */
.auth-box{
  max-width:420px;margin:32px auto;background:var(--card);
  border:1px solid var(--line);border-radius:var(--radius);padding:30px;box-shadow:var(--shadow);
}
.auth-box h1{font-size:1.5rem;margin-bottom:14px}
.auth-box form{display:flex;flex-direction:column;gap:14px;margin-top:12px}
.auth-box label{display:flex;flex-direction:column;gap:6px;font-weight:600;font-size:.92rem}
.auth-box input{
  background:var(--bg2);border:1px solid var(--line);border-radius:10px;
  padding:12px 14px;color:var(--txt);font-family:inherit;font-size:1rem;
}
.auth-box input:focus{outline:2px solid var(--accent);border-color:transparent}
.auth-alt{margin-top:16px;text-align:center;font-size:.92rem}

/* ---- умумӣ ---- */
.muted{color:var(--muted)}
.footer{border-top:1px solid var(--line);padding:22px 16px;text-align:center;color:var(--muted);font-size:.88rem}

/* ---- мобилӣ ---- */
@media (max-width:640px){
  .topbar{flex-wrap:wrap;gap:8px}
  .topnav{order:3;width:100%;justify-content:center}
  .prof-row{grid-template-columns:110px 1fr 52px}
  .lesson-map{grid-template-columns:repeat(5,1fr)}
  .hero{padding-top:32px}
}
    <?php
}
