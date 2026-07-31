<?php
/**
 * CodeTJ — барнома (аз index.php даъват мешавад).
 * Роутинг: ?p=...  Синтаксис: PHP 7.1+ мутобиқ.
 */

require __DIR__ . '/db.php';
codetj_session_start();

/* ============================================================
 *  ЗАБОНҲО — тамоми навиштаҷоти интерфейс дар як ҷо.
 * ============================================================ */
$LANG = array(
'tj' => array(
    'tagline'        => 'Барномасозиро бо забони тоҷикӣ омӯз',
    'hero_text'      => 'HTML, CSS ва JavaScript — бо забони модарӣ, бо мисолҳои зинда. Кодро дар браузер менависӣ ва дарҳол натиҷаро мебинӣ.',
    'start_free'     => 'Оғоз кун — ройгон',
    'have_account'   => 'Аллакай ҳисоб дорӣ? Ворид шав',
    'nav_home'       => 'Асосӣ',
    'nav_profile'    => 'Профил',
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
    'of'             => 'аз',
    'done_word'      => 'супорида шуд',
    'continue'       => 'Давом додан',
    'open_course'    => 'Кушодан',
    'full_locked_hint' => 'Ин курс кушода мешавад, вақте ки дар HTML, CSS ва JavaScript ҳар кадомашро на кам аз 60% мегузаронӣ. Ту метавонӣ!',
    'level'          => 'Сатҳ',
    'level_locked_hint' => 'Ин сатҳ пӯшида аст. Аввал ҳамаи 10 дарси сатҳи пешинаро супор.',
    'lesson'         => 'Дарс',
    'lesson_not_ready' => 'Ин дарс ҳанӯз тайёр мешавад. Ба зудӣ пайдо мешавад!',
    'soon'           => 'Ба зудӣ',
    'back'           => 'Бозгашт',
    'theory'         => 'Назария',
    'example'        => 'Намуна',
    'practice'       => 'Амалия',
    'test'           => 'Тест',
    'open_in_editor' => 'Дар муҳаррир кушодан',
    'run'            => 'Иҷро',
    'clear'          => 'Тоза кардан',
    'save'           => 'Захира',
    'reset'          => 'Аз нав',
    'fullscreen'     => 'Экрани пурра',
    'preview'        => 'Натиҷа',
    'code'           => 'Код',
    'saved'          => 'Захира шуд',
    'saving'         => 'Захира мешавад…',
    'save_err'       => 'Захира нашуд',
    'task'           => 'Супориш',
    'test_intro'     => 'Ба 5 савол ҷавоб деҳ. Ҷавоби дуруст аз кӯшиши аввал — 10 балл, аз дуюм — 5 балл.',
    'test_send'      => 'Ҷавобҳоро фиристодан',
    'test_again'     => 'Аз нав кӯшиш кардан',
    'test_result'    => 'Натиҷаи тест',
    'test_correct'   => 'Дуруст',
    'test_wrong'     => 'Нодуруст',
    'test_need_all'  => 'Ба ҳамаи саволҳо ҷавоб деҳ.',
    'test_passed'    => 'Офарин! Тест супорида шуд.',
    'test_failed'    => 'Ҳанӯз кам аст. Назарияро боз як бор хон ва кӯшиш кун.',
    'try_once_more'  => 'Нодуруст. Боз як бор фикр кун — ҷавоб дар назария ҳаст.',
    'lesson_done'    => 'Дарс супорида шуд!',
    'lesson_done_txt'=> 'Дарси навбатӣ кушода шуд. Давом деҳ!',
    'next_lesson'    => 'Дарси навбатӣ',
    'you_got'        => 'Ту гирифтӣ',
    'my_progress'    => 'Пешрафти ман',
    'top_students'   => 'Беҳтарин шогирдон',
    'no_students'    => 'Ҳанӯз касе нест — аввалин шав!',
    'rank'           => 'Ҷой дар рейтинг',
    'home_title'     => 'Курсҳои ту',
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
    'stat_lessons'   => 'дарс',
    'stat_free'      => 'ройгон',
    'stat_lang'      => 'бо тоҷикӣ',
    'why_title'      => 'Чаро CodeTJ?',
    'why_1_t'        => 'Бо забони худат',
    'why_1_d'        => 'Ҳамаи дарсҳо бо тоҷикии зинда навишта шудаанд — фаҳмо, бе тарҷумаи хушк.',
    'why_2_t'        => 'Код дар браузер',
    'why_2_d'        => 'Ҳеҷ чиз насб кардан лозим нест: менависӣ ва дарҳол натиҷаро мебинӣ.',
    'why_3_t'        => 'Қадам ба қадам',
    'why_3_d'        => 'Аз тегҳои оддӣ то лоиҳаҳои воқеӣ — бе ҷаҳиш, бе холигоҳ.',
    'why_4_t'        => 'Бозӣ барин',
    'why_4_d'        => 'Балл, сатҳ ва рейтинг — омӯзиш мисли бозии шавқовар.',
),
'ru' => array(
    'tagline'        => 'Учи программирование на таджикском',
    'hero_text'      => 'HTML, CSS и JavaScript — на родном языке, с живыми примерами. Пишешь код в браузере и сразу видишь результат.',
    'start_free'     => 'Начать — бесплатно',
    'have_account'   => 'Уже есть аккаунт? Войти',
    'nav_home'       => 'Главная',
    'nav_profile'    => 'Профиль',
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
    'of'             => 'из',
    'done_word'      => 'пройдено',
    'continue'       => 'Продолжить',
    'open_course'    => 'Открыть',
    'full_locked_hint' => 'Этот курс откроется, когда в HTML, CSS и JavaScript будет пройдено не меньше 60% уроков. У тебя получится!',
    'level'          => 'Уровень',
    'level_locked_hint' => 'Этот уровень закрыт. Сначала пройди все 10 уроков предыдущего уровня.',
    'lesson'         => 'Урок',
    'lesson_not_ready' => 'Этот урок ещё готовится. Скоро появится!',
    'soon'           => 'Скоро',
    'back'           => 'Назад',
    'theory'         => 'Теория',
    'example'        => 'Пример',
    'practice'       => 'Практика',
    'test'           => 'Тест',
    'open_in_editor' => 'Открыть в редакторе',
    'run'            => 'Запустить',
    'clear'          => 'Очистить',
    'save'           => 'Сохранить',
    'reset'          => 'Сбросить',
    'fullscreen'     => 'Во весь экран',
    'preview'        => 'Результат',
    'code'           => 'Код',
    'saved'          => 'Сохранено',
    'saving'         => 'Сохраняем…',
    'save_err'       => 'Не сохранилось',
    'task'           => 'Задание',
    'test_intro'     => 'Ответь на 5 вопросов. Правильный ответ с первой попытки — 10 баллов, со второй — 5.',
    'test_send'      => 'Отправить ответы',
    'test_again'     => 'Попробовать снова',
    'test_result'    => 'Результат теста',
    'test_correct'   => 'Верно',
    'test_wrong'     => 'Неверно',
    'test_need_all'  => 'Ответь на все вопросы.',
    'test_passed'    => 'Молодец! Тест сдан.',
    'test_failed'    => 'Пока маловато. Перечитай теорию и попробуй ещё раз.',
    'try_once_more'  => 'Неверно. Подумай ещё раз — ответ есть в теории.',
    'lesson_done'    => 'Урок пройден!',
    'lesson_done_txt'=> 'Следующий урок открыт. Продолжай!',
    'next_lesson'    => 'Следующий урок',
    'you_got'        => 'Ты получил',
    'my_progress'    => 'Мой прогресс',
    'top_students'   => 'Лучшие ученики',
    'no_students'    => 'Пока никого нет — стань первым!',
    'rank'           => 'Место в рейтинге',
    'home_title'     => 'Твои курсы',
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
    'stat_lessons'   => 'уроков',
    'stat_free'      => 'бесплатно',
    'stat_lang'      => 'на таджикском',
    'why_title'      => 'Почему CodeTJ?',
    'why_1_t'        => 'На твоём языке',
    'why_1_d'        => 'Все уроки написаны живым таджикским — понятно, без сухого перевода.',
    'why_2_t'        => 'Код в браузере',
    'why_2_d'        => 'Ничего не нужно устанавливать: пишешь и сразу видишь результат.',
    'why_3_t'        => 'Шаг за шагом',
    'why_3_d'        => 'От простых тегов до реальных проектов — без скачков и пробелов.',
    'why_4_t'        => 'Как игра',
    'why_4_d'        => 'Баллы, уровни и рейтинг — учёба превращается в увлекательную игру.',
),
);

/* ============================================================
 *  ОМОДАСОЗӢ
 * ============================================================ */

db();

$p = isset($_GET['p']) && is_string($_GET['p']) ? $_GET['p'] : 'home';

$userCount = (int)db()->query('SELECT COUNT(*) FROM users')->fetchColumn();
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
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
if ($user !== null && in_array($user['lang'], array('tj', 'ru'), true)) {
    $lang = $user['lang'];
} elseif (isset($_COOKIE['codetj_lang']) && in_array($_COOKIE['codetj_lang'], array('tj', 'ru'), true)) {
    $lang = $_COOKIE['codetj_lang'];
}

$theme = 'dark';
if ($user !== null && in_array($user['theme'], array('dark', 'light'), true)) {
    $theme = $user['theme'];
} elseif (isset($_COOKIE['codetj_theme']) && in_array($_COOKIE['codetj_theme'], array('dark', 'light'), true)) {
    $theme = $_COOKIE['codetj_theme'];
}

/** Навиштаҷоти интерфейс. */
function t($key)
{
    global $LANG, $lang;
    if (isset($LANG[$lang][$key])) {
        return $LANG[$lang][$key];
    }
    return isset($LANG['tj'][$key]) ? $LANG['tj'][$key] : $key;
}

/** Майдони дузабона: fld('title', $row) → title_tj ё title_ru. */
function fld($base, $row)
{
    global $lang;
    $v = isset($row[$base . '_' . $lang]) ? (string)$row[$base . '_' . $lang] : '';
    if ($v === '' && isset($row[$base . '_tj'])) {
        $v = (string)$row[$base . '_tj'];
    }
    return $v;
}

function flash_set($type, $key)
{
    $_SESSION['flash'] = array('type' => $type, 'key' => $key);
}

function flash_get()
{
    if (empty($_SESSION['flash'])) {
        return null;
    }
    $f = $_SESSION['flash'];
    unset($_SESSION['flash']);
    return $f;
}

/** Суроғаи бозгашти бехатар (танҳо дохилӣ). */
function safe_back()
{
    $b = isset($_POST['back']) ? $_POST['back'] : '';
    if (is_string($b) && preg_match('/^\?p=[a-z_]+(&[a-z]+=[a-zA-Z0-9_]+){0,3}$/', $b)) {
        return $b;
    }
    return '?p=home';
}

/** null = ҳама дуруст, вагарна калиди хато. */
function validate_credentials($login, $name, $p1, $p2, $checkTaken)
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
        $st->execute(array($login));
        if ((int)$st->fetchColumn() > 0) {
            return 'err_login_taken';
        }
    }
    return null;
}

/* ============================================================
 *  КОРКАРДИ POST
 * ============================================================ */

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = isset($_POST['action']) && is_string($_POST['action']) ? $_POST['action'] : '';
    $isAjax = in_array($action, array('settheme', 'savedraft'), true);

    if (!csrf_ok()) {
        if ($isAjax) {
            json_out(array('ok' => false, 'err' => 'csrf'), 403);
        }
        flash_set('err', 'err_csrf');
        redirect(safe_back());
    }

    switch ($action) {

        case 'setup':
            if ($userCount > 0) {
                redirect('?p=home');
            }
            $loginV = trim((string)(isset($_POST['login']) ? $_POST['login'] : ''));
            $nameV  = trim((string)(isset($_POST['name']) ? $_POST['name'] : ''));
            $pass1  = (string)(isset($_POST['password']) ? $_POST['password'] : '');
            $pass2  = (string)(isset($_POST['password2']) ? $_POST['password2'] : '');
            $err = validate_credentials($loginV, $nameV, $pass1, $pass2, false);
            if ($err !== null) {
                flash_set('err', $err);
                redirect('?p=setup');
            }
            $st = db()->prepare("INSERT INTO users (login, pass_hash, name, role, lang) VALUES (?, ?, ?, 'admin', ?)");
            $st->execute(array($loginV, password_hash($pass1, PASSWORD_DEFAULT), $nameV, $lang));
            session_regenerate_id(true);
            $_SESSION['uid'] = (int)db()->lastInsertId();
            flash_set('ok', 'ok_admin_created');
            redirect('?p=home');
            break;

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
            $loginV = trim((string)(isset($_POST['login']) ? $_POST['login'] : ''));
            $nameV  = trim((string)(isset($_POST['name']) ? $_POST['name'] : ''));
            $cityV  = mb_substr(trim((string)(isset($_POST['city']) ? $_POST['city'] : '')), 0, 64);
            $pass1  = (string)(isset($_POST['password']) ? $_POST['password'] : '');
            $pass2  = (string)(isset($_POST['password2']) ? $_POST['password2'] : '');
            $err = validate_credentials($loginV, $nameV, $pass1, $pass2, true);
            if ($err !== null) {
                flash_set('err', $err);
                redirect('?p=register');
            }
            $st = db()->prepare('INSERT INTO users (login, pass_hash, name, city, lang) VALUES (?, ?, ?, ?, ?)');
            $st->execute(array($loginV, password_hash($pass1, PASSWORD_DEFAULT), $nameV, $cityV, $lang));
            session_regenerate_id(true);
            $_SESSION['uid'] = (int)db()->lastInsertId();
            flash_set('ok', 'ok_registered');
            redirect('?p=home');
            break;

        case 'login':
            if ($user !== null) {
                redirect('?p=home');
            }
            if (!rate_limit('login', 10, 600)) {
                flash_set('err', 'err_rate');
                redirect('?p=login');
            }
            $loginV = trim((string)(isset($_POST['login']) ? $_POST['login'] : ''));
            $pass1  = (string)(isset($_POST['password']) ? $_POST['password'] : '');
            $st = db()->prepare('SELECT * FROM users WHERE login = ?');
            $st->execute(array($loginV));
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
            break;

        case 'logout':
            $_SESSION = array();
            if (ini_get('session.use_cookies')) {
                codetj_setcookie(session_name(), '', time() - 42000);
            }
            session_destroy();
            redirect('?p=home');
            break;

        case 'setlang':
            $newLang = (isset($_POST['lang']) && $_POST['lang'] === 'ru') ? 'ru' : 'tj';
            codetj_setcookie('codetj_lang', $newLang, time() + 31536000);
            if ($user !== null) {
                db()->prepare('UPDATE users SET lang = ? WHERE id = ?')->execute(array($newLang, (int)$user['id']));
            }
            redirect(safe_back());
            break;

        case 'settheme':
            $newTheme = (isset($_POST['theme']) && $_POST['theme'] === 'light') ? 'light' : 'dark';
            if ($user !== null) {
                db()->prepare('UPDATE users SET theme = ? WHERE id = ?')->execute(array($newTheme, (int)$user['id']));
            }
            json_out(array('ok' => true));
            break;

        case 'savedraft':
            if ($user === null) {
                json_out(array('ok' => false, 'err' => 'auth'), 403);
            }
            $lid = (int)(isset($_POST['lesson_id']) ? $_POST['lesson_id'] : 0);
            if ($lid < 1) {
                json_out(array('ok' => false, 'err' => 'lesson'), 400);
            }
            $cut = function ($v) {
                return mb_substr((string)$v, 0, 60000);
            };
            $st = db()->prepare(
                'INSERT INTO drafts (user_id, lesson_id, html_code, css_code, js_code, pasted)
                 VALUES (?,?,?,?,?,?)
                 ON DUPLICATE KEY UPDATE html_code=VALUES(html_code), css_code=VALUES(css_code),
                 js_code=VALUES(js_code), pasted=GREATEST(pasted, VALUES(pasted))'
            );
            $st->execute(array(
                (int)$user['id'], $lid,
                $cut(isset($_POST['html']) ? $_POST['html'] : ''),
                $cut(isset($_POST['css']) ? $_POST['css'] : ''),
                $cut(isset($_POST['js']) ? $_POST['js'] : ''),
                (isset($_POST['pasted']) && $_POST['pasted'] === '1') ? 1 : 0,
            ));
            json_out(array('ok' => true));
            break;

        case 'test':
            if ($user === null) {
                redirect('?p=login');
            }
            handle_test_submit((int)$user['id']);
            break;

        default:
            redirect('?p=home');
    }
}

/**
 * Тестро дар сервер месанҷад. Ҷавобҳои дуруст ҳеҷ гоҳ ба браузер намераванд.
 * 10 балл аз кӯшиши аввал, 5 балл аз дуюм, баъдтар — 0.
 */
function handle_test_submit($uid)
{
    $lid = (int)(isset($_POST['lesson_id']) ? $_POST['lesson_id'] : 0);
    $st = db()->prepare('SELECT * FROM lessons WHERE id = ? AND published = 1');
    $st->execute(array($lid));
    $L = $st->fetch();
    if (!$L) {
        redirect('?p=home');
    }

    $st = db()->prepare('SELECT * FROM questions WHERE lesson_id = ? ORDER BY num ASC, id ASC');
    $st->execute(array($lid));
    $questions = $st->fetchAll();
    if (!$questions) {
        redirect('?p=lesson&id=' . $lid);
    }

    $answers = isset($_POST['a']) && is_array($_POST['a']) ? $_POST['a'] : array();
    if (count($answers) < count($questions)) {
        $_SESSION['test_err'] = 'test_need_all';
        redirect('?p=lesson&id=' . $lid . '#test');
    }

    $pdo = db();
    $correctCnt = 0;
    $gained = 0;
    $detail = array();

    foreach ($questions as $q) {
        $qid = (int)$q['id'];
        $given = isset($answers[$qid]) ? (int)$answers[$qid] : -1;
        $isRight = ($given === (int)$q['correct']);

        $st = $pdo->prepare('SELECT attempts, correct, points FROM test_answers WHERE user_id = ? AND question_id = ?');
        $st->execute(array($uid, $qid));
        $prev = $st->fetch();
        $attempts = $prev ? (int)$prev['attempts'] : 0;
        $alreadyRight = $prev ? (int)$prev['correct'] === 1 : false;

        $award = 0;
        if ($isRight && !$alreadyRight) {
            if ($attempts === 0) {
                $award = 10;
            } elseif ($attempts === 1) {
                $award = 5;
            }
        }
        $attempts++;
        if ($isRight) {
            $correctCnt++;
        }
        $gained += $award;

        $pdo->prepare(
            'INSERT INTO test_answers (user_id, question_id, attempts, correct, points)
             VALUES (?,?,?,?,?)
             ON DUPLICATE KEY UPDATE attempts=VALUES(attempts),
             correct=GREATEST(correct, VALUES(correct)), points=points+VALUES(points)'
        )->execute(array($uid, $qid, $attempts, $isRight ? 1 : 0, $award));

        // Ҷавоби дурустро танҳо он вақт нишон медиҳем, ки шогирд ё дуруст
        // ҷавоб додааст, ё ҳар ду кӯшишро сарф кардааст. Вагарна кӯшиши
        // дуюм ройгон мешуд: як бор нодуруст фиристодан ва ҷавобро дидан.
        $reveal = $isRight || $attempts >= 2;
        $detail[] = array(
            'id'      => $qid,
            'right'   => $isRight,
            'given'   => $given,
            'reveal'  => $reveal,
            'correct' => $reveal ? (int)$q['correct'] : -1,
        );
    }

    $total = count($questions);
    $score = $total > 0 ? (int)round($correctCnt / $total * 100) : 0;
    $passed = $score >= 60;

    if ($gained > 0) {
        add_points($uid, $gained, 'test');
    }

    // Пешрафти дарс
    $st = $pdo->prepare('SELECT * FROM progress WHERE user_id = ? AND lesson_id = ?');
    $st->execute(array($uid, $lid));
    $pr = $st->fetch();
    $wasCompleted = $pr ? (int)$pr['completed'] === 1 : false;
    $prevAttempts = $pr ? (int)$pr['test_attempts'] : 0;
    $bestScore = $pr ? max((int)$pr['test_score'], $score) : $score;

    // Санҷиши AI ҳанӯз фаъол нест (Қисми 3). То он вақт дарс бо тест ҳисоб мешавад.
    $aiReady = trim((string)setting_get('openai_key', '')) !== '' || OPENAI_KEY !== '';
    $aiPassed = $pr ? (int)$pr['ai_passed'] === 1 : false;
    $completed = $passed && (!$aiReady || $aiPassed);

    $bonus = 0;
    if ($completed && !$wasCompleted) {
        if ($prevAttempts === 0 && $score === 100) {
            $bonus = 50;   // аз кӯшиши аввал бе хато
            add_points($uid, $bonus, 'first_try');
        }
    }

    $pdo->prepare(
        'INSERT INTO progress (user_id, lesson_id, test_score, test_attempts, completed, completed_at, points_earned, first_try)
         VALUES (?,?,?,?,?,?,?,?)
         ON DUPLICATE KEY UPDATE test_score=GREATEST(test_score, VALUES(test_score)),
         test_attempts=test_attempts+1,
         completed=GREATEST(completed, VALUES(completed)),
         completed_at=IF(completed_at IS NULL AND VALUES(completed)=1, NOW(), completed_at),
         points_earned=points_earned+VALUES(points_earned)'
    )->execute(array(
        $uid, $lid, $bestScore, 1, $completed ? 1 : 0,
        $completed ? date('Y-m-d H:i:s') : null,
        $gained + $bonus,
        ($prevAttempts === 0 && $score === 100) ? 1 : 0,
    ));

    $_SESSION['test_result'] = array(
        'lesson_id' => $lid,
        'score'     => $score,
        'correct'   => $correctCnt,
        'total'     => $total,
        'passed'    => $passed,
        'gained'    => $gained + $bonus,
        'completed' => $completed,
        'newly'     => $completed && !$wasCompleted,
        'detail'    => $detail,
    );
    redirect('?p=lesson&id=' . $lid . '#test');
}

/* ============================================================
 *  РОУТИНГИ GET
 * ============================================================ */

switch ($p) {
    case 'home':     page_home(); break;
    case 'login':    $user === null ? page_login() : redirect('?p=home'); break;
    case 'register': $user === null ? page_register() : redirect('?p=home'); break;
    case 'setup':    page_setup(); break;
    case 'course':   page_course(); break;
    case 'lesson':   page_lesson(); break;
    case 'profile':  $user !== null ? page_profile() : redirect('?p=login'); break;
    default:         page_404();
}
exit;

/* ============================================================
 *  САҲИФАҲО
 * ============================================================ */

function page_home()
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

function render_hero_guest()
{
    $ready = (int)db()->query('SELECT COUNT(*) FROM lessons WHERE published = 1')->fetchColumn();
    ?>
    <section class="hero">
      <h1><?= e(t('tagline')) ?></h1>
      <p class="hero-sub"><?= e(t('hero_text')) ?></p>
      <div class="hero-actions">
        <a class="btn btn-primary btn-lg" href="?p=register"><?= e(t('start_free')) ?></a>
        <a class="btn btn-ghost" href="?p=login"><?= e(t('have_account')) ?></a>
      </div>
      <div class="hero-stats">
        <div class="hstat"><b><?= $ready ?></b><span><?= e(t('stat_lessons')) ?></span></div>
        <div class="hstat"><b>100%</b><span><?= e(t('stat_free')) ?></span></div>
        <div class="hstat"><b>ТҶ</b><span><?= e(t('stat_lang')) ?></span></div>
      </div>
    </section>
    <section class="why">
      <h2><?= e(t('why_title')) ?></h2>
      <div class="why-grid">
        <div class="why-card"><div class="why-ic">&#128483;</div><h3><?= e(t('why_1_t')) ?></h3><p><?= e(t('why_1_d')) ?></p></div>
        <div class="why-card"><div class="why-ic">&#128187;</div><h3><?= e(t('why_2_t')) ?></h3><p><?= e(t('why_2_d')) ?></p></div>
        <div class="why-card"><div class="why-ic">&#129517;</div><h3><?= e(t('why_3_t')) ?></h3><p><?= e(t('why_3_d')) ?></p></div>
        <div class="why-card"><div class="why-ic">&#127942;</div><h3><?= e(t('why_4_t')) ?></h3><p><?= e(t('why_4_d')) ?></p></div>
      </div>
    </section>
    <?php
    render_course_cards(null);
}

function render_dashboard()
{
    global $user;
    ?>
    <section class="dash-head">
      <h1><?= e(t('welcome')) ?>, <?= e($user['name']) ?>! &#128075;</h1>
      <div class="dash-stats">
        <span class="chip">&#11088; <?= (int)$user['points'] ?> <?= e(t('points')) ?></span>
        <span class="chip">&#128293; <?= (int)$user['streak_days'] ?> <?= e(t('streak')) ?></span>
      </div>
    </section>
    <h2 class="sec-title"><?= e(t('home_title')) ?></h2>
    <?php
    render_course_cards((int)$user['id']);
}

/** Кортҳои 4 курс. */
function render_course_cards($userId)
{
    $fullOpen = $userId !== null ? full_course_unlocked($userId) : false;
    $counts = array();
    foreach (db()->query('SELECT course, COUNT(*) c FROM lessons WHERE published = 1 GROUP BY course') as $r) {
        $counts[$r['course']] = (int)$r['c'];
    }
    ?>
    <section class="courses-grid">
    <?php foreach (courses() as $slug => $c):
        $locked = ($slug === 'full') && ($userId === null || !$fullOpen);
        $done = $userId !== null ? course_done_count($userId, $slug) : 0;
        $ready = isset($counts[$slug]) ? $counts[$slug] : 0;
        $pct = (int)round($done / LESSONS_PER_COURSE * 100);
        ?>
        <div class="course-card <?= $locked ? 'is-locked' : '' ?>" style="--cc:<?= e($c['color']) ?>">
          <div class="cc-top">
            <span class="cc-icon"><?= $c['icon'] ?></span>
            <span class="cc-name"><?= e(fld('name', $c)) ?></span>
            <?php if ($locked): ?><span class="cc-lock">&#128274;</span><?php endif; ?>
          </div>
          <p class="cc-desc"><?= e(fld('desc', $c)) ?></p>
          <div class="cc-meta">
            <?= e(t('lessons_50')) ?> &middot; <?= e(t('levels_5')) ?>
            <?php if ($ready > 0 && $ready < LESSONS_PER_COURSE): ?>
              &middot; <?= $ready ?> <?= e(t('done_word') === 'пройдено' ? 'готово' : 'тайёр') ?>
            <?php endif; ?>
          </div>
          <?php if ($userId !== null && !$locked): ?>
            <div class="cc-bar"><div class="cc-bar-in" style="width:<?= $pct ?>%"></div></div>
            <div class="cc-progress"><?= $done ?> <?= e(t('of')) ?> <?= LESSONS_PER_COURSE ?> <?= e(t('done_word')) ?></div>
          <?php endif; ?>
          <?php if ($locked): ?>
            <p class="cc-hint"><?= e(t('full_locked_hint')) ?></p>
          <?php else: ?>
            <a class="btn btn-course" href="?p=course&c=<?= e($slug) ?>">
              <?= e(($userId !== null && $done > 0) ? t('continue') : t('open_course')) ?> &rarr;
            </a>
          <?php endif; ?>
        </div>
    <?php endforeach; ?>
    </section>
    <?php
}

function render_top3()
{
    $rows = db()->query(
        "SELECT name, city, points FROM users WHERE banned = 0 AND points > 0
         ORDER BY points DESC, id ASC LIMIT 3"
    )->fetchAll();
    $medals = array('&#129351;', '&#129352;', '&#129353;');
    ?>
    <section class="top3">
      <h2 class="sec-title"><?= e(t('top_students')) ?></h2>
      <?php if (!$rows): ?>
        <p class="muted"><?= e(t('no_students')) ?></p>
      <?php else: ?>
        <div class="top3-grid">
        <?php foreach ($rows as $i => $r): ?>
          <div class="top3-card">
            <div class="top3-medal"><?= $medals[$i] ?></div>
            <div class="top3-name"><?= e($r['name']) ?></div>
            <?php if ($r['city'] !== ''): ?><div class="top3-city"><?= e($r['city']) ?></div><?php endif; ?>
            <div class="top3-pts">&#11088; <?= (int)$r['points'] ?></div>
          </div>
        <?php endforeach; ?>
        </div>
      <?php endif; ?>
    </section>
    <?php
}

function page_login()
{
    render_header(t('login'));
    ?>
    <section class="auth-box">
      <h1><?= e(t('login')) ?></h1>
      <form method="post" action="index.php">
        <?= csrf_field() ?>
        <input type="hidden" name="action" value="login">
        <label><?= e(t('username')) ?><input type="text" name="login" required maxlength="32" autocomplete="username"></label>
        <label><?= e(t('password')) ?><input type="password" name="password" required autocomplete="current-password"></label>
        <button class="btn btn-primary btn-block" type="submit"><?= e(t('do_login')) ?></button>
      </form>
      <p class="auth-alt"><a href="?p=register"><?= e(t('no_account')) ?></a></p>
    </section>
    <?php
    render_footer();
}

function page_register()
{
    render_header(t('register'));
    ?>
    <section class="auth-box">
      <h1><?= e(t('register')) ?></h1>
      <form method="post" action="index.php">
        <?= csrf_field() ?>
        <input type="hidden" name="action" value="register">
        <label><?= e(t('name')) ?><input type="text" name="name" required maxlength="64"></label>
        <label><?= e(t('city')) ?><input type="text" name="city" maxlength="64" placeholder="<?= e(t('city_ph')) ?>"></label>
        <label><?= e(t('username')) ?><input type="text" name="login" required maxlength="32" pattern="[a-zA-Z0-9_]{3,32}" placeholder="<?= e(t('login_ph')) ?>" autocomplete="username"></label>
        <label><?= e(t('password')) ?><input type="password" name="password" required minlength="6" autocomplete="new-password"></label>
        <label><?= e(t('password2')) ?><input type="password" name="password2" required minlength="6" autocomplete="new-password"></label>
        <button class="btn btn-primary btn-block" type="submit"><?= e(t('do_register')) ?></button>
      </form>
      <p class="auth-alt"><a href="?p=login"><?= e(t('have_account')) ?></a></p>
    </section>
    <?php
    render_footer();
}

function page_setup()
{
    render_header(t('setup_title'));
    ?>
    <section class="auth-box">
      <h1>&#128736; <?= e(t('setup_title')) ?></h1>
      <p class="muted"><?= e(t('setup_note')) ?></p>
      <form method="post" action="index.php">
        <?= csrf_field() ?>
        <input type="hidden" name="action" value="setup">
        <label><?= e(t('name')) ?><input type="text" name="name" required maxlength="64"></label>
        <label><?= e(t('username')) ?><input type="text" name="login" required maxlength="32" pattern="[a-zA-Z0-9_]{3,32}" placeholder="<?= e(t('login_ph')) ?>" autocomplete="username"></label>
        <label><?= e(t('password')) ?><input type="password" name="password" required minlength="6" autocomplete="new-password"></label>
        <label><?= e(t('password2')) ?><input type="password" name="password2" required minlength="6" autocomplete="new-password"></label>
        <button class="btn btn-primary btn-block" type="submit"><?= e(t('create_admin')) ?></button>
      </form>
    </section>
    <?php
    render_footer();
}

/** Харитаи дарсҳои курс. */
function page_course()
{
    global $user, $lang;
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
        redirect('?p=home');
    }
    $c = $all[$slug];
    $uid = (int)$user['id'];

    $st = db()->prepare('SELECT id, num, title_tj, title_ru FROM lessons WHERE course = ? AND published = 1');
    $st->execute(array($slug));
    $lessons = array();
    foreach ($st->fetchAll() as $row) {
        $lessons[(int)$row['num']] = $row;
    }
    $doneMap = course_done_map($uid, $slug);
    $doneCnt = count($doneMap);
    $pct = (int)round($doneCnt / LESSONS_PER_COURSE * 100);

    render_header(fld('name', $c));
    ?>
    <section class="course-head" style="--cc:<?= e($c['color']) ?>">
      <a class="back-link" href="?p=home">&larr; <?= e(t('back')) ?></a>
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
            <h2><?= $unlocked ? '&#128215;' : '&#128274;' ?> <?= e(t('level')) ?> <?= $lvl ?> &mdash; <?= e(isset($lname[$lang]) ? $lname[$lang] : $lname['tj']) ?></h2>
            <span class="level-range"><?= e(t('lesson')) ?> <?= $from ?>&ndash;<?= $to ?></span>
          </div>
          <?php if (!$unlocked): ?>
            <p class="muted"><?= e(t('level_locked_hint')) ?></p>
          <?php endif; ?>
          <div class="lesson-map">
            <?php for ($n = $from; $n <= $to; $n++):
                $L = isset($lessons[$n]) ? $lessons[$n] : null;
                $isDone = isset($doneMap[$n]);
                $title = $L !== null ? fld('title', $L) : t('lesson_not_ready');
                if ($unlocked && $L !== null): ?>
                  <a class="lcell <?= $isDone ? 'done' : 'open' ?>" href="?p=lesson&id=<?= (int)$L['id'] ?>" title="<?= e($title) ?>">
                    <span class="lnum"><?= $isDone ? '&check;' : $n ?></span>
                  </a>
                <?php else: ?>
                  <span class="lcell <?= $unlocked ? 'soon' : 'lock' ?>" title="<?= e($title) ?>">
                    <span class="lnum"><?= $unlocked ? $n : '&#128274;' ?></span>
                  </span>
                <?php endif;
            endfor; ?>
          </div>
        </section>
    <?php endforeach; ?>
    <?php
    render_footer();
}

/** Саҳифаи дарс: назария → амалия (муҳаррир) → тест. */
function page_lesson()
{
    global $user;
    if ($user === null) {
        flash_set('err', 'err_need_login');
        redirect('?p=login');
    }
    $id = (int)(isset($_GET['id']) ? $_GET['id'] : 0);
    $st = db()->prepare('SELECT * FROM lessons WHERE id = ? AND published = 1');
    $st->execute(array($id));
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
    $courseList = courses();
    $c = $courseList[$slug];

    // сиёҳнавис
    $st = db()->prepare('SELECT * FROM drafts WHERE user_id = ? AND lesson_id = ?');
    $st->execute(array($uid, $id));
    $draft = $st->fetch();

    $startCode = (string)$L['task_start_code'];
    $htmlCode = $draft ? (string)$draft['html_code'] : $startCode;
    $cssCode  = $draft ? (string)$draft['css_code'] : '';
    $jsCode   = $draft ? (string)$draft['js_code'] : '';
    if (!$draft && $startCode === '') {
        $htmlCode = (string)$L['example_code'];
    }

    // саволҳо (бе ҷавоби дуруст!)
    $st = db()->prepare('SELECT id, num, q_tj, q_ru, options_tj, options_ru, explain_tj, explain_ru FROM questions WHERE lesson_id = ? ORDER BY num ASC, id ASC');
    $st->execute(array($id));
    $questions = $st->fetchAll();

    $result = null;
    if (isset($_SESSION['test_result']) && (int)$_SESSION['test_result']['lesson_id'] === $id) {
        $result = $_SESSION['test_result'];
        unset($_SESSION['test_result']);
    }
    $testErr = null;
    if (isset($_SESSION['test_err'])) {
        $testErr = $_SESSION['test_err'];
        unset($_SESSION['test_err']);
    }

    // дарси навбатӣ
    $st = db()->prepare('SELECT id FROM lessons WHERE course = ? AND num = ? AND published = 1');
    $st->execute(array($slug, $num + 1));
    $nextId = (int)$st->fetchColumn();

    render_header(fld('title', $L));
    ?>
    <section class="lesson-page" style="--cc:<?= e($c['color']) ?>">
      <a class="back-link" href="?p=course&c=<?= e($slug) ?>">&larr; <?= e(t('back')) ?></a>
      <h1><span class="lesson-tag"><?= e(fld('name', $c)) ?> &middot; <?= e(t('lesson')) ?> <?= $num ?></span><br><?= e(fld('title', $L)) ?></h1>

      <div class="lesson-block">
        <h2>&#128214; <?= e(t('theory')) ?></h2>
        <div class="theory-body">
          <?= fld('theory', $L) !== '' ? fld('theory', $L) : '<p class="muted">' . e(t('lesson_not_ready')) . '</p>' ?>
        </div>
      </div>

      <?php if ((string)$L['example_code'] !== ''): ?>
      <div class="lesson-block">
        <h2>&#128161; <?= e(t('example')) ?></h2>
        <pre class="code-view"><code id="exampleCode"><?= e((string)$L['example_code']) ?></code></pre>
        <button class="btn btn-ghost btn-sm" id="loadExample"><?= e(t('open_in_editor')) ?></button>
      </div>
      <?php endif; ?>

      <?php if (fld('task_text', $L) !== ''): ?>
      <div class="lesson-block">
        <h2>&#9997;&#65039; <?= e(t('task')) ?></h2>
        <div class="theory-body"><?= fld('task_text', $L) ?></div>
      </div>
      <?php endif; ?>

      <div class="lesson-block" id="practice">
        <h2>&#128187; <?= e(t('practice')) ?></h2>
        <?php render_editor($id, $htmlCode, $cssCode, $jsCode, $startCode); ?>
      </div>

      <?php if ($questions): ?>
        <div class="lesson-block" id="test">
          <h2>&#128221; <?= e(t('test')) ?></h2>
          <?php render_test($id, $questions, $result, $testErr, $nextId); ?>
        </div>
      <?php endif; ?>
    </section>
    <?php
    render_footer();
}

/** Муҳаррири код бо се ҷадвалак ва пешнамоиши зинда. */
function render_editor($lessonId, $html, $css, $js, $startCode)
{
    ?>
    <div class="editor-wrap" id="edWrap">
      <div class="ed-toolbar">
        <div class="ed-tabs">
          <button class="ed-tab act" data-pane="html">HTML</button>
          <button class="ed-tab" data-pane="css">CSS</button>
          <button class="ed-tab" data-pane="js">JS</button>
        </div>
        <div class="ed-actions">
          <button class="ed-btn" id="btnRun">&#9654; <?= e(t('run')) ?></button>
          <button class="ed-btn" id="btnSave"><?= e(t('save')) ?></button>
          <button class="ed-btn" id="btnReset"><?= e(t('reset')) ?></button>
          <button class="ed-btn" id="btnFull">&#9974;</button>
        </div>
      </div>

      <div class="ed-mobile-switch">
        <button class="ms-btn act" data-view="code"><?= e(t('code')) ?></button>
        <button class="ms-btn" data-view="preview"><?= e(t('preview')) ?></button>
      </div>

      <div class="ed-body">
        <div class="ed-code" id="edCode">
          <textarea id="ta_html" class="ed-area" spellcheck="false"><?= e($html) ?></textarea>
          <textarea id="ta_css" class="ed-area hidden" spellcheck="false"><?= e($css) ?></textarea>
          <textarea id="ta_js" class="ed-area hidden" spellcheck="false"><?= e($js) ?></textarea>
        </div>
        <div class="ed-preview" id="edPreview">
          <iframe id="edFrame" sandbox="allow-scripts allow-modals" title="preview"></iframe>
        </div>
      </div>

      <div class="ed-status">
        <span id="edSaveState" class="muted"></span>
        <span id="edErr" class="ed-err"></span>
      </div>
    </div>

    <script>
    (function () {
      var LESSON_ID = <?= (int)$lessonId ?>;
      var START = <?= json_encode((string)$startCode, JSON_UNESCAPED_UNICODE) ?>;
      var TXT = {
        saved: <?= json_encode(t('saved'), JSON_UNESCAPED_UNICODE) ?>,
        saving: <?= json_encode(t('saving'), JSON_UNESCAPED_UNICODE) ?>,
        saveErr: <?= json_encode(t('save_err'), JSON_UNESCAPED_UNICODE) ?>
      };
      var csrfEl = document.querySelector('input[name="csrf"]');
      var CSRF = csrfEl ? csrfEl.value : '';

      var areas = {
        html: document.getElementById('ta_html'),
        css: document.getElementById('ta_css'),
        js: document.getElementById('ta_js')
      };
      var frame = document.getElementById('edFrame');
      var errBox = document.getElementById('edErr');
      var saveState = document.getElementById('edSaveState');
      var pasted = false;
      var timer = null;

      function val(k) { return areas[k] ? areas[k].value : ''; }

      function build() {
        var h = val('html'), c = val('css'), j = val('js');
        // агар ученик саҳифаи пурра нанавишта бошад — худамон печонем
        var doc = h;
        if (h.toLowerCase().indexOf('<html') === -1) {
          doc = '<!doctype html><html><head><meta charset="utf-8">'
              + '<meta name="viewport" content="width=device-width,initial-scale=1">'
              + '<style>body{font-family:system-ui,sans-serif;padding:12px;line-height:1.6}</style>'
              + '<style>' + c + '</style></head><body>' + h + '</body></html>';
        } else if (c) {
          doc = doc.replace(/<\/head>/i, '<style>' + c + '</style></head>');
        }
        if (j) {
          var script = '<script>window.onerror=function(m,s,l){parent.postMessage({codetjErr:m,line:l},"*");return true;};try{'
                     + j + '\n}catch(e){parent.postMessage({codetjErr:e.message},"*");}<\/script>';
          if (doc.toLowerCase().indexOf('</body>') !== -1) {
            doc = doc.replace(/<\/body>/i, script + '</body>');
          } else {
            doc += script;
          }
        }
        return doc;
      }

      function run() {
        errBox.textContent = '';
        frame.srcdoc = build();
      }

      window.addEventListener('message', function (ev) {
        if (ev.data && ev.data.codetjErr) {
          errBox.textContent = 'JS: ' + ev.data.codetjErr + (ev.data.line ? ' (сатри ' + ev.data.line + ')' : '');
        }
      });

      function schedule() {
        if (timer) { clearTimeout(timer); }
        timer = setTimeout(run, 600);
      }

      Object.keys(areas).forEach(function (k) {
        if (!areas[k]) { return; }
        areas[k].addEventListener('input', schedule);
        areas[k].addEventListener('paste', function () { pasted = true; });
        // Tab дар textarea — фосила, на гузариш ба тугмаи дигар
        areas[k].addEventListener('keydown', function (ev) {
          if (ev.key === 'Tab') {
            ev.preventDefault();
            var s = this.selectionStart, e2 = this.selectionEnd;
            this.value = this.value.substring(0, s) + '  ' + this.value.substring(e2);
            this.selectionStart = this.selectionEnd = s + 2;
            schedule();
          }
        });
      });

      // ҷадвалакҳои HTML / CSS / JS
      var tabs = document.querySelectorAll('.ed-tab');
      for (var i = 0; i < tabs.length; i++) {
        tabs[i].addEventListener('click', function () {
          for (var j2 = 0; j2 < tabs.length; j2++) { tabs[j2].classList.remove('act'); }
          this.classList.add('act');
          var pane = this.getAttribute('data-pane');
          Object.keys(areas).forEach(function (k) {
            if (areas[k]) { areas[k].classList.toggle('hidden', k !== pane); }
          });
        });
      }

      // дар телефон: код ё натиҷа
      var msBtns = document.querySelectorAll('.ms-btn');
      var wrap = document.getElementById('edWrap');
      for (var m = 0; m < msBtns.length; m++) {
        msBtns[m].addEventListener('click', function () {
          for (var n = 0; n < msBtns.length; n++) { msBtns[n].classList.remove('act'); }
          this.classList.add('act');
          wrap.setAttribute('data-view', this.getAttribute('data-view'));
          if (this.getAttribute('data-view') === 'preview') { run(); }
        });
      }

      document.getElementById('btnRun').addEventListener('click', run);
      document.getElementById('btnFull').addEventListener('click', function () {
        wrap.classList.toggle('is-full');
        document.body.classList.toggle('no-scroll', wrap.classList.contains('is-full'));
        run();
      });
      document.getElementById('btnReset').addEventListener('click', function () {
        if (areas.html) { areas.html.value = START; }
        if (areas.css) { areas.css.value = ''; }
        if (areas.js) { areas.js.value = ''; }
        run();
      });

      function save(silent) {
        if (!CSRF) { return; }
        if (!silent) { saveState.textContent = TXT.saving; }
        var fd = new FormData();
        fd.append('action', 'savedraft');
        fd.append('csrf', CSRF);
        fd.append('lesson_id', LESSON_ID);
        fd.append('html', val('html'));
        fd.append('css', val('css'));
        fd.append('js', val('js'));
        fd.append('pasted', pasted ? '1' : '0');
        fetch('index.php', { method: 'POST', body: fd, credentials: 'same-origin' })
          .then(function (r) { return r.json(); })
          .then(function (d) { saveState.textContent = d && d.ok ? TXT.saved : TXT.saveErr; })
          .catch(function () { saveState.textContent = TXT.saveErr; });
      }
      document.getElementById('btnSave').addEventListener('click', function () { save(false); });
      setInterval(function () { save(true); }, 20000);   // автозахира ҳар 20 сония

      var loadEx = document.getElementById('loadExample');
      if (loadEx) {
        loadEx.addEventListener('click', function () {
          var ex = document.getElementById('exampleCode');
          if (ex && areas.html) {
            areas.html.value = ex.textContent;
            run();
            document.getElementById('practice').scrollIntoView({ behavior: 'smooth' });
          }
        });
      }

      run();
    })();
    </script>
    <?php
}

/** Тест: 5 савол. Ҷавобҳои дуруст дар сервер мемонанд. */
function render_test($lessonId, $questions, $result, $testErr, $nextId)
{
    global $lang;
    $detail = array();
    if ($result !== null) {
        foreach ($result['detail'] as $d) {
            $detail[(int)$d['id']] = $d;
        }
    }
    ?>
    <?php if ($result !== null): ?>
      <div class="test-result <?= $result['passed'] ? 'ok' : 'bad' ?>">
        <div class="tr-score"><?= (int)$result['score'] ?>%</div>
        <div>
          <b><?= e($result['passed'] ? t('test_passed') : t('test_failed')) ?></b>
          <div class="muted"><?= (int)$result['correct'] ?>/<?= (int)$result['total'] ?> &middot;
            <?= e(t('you_got')) ?> +<?= (int)$result['gained'] ?> <?= e(t('points')) ?></div>
        </div>
      </div>
      <?php if (!empty($result['newly'])): ?>
        <div class="lesson-done">
          <b>&#127881; <?= e(t('lesson_done')) ?></b>
          <p class="muted"><?= e(t('lesson_done_txt')) ?></p>
          <?php if ($nextId > 0): ?>
            <a class="btn btn-primary" href="?p=lesson&id=<?= (int)$nextId ?>"><?= e(t('next_lesson')) ?> &rarr;</a>
          <?php endif; ?>
        </div>
      <?php endif; ?>
    <?php else: ?>
      <p class="muted"><?= e(t('test_intro')) ?></p>
    <?php endif; ?>

    <?php if ($testErr !== null): ?>
      <div class="flash flash-err"><?= e(t($testErr)) ?></div>
    <?php endif; ?>

    <form method="post" action="index.php" class="test-form">
      <?= csrf_field() ?>
      <input type="hidden" name="action" value="test">
      <input type="hidden" name="lesson_id" value="<?= (int)$lessonId ?>">

      <?php foreach ($questions as $qi => $q):
          $qid = (int)$q['id'];
          $optRaw = $lang === 'ru' ? $q['options_ru'] : $q['options_tj'];
          $opts = json_decode((string)$optRaw, true);
          if (!is_array($opts)) {
              $opts = array();
          }
          // тартиби вариантҳо омехта мешавад, вале қиммати аслӣ нигоҳ дошта мешавад
          $order = array_keys($opts);
          shuffle($order);
          $d = isset($detail[$qid]) ? $detail[$qid] : null;
          ?>
          <div class="q-block <?= $d ? ($d['right'] ? 'q-ok' : 'q-bad') : '' ?>">
            <div class="q-title"><span class="q-num"><?= $qi + 1 ?></span> <?= e($lang === 'ru' ? $q['q_ru'] : $q['q_tj']) ?></div>
            <div class="q-opts">
              <?php foreach ($order as $oi):
                  $checked = ($d !== null && (int)$d['given'] === (int)$oi);
                  $isCorrect = ($d !== null && (int)$d['correct'] === (int)$oi);
                  ?>
                  <label class="q-opt <?= $isCorrect ? 'is-correct' : '' ?> <?= ($checked && !$isCorrect) ? 'is-wrong' : '' ?>">
                    <input type="radio" name="a[<?= $qid ?>]" value="<?= (int)$oi ?>" <?= $checked ? 'checked' : '' ?> required>
                    <span><?= e((string)$opts[$oi]) ?></span>
                  </label>
              <?php endforeach; ?>
            </div>
            <?php if ($d !== null):
                $ex = $lang === 'ru' ? $q['explain_ru'] : $q['explain_tj'];
                if (!empty($d['reveal']) && (string)$ex !== ''): ?>
                  <div class="q-explain"><?= $d['right'] ? '&#9989; ' : '&#128161; ' ?><?= e((string)$ex) ?></div>
                <?php elseif (!$d['right']): ?>
                  <div class="q-explain">&#128260; <?= e(t('try_once_more')) ?></div>
                <?php endif;
            endif; ?>
          </div>
      <?php endforeach; ?>

      <button class="btn btn-primary btn-block" type="submit">
        <?= e($result !== null ? t('test_again') : t('test_send')) ?>
      </button>
    </form>
    <?php
}

function page_profile()
{
    global $user;
    $uid = (int)$user['id'];
    $st = db()->prepare('SELECT COUNT(*) + 1 FROM users WHERE banned = 0 AND points > ?');
    $st->execute(array((int)$user['points']));
    $rank = (int)$st->fetchColumn();

    render_header(t('nav_profile'));
    ?>
    <section class="profile-head">
      <div class="avatar"><?= e(mb_strtoupper(mb_substr($user['name'], 0, 1))) ?></div>
      <div>
        <h1><?= e($user['name']) ?></h1>
        <?php if ($user['city'] !== ''): ?><p class="muted">&#128205; <?= e($user['city']) ?></p><?php endif; ?>
        <div class="dash-stats">
          <span class="chip">&#11088; <?= (int)$user['points'] ?> <?= e(t('points')) ?></span>
          <span class="chip">&#128293; <?= (int)$user['streak_days'] ?> <?= e(t('streak')) ?></span>
          <span class="chip">&#127941; <?= e(t('rank')) ?>: <?= $rank ?></span>
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

function page_404()
{
    if (!headers_sent()) {
        http_response_code(404);
    }
    render_header('404');
    ?>
    <section class="auth-box" style="text-align:center">
      <h1 style="font-size:3rem">&#129335;</h1>
      <p><?= e(t('err_not_found')) ?></p>
      <a class="btn btn-primary" href="?p=home"><?= e(t('nav_home')) ?></a>
    </section>
    <?php
    render_footer();
}

/* ============================================================
 *  ҚОЛИБ
 * ============================================================ */

function render_header($title)
{
    global $user, $lang, $theme, $p;
    $backUrl = '?p=' . preg_replace('/[^a-z_]/', '', $p);
    if ($p === 'course' && isset($_GET['c']) && preg_match('/^[a-z]+$/', (string)$_GET['c'])) {
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
    <button id="themeBtn" class="icon-btn" title="<?= e(t('theme_toggle')) ?>"><?= $theme === 'light' ? '&#127769;' : '&#9728;&#65039;' ?></button>
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

function render_footer()
{
    ?>
</main>
<footer class="footer">
  <p><b>CodeTJ</b> &copy; <?= date('Y') ?> &middot; <?= e(t('footer_note')) ?></p>
</footer>
<script>
(function () {
  var btn = document.getElementById('themeBtn');
  if (!btn) { return; }
  btn.addEventListener('click', function () {
    var light = document.documentElement.classList.toggle('light');
    btn.innerHTML = light ? '&#127769;' : '&#9728;&#65039;';
    document.cookie = 'codetj_theme=' + (light ? 'light' : 'dark') + ';path=/;max-age=31536000;samesite=Lax';
    var csrf = document.querySelector('input[name="csrf"]');
    if (csrf) {
      var fd = new FormData();
      fd.append('action', 'settheme');
      fd.append('theme', light ? 'light' : 'dark');
      fd.append('csrf', csrf.value);
      fetch('index.php', { method: 'POST', body: fd, credentials: 'same-origin' }).catch(function () {});
    }
  });
})();
</script>
</body>
</html>
    <?php
}

function render_css()
{
    ?>
:root{
  --bg:#0b1120;--bg2:#111a2e;--card:#16223a;--line:#243350;
  --txt:#e7edf7;--muted:#8fa0bd;--accent:#38bdf8;--accent2:#818cf8;
  --ok:#22c55e;--err:#ef4444;--radius:16px;--shadow:0 10px 30px rgba(0,0,0,.35);
}
html.light{
  --bg:#f2f5fa;--bg2:#e8edf5;--card:#fff;--line:#dbe3ef;
  --txt:#17233b;--muted:#5b6b88;--shadow:0 8px 24px rgba(23,35,59,.10);
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Noto Sans',system-ui,-apple-system,'Segoe UI',Arial,sans-serif;background:var(--bg);color:var(--txt);
 min-height:100vh;display:flex;flex-direction:column;line-height:1.65;-webkit-font-smoothing:antialiased}
body.no-scroll{overflow:hidden}
a{color:var(--accent);text-decoration:none}
h1,h2,h3{line-height:1.3;font-weight:800}
.wrap{width:100%;max-width:1080px;margin:0 auto;padding:24px 16px;flex:1}
.hidden{display:none !important}

.topbar{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:16px;padding:10px 16px;
 background:var(--bg);border-bottom:1px solid var(--line)}
.logo{font-size:1.35rem;font-weight:800;color:var(--txt)}
.logo span{color:var(--accent)}
.topnav{display:flex;gap:4px;flex:1}
.topnav a{color:var(--muted);padding:6px 12px;border-radius:10px;font-weight:600;font-size:.95rem}
.topnav a.act,.topnav a:hover{color:var(--txt);background:var(--card)}
.topbar-right{display:flex;align-items:center;gap:8px}
.lang-form{display:flex;border:1px solid var(--line);border-radius:10px;overflow:hidden}
.lang-btn{background:transparent;border:0;color:var(--muted);padding:6px 10px;font-weight:700;cursor:pointer;font-size:.85rem}
.lang-btn.act{background:var(--accent);color:#04121f}
.icon-btn{background:transparent;border:1px solid var(--line);border-radius:10px;padding:5px 9px;cursor:pointer;font-size:1rem;color:var(--txt)}
.inline-form{display:inline}

.btn{display:inline-block;border:0;border-radius:12px;cursor:pointer;font-weight:700;font-family:inherit;
 font-size:1rem;padding:12px 22px;color:var(--txt);text-align:center}
.btn-primary{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#04121f}
html.light .btn-primary{color:#fff}
.btn-ghost{background:var(--card);border:1px solid var(--line)}
.btn-sm{padding:7px 14px;font-size:.9rem}
.btn-lg{padding:15px 30px;font-size:1.1rem}
.btn-block{width:100%}
.btn-course{background:var(--cc);color:#fff;padding:10px 18px;font-size:.95rem}

.flash{padding:13px 18px;border-radius:12px;margin-bottom:18px;font-weight:600}
.flash-ok{background:rgba(34,197,94,.18);border:1px solid var(--ok)}
.flash-err{background:rgba(239,68,68,.18);border:1px solid var(--err)}

.hero{text-align:center;padding:56px 8px 40px}
.hero h1{font-size:clamp(1.8rem,5.5vw,3.2rem);color:var(--accent)}
.hero-sub{max-width:620px;margin:16px auto 0;color:var(--muted);font-size:1.08rem}
.hero-actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:28px}
.hero-stats{display:flex;gap:14px;justify-content:center;flex-wrap:wrap;margin-top:40px}
.hstat{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:14px 26px;min-width:120px}
.hstat b{display:block;font-size:1.5rem;color:var(--accent)}
.hstat span{color:var(--muted);font-size:.85rem}

.why{padding:24px 0}
.why h2{text-align:center;margin-bottom:24px;font-size:1.6rem}
.why-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
.why-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px}
.why-ic{font-size:1.9rem;margin-bottom:8px}
.why-card h3{font-size:1.05rem;margin-bottom:6px}
.why-card p{color:var(--muted);font-size:.92rem}

.dash-head{padding:16px 0 4px}
.dash-head h1{font-size:clamp(1.4rem,4vw,2rem)}
.dash-stats{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.chip{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:6px 14px;font-size:.9rem;font-weight:600}
.sec-title{margin:28px 0 16px;font-size:1.35rem}

.courses-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;padding:8px 0 24px}
.course-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px;
 display:flex;flex-direction:column;gap:10px;border-top:3px solid var(--cc);box-shadow:var(--shadow)}
.course-card.is-locked{opacity:.75}
.cc-top{display:flex;align-items:center;gap:10px}
.cc-icon{font-size:1.6rem}
.cc-name{font-size:1.25rem;font-weight:800;flex:1}
.cc-desc{color:var(--muted);font-size:.92rem;flex:1}
.cc-meta{color:var(--muted);font-size:.8rem;font-weight:600;letter-spacing:.3px}
.cc-bar{height:8px;background:var(--bg2);border-radius:99px;overflow:hidden}
.cc-bar.big{height:12px;margin-top:14px}
.cc-bar-in{height:100%;background:var(--cc);border-radius:99px}
.cc-progress{color:var(--muted);font-size:.85rem}
.cc-hint{color:var(--muted);font-size:.85rem;background:var(--bg2);border-radius:10px;padding:10px 12px}

.top3{padding-bottom:24px}
.top3-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;max-width:640px}
.top3-card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px;text-align:center}
.top3-medal{font-size:2rem}
.top3-name{font-weight:800;margin-top:6px}
.top3-city{color:var(--muted);font-size:.85rem}
.top3-pts{margin-top:6px;font-weight:700;color:var(--accent)}

.course-head{padding:12px 0 8px}
.course-head h1{font-size:clamp(1.5rem,4.5vw,2.2rem);margin-top:10px}
.ch-icon{font-size:1.8rem}
.back-link{color:var(--muted);font-weight:600;font-size:.9rem}
.level-block{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:20px;margin-top:18px}
.level-block.is-locked{opacity:.6}
.level-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.level-head h2{font-size:1.15rem}
.level-range{color:var(--muted);font-size:.85rem;font-weight:600}
.lesson-map{display:grid;grid-template-columns:repeat(auto-fill,minmax(52px,1fr));gap:8px}
.lcell{aspect-ratio:1;display:flex;align-items:center;justify-content:center;border-radius:12px;
 background:var(--bg2);border:1px solid var(--line);font-weight:800;font-size:1rem;color:var(--muted)}
.lcell.open{color:var(--txt);border-color:var(--cc)}
.lcell.done{background:var(--cc);border-color:var(--cc);color:#fff}
.lcell.lock{opacity:.55;font-size:.8rem}
.lcell.soon{opacity:.45}

.lesson-page h1{font-size:clamp(1.3rem,4vw,1.9rem);margin:12px 0 6px}
.lesson-tag{display:inline-block;font-size:.78rem;font-weight:700;color:var(--cc);text-transform:uppercase}
.lesson-block{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px;margin-top:16px}
.lesson-block h2{font-size:1.1rem;margin-bottom:12px}
.theory-body p{margin:10px 0}
.theory-body h3{margin:18px 0 8px;font-size:1.02rem;color:var(--accent)}
.theory-body ul,.theory-body ol{padding-left:22px;margin:10px 0}
.theory-body li{margin:5px 0}
.theory-body code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.88em;background:var(--bg2);
 padding:2px 6px;border-radius:6px;color:var(--accent);word-break:break-word}
.theory-body pre{background:#0d1526;border:1px solid var(--line);border-radius:10px;padding:14px;
 overflow-x:auto;margin:12px 0}
.theory-body pre code{background:none;color:#c9d8f0;padding:0;white-space:pre}
.code-view{background:#0d1526;border:1px solid var(--line);border-radius:12px;padding:16px;overflow-x:auto;margin-bottom:12px}
.code-view code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.86rem;color:#c9d8f0;white-space:pre}

/* ---- муҳаррири код ---- */
.editor-wrap{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#0d1526}
.editor-wrap.is-full{position:fixed;inset:0;z-index:200;border-radius:0}
.ed-toolbar{display:flex;justify-content:space-between;align-items:center;gap:8px;
 background:#111a2e;border-bottom:1px solid var(--line);padding:6px 8px;flex-wrap:wrap}
.ed-tabs{display:flex;gap:4px}
.ed-tab{background:transparent;border:0;color:#8fa0bd;padding:7px 14px;border-radius:8px;
 cursor:pointer;font-weight:700;font-size:.86rem;font-family:inherit}
.ed-tab.act{background:#243350;color:#e7edf7}
.ed-actions{display:flex;gap:4px;flex-wrap:wrap}
.ed-btn{background:#1c2a45;border:1px solid #243350;color:#c9d8f0;border-radius:8px;
 padding:7px 12px;cursor:pointer;font-size:.82rem;font-family:inherit;font-weight:600}
.ed-mobile-switch{display:none;background:#111a2e;border-bottom:1px solid var(--line);padding:6px 8px;gap:4px}
.ms-btn{flex:1;background:transparent;border:0;color:#8fa0bd;padding:8px;border-radius:8px;
 cursor:pointer;font-weight:700;font-family:inherit;font-size:.86rem}
.ms-btn.act{background:#243350;color:#e7edf7}
.ed-body{display:grid;grid-template-columns:1fr 1fr;height:420px}
.editor-wrap.is-full .ed-body{height:calc(100vh - 96px)}
.ed-code{position:relative;border-right:1px solid var(--line)}
.ed-area{width:100%;height:100%;border:0;outline:0;resize:none;background:#0d1526;color:#c9d8f0;
 font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;line-height:1.6;padding:12px;display:block}
.ed-preview{background:#fff}
.ed-preview iframe{width:100%;height:100%;border:0;display:block;background:#fff}
.ed-status{display:flex;justify-content:space-between;gap:10px;padding:7px 12px;background:#111a2e;
 border-top:1px solid var(--line);font-size:.8rem;flex-wrap:wrap}
.ed-err{color:#f87171;font-family:ui-monospace,monospace;word-break:break-word}

/* ---- тест ---- */
.test-form{margin-top:14px}
.q-block{background:var(--bg2);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:12px}
.q-block.q-ok{border-color:var(--ok)}
.q-block.q-bad{border-color:var(--err)}
.q-title{font-weight:700;margin-bottom:12px;display:flex;gap:10px;align-items:flex-start}
.q-num{background:var(--accent);color:#04121f;width:24px;height:24px;border-radius:50%;flex-shrink:0;
 display:flex;align-items:center;justify-content:center;font-size:.82rem}
.q-opts{display:flex;flex-direction:column;gap:8px}
.q-opt{display:flex;gap:10px;align-items:flex-start;background:var(--card);border:1px solid var(--line);
 border-radius:10px;padding:11px 14px;cursor:pointer;font-size:.95rem}
.q-opt input{margin-top:4px;flex-shrink:0}
.q-opt.is-correct{border-color:var(--ok);background:rgba(34,197,94,.12)}
.q-opt.is-wrong{border-color:var(--err);background:rgba(239,68,68,.12)}
.q-explain{margin-top:10px;font-size:.88rem;color:var(--muted);background:var(--card);
 border-radius:8px;padding:10px 12px}
.test-result{display:flex;gap:16px;align-items:center;border-radius:12px;padding:16px;margin-bottom:14px;
 border:1px solid var(--line);background:var(--bg2)}
.test-result.ok{border-color:var(--ok)}
.test-result.bad{border-color:var(--err)}
.tr-score{font-size:2rem;font-weight:800;color:var(--accent)}
.lesson-done{background:rgba(34,197,94,.12);border:1px solid var(--ok);border-radius:12px;
 padding:16px;margin-bottom:14px;text-align:center}
.lesson-done .btn{margin-top:10px}

.profile-head{display:flex;gap:18px;align-items:center;padding:16px 0;flex-wrap:wrap}
.avatar{width:84px;height:84px;border-radius:50%;flex-shrink:0;background:linear-gradient(135deg,var(--accent),var(--accent2));
 display:flex;align-items:center;justify-content:center;font-size:2.2rem;font-weight:800;color:#04121f}
.prof-progress{display:flex;flex-direction:column;gap:12px}
.prof-row{display:grid;grid-template-columns:150px 1fr 60px;gap:12px;align-items:center}
.prof-course{font-weight:700;font-size:.95rem}
.prof-pct{color:var(--muted);font-size:.85rem;text-align:right}

.auth-box{max-width:420px;margin:32px auto;background:var(--card);border:1px solid var(--line);
 border-radius:var(--radius);padding:30px;box-shadow:var(--shadow)}
.auth-box h1{font-size:1.5rem;margin-bottom:14px}
.auth-box form{display:flex;flex-direction:column;gap:14px;margin-top:12px}
.auth-box label{display:flex;flex-direction:column;gap:6px;font-weight:600;font-size:.92rem}
.auth-box input{background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:12px 14px;
 color:var(--txt);font-family:inherit;font-size:1rem}
.auth-alt{margin-top:16px;text-align:center;font-size:.92rem}

.muted{color:var(--muted)}
.footer{border-top:1px solid var(--line);padding:22px 16px;text-align:center;color:var(--muted);font-size:.88rem}

@media (max-width:760px){
  .topbar{flex-wrap:wrap;gap:8px}
  .topnav{order:3;width:100%;justify-content:center}
  .prof-row{grid-template-columns:110px 1fr 52px}
  .lesson-map{grid-template-columns:repeat(5,1fr)}
  .hero{padding-top:32px}
  .lesson-block{padding:16px}
  /* дар телефон: код ва натиҷа иваз мешаванд, на ним-ним */
  .ed-mobile-switch{display:flex}
  .ed-body{grid-template-columns:1fr;height:380px}
  .ed-code{border-right:0}
  .editor-wrap[data-view="preview"] .ed-code{display:none}
  .editor-wrap:not([data-view="preview"]) .ed-preview{display:none}
  .editor-wrap.is-full .ed-body{height:calc(100vh - 130px)}
}
    <?php
}
