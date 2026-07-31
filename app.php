<?php
/**
 * CodeTJ — барнома (аз index.php даъват мешавад).
 * Роутинг: ?p=...  Синтаксис: PHP 7.1+ мутобиқ.
 *
 * Воридшавӣ бо рақами телефон, дарсҳо қадам ба қадам,
 * дарси навбатӣ танҳо баъд аз супоридани дарси пешина кушода мешавад.
 */

// Муҳофизат аз дубора ворид шудани ҳамин файл.
if (defined('CODETJ_APP_LOADED')) {
    return;
}
define('CODETJ_APP_LOADED', 1);

// db.php-ро ПЕШ АЗ ворид кардан тафтиш мекунем.
// PHP функсияҳоро ҳангоми компиляция эълон мекунад, барои ҳамин
// «return»-и дохили файл аз хатои «Cannot redeclare» наҷот намедиҳад.
$codetj_db = __DIR__ . '/db.php';
$codetj_src = file_exists($codetj_db) ? (string)file_get_contents($codetj_db) : '';
if ($codetj_src === '' || strpos($codetj_src, 'function db(') === false
    || strpos($codetj_src, 'function t(') !== false) {
    if (function_exists('codetj_boot_page')) {
        codetj_boot_page(
            'Файли db.php нодуруст аст',
            'Дар папка ба ҷои <b>db.php</b> файли дигар хобидааст — аз афташ нусхаи <b>app.php</b>. '
            . 'Файли дурусти <b>db.php</b>-ро аз нав бор кунед: дар он бояд танзимоти база бошад, на коди сайт.',
            'Вместо db.php лежит другой файл — похоже, копия app.php. Загрузите правильный db.php заново: '
            . 'в нём должны быть настройки базы, а не код сайта.'
        );
    }
    exit('db.php нодуруст аст / неверный db.php');
}
unset($codetj_db, $codetj_src);

require_once __DIR__ . '/db.php';

codetj_session_start();

/* ============================================================
 *  ЗАБОНҲО
 * ============================================================ */
$LANG = array(
'tj' => array(
    'tagline'        => 'Барномасозиро бо забони тоҷикӣ омӯз',
    'hero_text'      => 'HTML, CSS ва JavaScript — бо забони модарӣ. Кодро дар браузер менависӣ ва дарҳол натиҷаро мебинӣ.',
    'start_free'     => 'Оғоз кун — ройгон',
    'nav_home'       => 'Асосӣ',
    'nav_profile'    => 'Профил',
    'nav_rating'     => 'Рейтинг',
    'enter'          => 'Даромадан',
    'logout'         => 'Баромадан',
    'phone'          => 'Рақами телефон',
    'phone_hint'     => 'Рақами худро нависед — ҳамин бас. Пароли ба хотир гирифтан лозим нест.',
    'phone_ph'       => '90 123 45 67',
    'phone_next'     => 'Идома',
    'phone_bad'      => 'Рақам нодуруст аст. Мисол: 901234567',
    'name_title'     => 'Шинос шавем!',
    'name_hint'      => 'Ин рақам аввалин бор ин ҷо. Номатро нависед — ҳамин бас.',
    'name'           => 'Номи ту',
    'name_ph'        => 'Масалан: Алиҷон',
    'city'           => 'Шаҳр ё ноҳия',
    'city_ph'        => 'Душанбе, Хуҷанд, Кӯлоб…',
    'city_opt'       => 'ихтиёрӣ',
    'start_learn'    => 'Оғози омӯзиш',
    'name_empty'     => 'Номатро нависед.',
    'welcome_back'   => 'Хуш омадӣ',
    'pin_title'      => 'Рамзи админ',
    'pin_hint'       => 'Ту аввалин корбарӣ, барои ҳамин администратор мешавӣ. Рамзи 4–6 рақама соз, то ҳисобатро касе нагирад.',
    'pin_ask'        => 'Рамзи худро нависед',
    'pin'            => 'Рамз (4–6 рақам)',
    'pin_bad'        => 'Рамз нодуруст аст.',
    'pin_short'      => 'Рамз бояд 4–6 рақам бошад.',
    'points'         => 'балл',
    'streak'         => 'рӯз пай дар пай',
    'of'             => 'аз',
    'done_word'      => 'супорида шуд',
    'continue'       => 'Давом додан',
    'open_course'    => 'Оғоз кардан',
    'full_locked_hint' => 'Ин курс кушода мешавад, вақте дар HTML, CSS ва JS ҳар кадомашро 60% мегузаронӣ.',
    'level'          => 'Сатҳ',
    'lesson'         => 'Дарс',
    'lesson_locked'  => 'Аввал дарси пешинаро супор',
    'lesson_soon'    => 'Ин дарс ҳанӯз тайёр мешавад',
    'back'           => 'Бозгашт',
    'step'           => 'Қадам',
    'step_next'      => 'Оянда',
    'step_prev'      => 'Қафо',
    'step_done'      => 'Назария тамом! Акнун худат нависем',
    'to_practice'    => 'Ба амалия гузаштан',
    'practice'       => 'Амалия',
    'test'           => 'Тест',
    'example'        => 'Намуна',
    'open_in_editor' => 'Дар муҳаррир кушодан',
    'run'            => 'Иҷро',
    'save'           => 'Захира',
    'reset'          => 'Аз нав',
    'preview'        => 'Натиҷа',
    'code'           => 'Код',
    'saved'          => 'Захира шуд',
    'saving'         => 'Захира мешавад…',
    'save_err'       => 'Захира нашуд',
    'task'           => 'Супориш',
    'console'        => 'Терминал',
    'con_clear'      => 'Тоза',
    'con_empty'      => 'Ин ҷо натиҷаи console.log ва хатоҳо пайдо мешаванд.',
    'ai_check'       => 'Санҷиши AI',
    'ai_checking'    => 'Устод коратро мехонад…',
    'ai_wait'        => 'Каме сабр кун',
    'ai_sec'         => 'сония',
    'ai_limit'       => 'Имрӯз барои ин дарс лимит тамом шуд. Пагоҳ боз кӯшиш кун.',
    'ai_empty'       => 'Аввал кодро нависед, баъд месанҷем.',
    'ai_off'         => 'Санҷиши AI ҳанӯз фаъол нест.',
    'ai_err'         => 'Ҳозир устод ҷавоб дода наметавонад. Каме баъдтар кӯшиш кун.',
    'ai_passed'      => 'Кор қабул шуд!',
    'ai_failed'      => 'Ҳанӯз тайёр нест',
    'ai_errors'      => 'Чиро дуруст кардан лозим',
    'ai_advice'      => 'Маслиҳат',
    'ai_line'        => 'сатри',
    'ai_cached'      => 'аз хотира',
    'ai_left'        => 'Имрӯз боқӣ мондааст',
    'ai_need'        => 'Барои супоридани дарс: санҷиши AI + тест аз 60%',
    'test_intro'     => 'Ба 5 савол ҷавоб деҳ. Ҷавоби дуруст аз кӯшиши аввал — 10 балл, аз дуюм — 5.',
    'test_send'      => 'Ҷавобҳоро фиристодан',
    'test_again'     => 'Аз нав кӯшиш кардан',
    'test_correct'   => 'Дуруст',
    'test_need_all'  => 'Ба ҳамаи саволҳо ҷавоб деҳ.',
    'test_passed'    => 'Офарин! Тест супорида шуд.',
    'test_failed'    => 'Ҳанӯз кам аст. Назарияро боз як бор хон.',
    'grade_1'        => 'Бояд такрор кунӣ',
    'grade_2'        => 'Хуб',
    'grade_3'        => 'Хеле хуб',
    'grade_4'        => 'Аъло',
    'grade_word'     => 'Баҳо',
    'answers_right'  => 'ҷавоби дуруст',
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
    'keep_going'     => 'Давом деҳ',
    'lesson_of'      => 'Дарси',
    'footer_note'    => 'Барои ҳамаи онҳое, ки мехоҳанд барномасоз шаванд',
    'err_csrf'       => 'Форма кӯҳна шудааст. Саҳифаро нав кун.',
    'err_rate'       => 'Хеле зуд-зуд кӯшиш кардӣ. Якчанд дақиқа сабр кун.',
    'err_banned'     => 'Ҳисоби ту баста шудааст.',
    'err_not_found'  => 'Чунин саҳифа ёфт нашуд.',
    'err_need_login' => 'Барои ин амал аввал даро.',
    'ok_registered'  => 'Табрик! Акнун омӯзишро сар кун!',
    'lang_tj'        => 'ТҶ',
    'lang_ru'        => 'РУ',
    'why_title'      => 'Чаро CodeTJ?',
    'why_1_t'        => 'Бо забони худат',
    'why_1_d'        => 'Дарсҳо бо тоҷикии зинда — фаҳмо, бе тарҷумаи хушк.',
    'why_2_t'        => 'Қадам ба қадам',
    'why_2_d'        => 'Ҳар дарс ба қадамҳои хурд тақсим шудааст. Гум намешавӣ.',
    'why_3_t'        => 'Код дар браузер',
    'why_3_d'        => 'Менависӣ — дарҳол натиҷаро мебинӣ. Ҳеҷ чиз насб кардан лозим нест.',
    'why_4_t'        => 'Бе парол',
    'why_4_d'        => 'Танҳо рақами телефон. Даромадан — 5 сония.',
    'stat_lessons'   => 'дарс',
    'stat_free'      => 'ройгон',
    'stat_lang'      => 'тоҷикӣ',
),
'ru' => array(
    'tagline'        => 'Учи программирование на таджикском',
    'hero_text'      => 'HTML, CSS и JavaScript — на родном языке. Пишешь код в браузере и сразу видишь результат.',
    'start_free'     => 'Начать — бесплатно',
    'nav_home'       => 'Главная',
    'nav_profile'    => 'Профиль',
    'nav_rating'     => 'Рейтинг',
    'enter'          => 'Войти',
    'logout'         => 'Выйти',
    'phone'          => 'Номер телефона',
    'phone_hint'     => 'Просто напиши свой номер. Пароль запоминать не нужно.',
    'phone_ph'       => '90 123 45 67',
    'phone_next'     => 'Далее',
    'phone_bad'      => 'Неверный номер. Пример: 901234567',
    'name_title'     => 'Давай познакомимся!',
    'name_hint'      => 'Этот номер здесь впервые. Напиши своё имя — этого достаточно.',
    'name'           => 'Твоё имя',
    'name_ph'        => 'Например: Алиджон',
    'city'           => 'Город или район',
    'city_ph'        => 'Душанбе, Худжанд, Куляб…',
    'city_opt'       => 'необязательно',
    'start_learn'    => 'Начать учиться',
    'name_empty'     => 'Напиши своё имя.',
    'welcome_back'   => 'С возвращением',
    'pin_title'      => 'Код администратора',
    'pin_hint'       => 'Ты первый пользователь, поэтому становишься администратором. Придумай код из 4–6 цифр, чтобы аккаунт не занял кто-то другой.',
    'pin_ask'        => 'Введи свой код',
    'pin'            => 'Код (4–6 цифр)',
    'pin_bad'        => 'Неверный код.',
    'pin_short'      => 'Код должен быть из 4–6 цифр.',
    'points'         => 'баллов',
    'streak'         => 'дней подряд',
    'of'             => 'из',
    'done_word'      => 'пройдено',
    'continue'       => 'Продолжить',
    'open_course'    => 'Начать',
    'full_locked_hint' => 'Этот курс откроется, когда в HTML, CSS и JS будет пройдено по 60%.',
    'level'          => 'Уровень',
    'lesson'         => 'Урок',
    'lesson_locked'  => 'Сначала пройди предыдущий урок',
    'lesson_soon'    => 'Этот урок ещё готовится',
    'back'           => 'Назад',
    'step'           => 'Шаг',
    'step_next'      => 'Дальше',
    'step_prev'      => 'Назад',
    'step_done'      => 'Теория пройдена! Теперь пишем сами',
    'to_practice'    => 'Перейти к практике',
    'practice'       => 'Практика',
    'test'           => 'Тест',
    'example'        => 'Пример',
    'open_in_editor' => 'Открыть в редакторе',
    'run'            => 'Запустить',
    'save'           => 'Сохранить',
    'reset'          => 'Сбросить',
    'preview'        => 'Результат',
    'code'           => 'Код',
    'saved'          => 'Сохранено',
    'saving'         => 'Сохраняем…',
    'save_err'       => 'Не сохранилось',
    'task'           => 'Задание',
    'console'        => 'Терминал',
    'con_clear'      => 'Очистить',
    'con_empty'      => 'Здесь появятся console.log и ошибки.',
    'ai_check'       => 'Проверка AI',
    'ai_checking'    => 'Наставник читает твой код…',
    'ai_wait'        => 'Немного подожди',
    'ai_sec'         => 'сек',
    'ai_limit'       => 'На сегодня лимит для этого урока исчерпан. Попробуй завтра.',
    'ai_empty'       => 'Сначала напиши код, потом проверим.',
    'ai_off'         => 'Проверка AI пока не включена.',
    'ai_err'         => 'Наставник сейчас не отвечает. Попробуй чуть позже.',
    'ai_passed'      => 'Работа принята!',
    'ai_failed'      => 'Пока не готово',
    'ai_errors'      => 'Что нужно исправить',
    'ai_advice'      => 'Совет',
    'ai_line'        => 'строка',
    'ai_cached'      => 'из памяти',
    'ai_left'        => 'Осталось сегодня',
    'ai_need'        => 'Чтобы сдать урок: проверка AI + тест от 60%',
    'test_intro'     => 'Ответь на 5 вопросов. Верный ответ с первой попытки — 10 баллов, со второй — 5.',
    'test_send'      => 'Отправить ответы',
    'test_again'     => 'Попробовать снова',
    'test_correct'   => 'Верно',
    'test_need_all'  => 'Ответь на все вопросы.',
    'test_passed'    => 'Молодец! Тест сдан.',
    'test_failed'    => 'Пока маловато. Перечитай теорию.',
    'grade_1'        => 'Нужно повторить',
    'grade_2'        => 'Хорошо',
    'grade_3'        => 'Очень хорошо',
    'grade_4'        => 'Отлично',
    'grade_word'     => 'Оценка',
    'answers_right'  => 'верных ответа',
    'try_once_more'  => 'Неверно. Подумай ещё — ответ есть в теории.',
    'lesson_done'    => 'Урок пройден!',
    'lesson_done_txt'=> 'Следующий урок открыт. Продолжай!',
    'next_lesson'    => 'Следующий урок',
    'you_got'        => 'Ты получил',
    'my_progress'    => 'Мой прогресс',
    'top_students'   => 'Лучшие ученики',
    'no_students'    => 'Пока никого нет — стань первым!',
    'rank'           => 'Место в рейтинге',
    'home_title'     => 'Твои курсы',
    'keep_going'     => 'Продолжай',
    'lesson_of'      => 'Урок',
    'footer_note'    => 'Для всех, кто хочет стать программистом',
    'err_csrf'       => 'Форма устарела. Обнови страницу.',
    'err_rate'       => 'Слишком много попыток. Подожди несколько минут.',
    'err_banned'     => 'Твой аккаунт заблокирован.',
    'err_not_found'  => 'Такая страница не найдена.',
    'err_need_login' => 'Сначала войди.',
    'ok_registered'  => 'Поздравляем! Начинай учиться!',
    'lang_tj'        => 'ТҶ',
    'lang_ru'        => 'РУ',
    'why_title'      => 'Почему CodeTJ?',
    'why_1_t'        => 'На твоём языке',
    'why_1_d'        => 'Уроки на живом таджикском — понятно, без сухого перевода.',
    'why_2_t'        => 'Шаг за шагом',
    'why_2_d'        => 'Каждый урок разбит на маленькие шаги. Не запутаешься.',
    'why_3_t'        => 'Код в браузере',
    'why_3_d'        => 'Пишешь — сразу видишь результат. Ничего не нужно устанавливать.',
    'why_4_t'        => 'Без пароля',
    'why_4_d'        => 'Только номер телефона. Вход за 5 секунд.',
    'stat_lessons'   => 'уроков',
    'stat_free'      => 'бесплатно',
    'stat_lang'      => 'таджикский',
),
);

/* ============================================================
 *  ОМОДАСОЗӢ
 * ============================================================ */

db();

$p = isset($_GET['p']) && is_string($_GET['p']) ? $_GET['p'] : 'home';

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

function t($key)
{
    global $LANG, $lang;
    if (isset($LANG[$lang][$key])) {
        return $LANG[$lang][$key];
    }
    return isset($LANG['tj'][$key]) ? $LANG['tj'][$key] : $key;
}

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

function safe_back()
{
    $b = isset($_POST['back']) ? $_POST['back'] : '';
    if (is_string($b) && preg_match('/^\?p=[a-z_]+(&[a-z]+=[a-zA-Z0-9_]+){0,3}$/', $b)) {
        return $b;
    }
    return '?p=home';
}

/* ---------- Телефон ---------- */

/**
 * Рақамро ба шакли ягона меорад: танҳо рақамҳо, бо коди кишвар 992.
 * '' — агар рақам нодуруст бошад.
 */
function normalize_phone($raw)
{
    $d = preg_replace('/\D+/', '', (string)$raw);
    if ($d === '') {
        return '';
    }
    if (substr($d, 0, 3) === '992') {
        $d = substr($d, 3);
    } elseif (substr($d, 0, 4) === '0992') {
        $d = substr($d, 4);
    }
    $d = ltrim($d, '0');
    if (strlen($d) !== 9) {
        return '';   // дар Тоҷикистон рақами мобилӣ 9 рақам аст
    }
    return '992' . $d;
}

/** Барои нишон додан: 992901234567 → +992 90 123 45 67 */
function pretty_phone($p)
{
    if (strlen($p) !== 12) {
        return $p;
    }
    return '+992 ' . substr($p, 3, 2) . ' ' . substr($p, 5, 3) . ' ' . substr($p, 8, 2) . ' ' . substr($p, 10, 2);
}

/* ---------- Кушода будани дарс ---------- */

/**
 * Дарс кушода аст, агар дарси пешина супорида шуда бошад.
 * Дарси 1 ҳамеша кушода. Ҷаҳидан ба дарси 5 ё 10 мумкин нест.
 */
function lesson_unlocked($userId, $course, $num)
{
    if ($num <= 1) {
        return true;
    }
    $st = db()->prepare(
        'SELECT COUNT(*) FROM cj_progress p JOIN cj_lessons l ON l.id = p.lesson_id
         WHERE p.user_id = ? AND l.course = ? AND l.num = ? AND p.completed = 1'
    );
    $st->execute(array($userId, $course, $num - 1));
    return (int)$st->fetchColumn() > 0;
}

/** Дарси ҷорӣ — аввалин дарси насупоридашуда. */
function next_lesson_num($userId, $course)
{
    $done = course_done_map($userId, $course);
    for ($n = 1; $n <= LESSONS_PER_COURSE; $n++) {
        if (!isset($done[$n])) {
            return $n;
        }
    }
    return LESSONS_PER_COURSE;
}

/* ---------- Назария → қадамҳо ---------- */

/**
 * Назарияро аз рӯи сарлавҳаҳои <h3> ба қадамҳо тақсим мекунад.
 * Ҳамин тавр ҳар дарс худ ба худ қадам ба қадам мешавад.
 */
function theory_steps($html)
{
    $html = trim((string)$html);
    if ($html === '') {
        return array();
    }
    $parts = preg_split('/(?=<h3[\s>])/i', $html);
    $steps = array();
    foreach ($parts as $part) {
        $part = trim($part);
        if ($part === '') {
            continue;
        }
        if (preg_match('/^<h3[^>]*>(.*?)<\/h3>(.*)$/is', $part, $m)) {
            $steps[] = array('title' => trim(strip_tags($m[1])), 'body' => trim($m[2]));
        } else {
            $steps[] = array('title' => '', 'body' => $part);
        }
    }
    return $steps;
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

        /* --- Қадами 1: рақами телефон --- */
        case 'phone':
            if ($user !== null) {
                redirect('?p=home');
            }
            if (!rate_limit('login', 15, 600)) {
                flash_set('err', 'err_rate');
                redirect('?p=enter');
            }
            $phone = normalize_phone(isset($_POST['phone']) ? $_POST['phone'] : '');
            if ($phone === '') {
                $_SESSION['auth_err'] = 'phone_bad';
                redirect('?p=enter');
            }
            $st = db()->prepare('SELECT * FROM cj_users WHERE phone = ?');
            $st->execute(array($phone));
            $u = $st->fetch();
            if ($u) {
                if ((int)$u['banned'] === 1) {
                    flash_set('err', 'err_banned');
                    redirect('?p=enter');
                }
                if ((string)$u['pin'] !== '') {
                    $_SESSION['pin_uid'] = (int)$u['id'];
                    redirect('?p=pin');
                }
                session_regenerate_id(true);
                $_SESSION['uid'] = (int)$u['id'];
                redirect('?p=home');
            }
            $_SESSION['reg_phone'] = $phone;
            redirect('?p=name');
            break;

        /* --- Қадами 2: ном (танҳо барои рақами нав) --- */
        case 'signup':
            if ($user !== null || empty($_SESSION['reg_phone'])) {
                redirect('?p=enter');
            }
            $nameV = trim((string)(isset($_POST['name']) ? $_POST['name'] : ''));
            $cityV = mb_substr(trim((string)(isset($_POST['city']) ? $_POST['city'] : '')), 0, 64);
            if ($nameV === '' || mb_strlen($nameV) > 64) {
                $_SESSION['auth_err'] = 'name_empty';
                redirect('?p=name');
            }
            $phone = $_SESSION['reg_phone'];
            $isFirst = ((int)db()->query('SELECT COUNT(*) FROM cj_users')->fetchColumn() === 0);

            $pinHash = null;
            if ($isFirst) {
                $pinV = preg_replace('/\D+/', '', (string)(isset($_POST['pin']) ? $_POST['pin'] : ''));
                if (strlen($pinV) < 4 || strlen($pinV) > 6) {
                    $_SESSION['auth_err'] = 'pin_short';
                    redirect('?p=name');
                }
                $pinHash = password_hash($pinV, PASSWORD_DEFAULT);
            }

            $st = db()->prepare(
                'INSERT INTO cj_users (phone, pin, name, city, role, lang) VALUES (?, ?, ?, ?, ?, ?)'
            );
            $st->execute(array($phone, $pinHash, $nameV, $cityV, $isFirst ? 'admin' : 'student', $lang));
            unset($_SESSION['reg_phone']);
            session_regenerate_id(true);
            $_SESSION['uid'] = (int)db()->lastInsertId();
            flash_set('ok', 'ok_registered');
            redirect('?p=home');
            break;

        /* --- Рамзи админ --- */
        case 'pin':
            if (empty($_SESSION['pin_uid'])) {
                redirect('?p=enter');
            }
            if (!rate_limit('pin', 10, 600)) {
                flash_set('err', 'err_rate');
                redirect('?p=enter');
            }
            $st = db()->prepare('SELECT * FROM cj_users WHERE id = ?');
            $st->execute(array((int)$_SESSION['pin_uid']));
            $u = $st->fetch();
            $pinV = preg_replace('/\D+/', '', (string)(isset($_POST['pin']) ? $_POST['pin'] : ''));
            if (!$u || !password_verify($pinV, (string)$u['pin'])) {
                $_SESSION['auth_err'] = 'pin_bad';
                redirect('?p=pin');
            }
            unset($_SESSION['pin_uid']);
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
                db()->prepare('UPDATE cj_users SET lang = ? WHERE id = ?')->execute(array($newLang, (int)$user['id']));
            }
            redirect(safe_back());
            break;

        case 'settheme':
            $newTheme = (isset($_POST['theme']) && $_POST['theme'] === 'light') ? 'light' : 'dark';
            if ($user !== null) {
                db()->prepare('UPDATE cj_users SET theme = ? WHERE id = ?')->execute(array($newTheme, (int)$user['id']));
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
            db()->prepare(
                'INSERT INTO cj_drafts (user_id, lesson_id, html_code, css_code, js_code, pasted)
                 VALUES (?,?,?,?,?,?)
                 ON DUPLICATE KEY UPDATE html_code=VALUES(html_code), css_code=VALUES(css_code),
                 js_code=VALUES(js_code), pasted=GREATEST(pasted, VALUES(pasted))'
            )->execute(array(
                (int)$user['id'], $lid,
                $cut(isset($_POST['html']) ? $_POST['html'] : ''),
                $cut(isset($_POST['css']) ? $_POST['css'] : ''),
                $cut(isset($_POST['js']) ? $_POST['js'] : ''),
                (isset($_POST['pasted']) && $_POST['pasted'] === '1') ? 1 : 0,
            ));
            json_out(array('ok' => true));
            break;

        case 'ai_check':
            if ($user === null) {
                json_out(array('ok' => false, 'msg' => t('err_need_login')), 403);
            }
            handle_ai_check((int)$user['id']);
            break;

        case 'test':
            if ($user === null) {
                redirect('?p=enter');
            }
            handle_test_submit((int)$user['id']);
            break;

        default:
            redirect('?p=home');
    }
}

/* ============================================================
 *  САНҶИШИ КОД БО ЗЕҲНИ СУНЪӢ
 * ============================================================ */

/** Калиди API: аввал аз танзимот, баъд аз db.php. Ҳеҷ гоҳ ба браузер намеравад. */
function ai_key()
{
    $k = trim((string)setting_get('openai_key', ''));
    if ($k !== '') {
        return $k;
    }
    return trim(OPENAI_KEY);
}

/**
 * Дархост ба OpenAI. Танҳо аз сервер, бо cURL.
 * Бармегардонад: array('ok'=>bool, 'text'=>..., 'in'=>..., 'out'=>..., 'err'=>...)
 */
function openai_chat($messages, $maxTokens = 600)
{
    $key = ai_key();
    if ($key === '') {
        return array('ok' => false, 'err' => 'no_key');
    }
    if (!function_exists('curl_init')) {
        return array('ok' => false, 'err' => 'no_curl');
    }
    $payload = json_encode(array(
        'model'       => OPENAI_MODEL,
        'messages'    => $messages,
        'temperature' => 0.2,
        'max_tokens'  => $maxTokens,
    ), JSON_UNESCAPED_UNICODE);

    $ch = curl_init(OPENAI_URL);
    curl_setopt_array($ch, array(
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $payload,
        CURLOPT_HTTPHEADER     => array(
            'Content-Type: application/json',
            'Authorization: Bearer ' . $key,
        ),
        CURLOPT_TIMEOUT        => 45,
        CURLOPT_CONNECTTIMEOUT => 12,
    ));
    $raw = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $cerr = curl_error($ch);
    curl_close($ch);

    if ($raw === false || $code === 0) {
        return array('ok' => false, 'err' => 'net:' . $cerr);
    }
    $data = json_decode($raw, true);
    if (!is_array($data)) {
        return array('ok' => false, 'err' => 'bad_json');
    }
    if ($code !== 200 || isset($data['error'])) {
        $m = isset($data['error']['message']) ? $data['error']['message'] : ('http ' . $code);
        return array('ok' => false, 'err' => $m);
    }
    if (!isset($data['choices'][0]['message']['content'])) {
        return array('ok' => false, 'err' => 'no_content');
    }
    return array(
        'ok'   => true,
        'text' => (string)$data['choices'][0]['message']['content'],
        'in'   => isset($data['usage']['prompt_tokens']) ? (int)$data['usage']['prompt_tokens'] : 0,
        'out'  => isset($data['usage']['completion_tokens']) ? (int)$data['usage']['completion_tokens'] : 0,
    );
}

/** JSON-и ҷавобро бехатар мехонад (ҳатто агар дар ```json печонида шуда бошад). */
function parse_ai_json($text)
{
    $t = trim($text);
    $t = preg_replace('/^```[a-z]*\s*/i', '', $t);
    $t = preg_replace('/\s*```$/', '', $t);
    $d = json_decode($t, true);
    if (!is_array($d)) {
        // баъзан модел матни иловагӣ менависад — аввалин { … }-ро мегирем
        if (preg_match('/\{.*\}/s', $t, $m)) {
            $d = json_decode($m[0], true);
        }
    }
    if (!is_array($d)) {
        return null;
    }
    $errors = array();
    if (isset($d['errors']) && is_array($d['errors'])) {
        foreach ($d['errors'] as $er) {
            if (!is_array($er)) {
                continue;
            }
            $errors[] = array(
                'line' => isset($er['line']) ? (int)$er['line'] : 0,
                'text' => isset($er['text']) ? mb_substr((string)$er['text'], 0, 400) : '',
            );
            if (count($errors) >= 8) {
                break;
            }
        }
    }
    $score = isset($d['score']) ? (int)$d['score'] : 0;
    if ($score < 0) { $score = 0; }
    if ($score > 100) { $score = 100; }
    return array(
        'passed' => !empty($d['passed']),
        'score'  => $score,
        'errors' => $errors,
        'advice' => isset($d['advice']) ? mb_substr((string)$d['advice'], 0, 700) : '',
        'praise' => isset($d['praise']) ? mb_substr((string)$d['praise'], 0, 400) : '',
    );
}

/** Санҷиши арзон дар сервер, то коди холӣ ба API нафиристем. */
function local_precheck($code)
{
    if (trim($code) === '') {
        return 'ai_empty';
    }
    return null;
}

function handle_ai_check($uid)
{
    global $lang;

    $lid = (int)(isset($_POST['lesson_id']) ? $_POST['lesson_id'] : 0);
    $st = db()->prepare('SELECT * FROM cj_lessons WHERE id = ? AND published = 1');
    $st->execute(array($lid));
    $L = $st->fetch();
    if (!$L) {
        json_out(array('ok' => false, 'msg' => t('err_not_found')), 404);
    }
    if (ai_key() === '') {
        json_out(array('ok' => false, 'msg' => t('ai_off')));
    }

    $html = (string)(isset($_POST['html']) ? $_POST['html'] : '');
    $css  = (string)(isset($_POST['css']) ? $_POST['css'] : '');
    $js   = (string)(isset($_POST['js']) ? $_POST['js'] : '');
    $code = trim($html);
    if (trim($css) !== '') {
        $code .= "\n\n/* CSS */\n" . $css;
    }
    if (trim($js) !== '') {
        $code .= "\n\n// JS\n" . $js;
    }
    $code = mb_substr($code, 0, 12000);

    $pre = local_precheck($code);
    if ($pre !== null) {
        json_out(array('ok' => false, 'msg' => t($pre)));
    }

    $pdo = db();

    // Кулдаун
    $cool = (int)setting_get('ai_cooldown_sec', '15');
    $st = $pdo->prepare(
        'SELECT TIMESTAMPDIFF(SECOND, created_at, NOW()) FROM cj_ai_usage
         WHERE user_id = ? ORDER BY id DESC LIMIT 1'
    );
    $st->execute(array($uid));
    $since = $st->fetchColumn();
    if ($since !== false && (int)$since < $cool) {
        json_out(array('ok' => false, 'wait' => $cool - (int)$since, 'msg' => t('ai_wait')));
    }

    // Лимити рӯзона барои ин дарс
    $limit = (int)setting_get('ai_daily_limit', '10');
    $st = $pdo->prepare(
        'SELECT COUNT(*) FROM cj_ai_usage WHERE user_id = ? AND lesson_id = ?
         AND kind = ? AND DATE(created_at) = CURDATE()'
    );
    $st->execute(array($uid, $lid, 'check'));
    $used = (int)$st->fetchColumn();
    if ($used >= $limit) {
        json_out(array('ok' => false, 'msg' => t('ai_limit')));
    }

    // Кэш аз рӯи хэши код
    $hash = hash('sha256', $code);
    $st = $pdo->prepare('SELECT response FROM cj_ai_cache WHERE lesson_id = ? AND code_hash = ? AND lang = ?');
    $st->execute(array($lid, $hash, $lang));
    $cached = $st->fetchColumn();
    if ($cached !== false) {
        $res = json_decode((string)$cached, true);
        if (is_array($res)) {
            $pdo->prepare('INSERT INTO cj_ai_usage (user_id, lesson_id, kind, cached) VALUES (?,?,?,1)')
                ->execute(array($uid, $lid, 'check'));
            save_ai_progress($uid, $lid, $res);
            $res['cached'] = true;
            $res['left'] = max(0, $limit - $used - 1);
            json_out(array('ok' => true, 'res' => $res));
        }
    }

    $langName = ($lang === 'ru') ? 'русском' : 'таджикском (кириллица)';
    $sys = "Ты — добрый, но требовательный учитель веб-разработки для подростков из Таджикистана.\n"
         . "ОТВЕЧАЙ СТРОГО на {$langName} языке. Ни одного слова на другом языке.\n"
         . "Обращайся на «ты», пиши короткими простыми предложениями, как школьнику 14 лет.\n\n"
         . "Оценивай код ТОЛЬКО по критериям задания, которые тебе дали.\n\n"
         . "ЕСЛИ ЕСТЬ ОШИБКИ:\n"
         . "- НИКОГДА не давай готовый правильный код и не пиши готовый ответ.\n"
         . "- Для каждой ошибки укажи номер строки и объясни ПРИЧИНУ: что именно не так и почему это неправильно.\n"
         . "- Дай наводящую подсказку, чтобы ученик сам догадался.\n\n"
         . "ЕСЛИ ВСЁ ПРАВИЛЬНО:\n"
         . "- Похвали конкретно за то, что он сделал хорошо.\n"
         . "- В поле advice объясни, ЗАЧЕМ нужны те теги и приёмы, которые он применил — для чего они служат.\n"
         . "- Добавь один совет, как сделать код ещё лучше.\n\n"
         . "Верни ТОЛЬКО валидный JSON, без markdown и без ```:\n"
         . '{"passed":true,"score":85,"errors":[{"line":7,"text":"..."}],"advice":"...","praise":"..."}' . "\n"
         . "passed = true только если выполнены все критерии. score от 0 до 100.";

    $usr = "ЗАДАНИЕ (что должен был сделать ученик):\n" . (string)$L['task_criteria']
         . "\n\nКОД УЧЕНИКА (номера строк указаны слева):\n" . number_lines($code);

    $ans = openai_chat(array(
        array('role' => 'system', 'content' => $sys),
        array('role' => 'user',   'content' => $usr),
    ), 700);

    if (empty($ans['ok'])) {
        error_log('CodeTJ AI: ' . (isset($ans['err']) ? $ans['err'] : '?'));
        json_out(array('ok' => false, 'msg' => t('ai_err')));
    }
    $res = parse_ai_json($ans['text']);
    if ($res === null) {
        error_log('CodeTJ AI: bad json from model');
        json_out(array('ok' => false, 'msg' => t('ai_err')));
    }

    $pdo->prepare(
        'INSERT IGNORE INTO cj_ai_cache (lesson_id, code_hash, lang, response) VALUES (?,?,?,?)'
    )->execute(array($lid, $hash, $lang, json_encode($res, JSON_UNESCAPED_UNICODE)));

    $pdo->prepare(
        'INSERT INTO cj_ai_usage (user_id, lesson_id, kind, tokens_in, tokens_out, cached) VALUES (?,?,?,?,?,0)'
    )->execute(array($uid, $lid, 'check', (int)$ans['in'], (int)$ans['out']));

    save_ai_progress($uid, $lid, $res);
    $res['cached'] = false;
    $res['left'] = max(0, $limit - $used - 1);
    json_out(array('ok' => true, 'res' => $res));
}

/** Рақами сатрҳоро мегузорад, то ИИ дақиқ гӯяд, ки хато дар куҷост. */
function number_lines($code)
{
    $lines = explode("\n", $code);
    $out = array();
    foreach ($lines as $i => $l) {
        $out[] = ($i + 1) . ': ' . $l;
    }
    return implode("\n", $out);
}

/** Натиҷаи ИИ-ро дар пешрафт сабт мекунад ва дарсро месупорад, агар тест ҳам тайёр бошад. */
function save_ai_progress($uid, $lid, $res)
{
    $pdo = db();
    $passed = !empty($res['passed']) ? 1 : 0;
    $score = (int)$res['score'];

    $st = $pdo->prepare('SELECT * FROM cj_progress WHERE user_id = ? AND lesson_id = ?');
    $st->execute(array($uid, $lid));
    $pr = $st->fetch();
    $wasPassed = $pr ? (int)$pr['ai_passed'] === 1 : false;
    $testOk = $pr ? (int)$pr['test_score'] >= 60 : false;
    $wasCompleted = $pr ? (int)$pr['completed'] === 1 : false;
    $completed = ($passed === 1 && $testOk) ? 1 : 0;

    // Баллҳо барои коди қабулшуда — танҳо як бор: score × 2
    $gain = 0;
    if ($passed === 1 && !$wasPassed) {
        $gain = $score * 2;
        add_points($uid, $gain, 'ai_task');
    }

    $pdo->prepare(
        'INSERT INTO cj_progress (user_id, lesson_id, ai_passed, ai_score, completed, completed_at, points_earned)
         VALUES (?,?,?,?,?,?,?)
         ON DUPLICATE KEY UPDATE ai_passed=GREATEST(ai_passed, VALUES(ai_passed)),
         ai_score=GREATEST(ai_score, VALUES(ai_score)),
         completed=GREATEST(completed, VALUES(completed)),
         completed_at=IF(completed_at IS NULL AND VALUES(completed)=1, NOW(), completed_at),
         points_earned=points_earned+VALUES(points_earned)'
    )->execute(array(
        $uid, $lid, $passed, $score, $completed,
        $completed === 1 ? date('Y-m-d H:i:s') : null,
        $gain,
    ));

    return array('completed' => $completed === 1, 'newly' => $completed === 1 && !$wasCompleted, 'gain' => $gain);
}

/** Тестро дар сервер месанҷад. Ҷавобҳои дуруст ба браузер намераванд. */
function handle_test_submit($uid)
{
    $lid = (int)(isset($_POST['lesson_id']) ? $_POST['lesson_id'] : 0);
    $st = db()->prepare('SELECT * FROM cj_lessons WHERE id = ? AND published = 1');
    $st->execute(array($lid));
    $L = $st->fetch();
    if (!$L) {
        redirect('?p=home');
    }
    $st = db()->prepare('SELECT * FROM cj_questions WHERE lesson_id = ? ORDER BY num ASC, id ASC');
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

        $st = $pdo->prepare('SELECT attempts, correct FROM cj_test_answers WHERE user_id = ? AND question_id = ?');
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
            'INSERT INTO cj_test_answers (user_id, question_id, attempts, correct, points)
             VALUES (?,?,?,?,?)
             ON DUPLICATE KEY UPDATE attempts=VALUES(attempts),
             correct=GREATEST(correct, VALUES(correct)), points=points+VALUES(points)'
        )->execute(array($uid, $qid, $attempts, $isRight ? 1 : 0, $award));

        // Ҷавоби дурустро танҳо баъд аз ҷавоби дуруст ё ду кӯшиш нишон медиҳем.
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

    $st = $pdo->prepare('SELECT * FROM cj_progress WHERE user_id = ? AND lesson_id = ?');
    $st->execute(array($uid, $lid));
    $pr = $st->fetch();
    $wasCompleted = $pr ? (int)$pr['completed'] === 1 : false;
    $prevAttempts = $pr ? (int)$pr['test_attempts'] : 0;
    $bestScore = $pr ? max((int)$pr['test_score'], $score) : $score;

    // Санҷиши AI ҳанӯз фаъол нест — то он вақт дарс бо тест ҳисоб мешавад.
    $aiReady = trim((string)setting_get('openai_key', '')) !== '' || OPENAI_KEY !== '';
    $aiPassed = $pr ? (int)$pr['ai_passed'] === 1 : false;
    $completed = $passed && (!$aiReady || $aiPassed);

    $bonus = 0;
    if ($completed && !$wasCompleted && $prevAttempts === 0 && $score === 100) {
        $bonus = 50;
        add_points($uid, $bonus, 'first_try');
    }

    $pdo->prepare(
        'INSERT INTO cj_progress (user_id, lesson_id, test_score, test_attempts, completed, completed_at, points_earned, first_try)
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
 *  РОУТИНГ
 * ============================================================ */

switch ($p) {
    case 'home':    page_home(); break;
    case 'enter':   $user === null ? page_enter() : redirect('?p=home'); break;
    case 'name':    $user === null ? page_name() : redirect('?p=home'); break;
    case 'pin':     $user === null ? page_pin() : redirect('?p=home'); break;
    case 'course':  page_course(); break;
    case 'lesson':  page_lesson(); break;
    case 'rating':  page_rating(); break;
    case 'profile': $user !== null ? page_profile() : redirect('?p=enter'); break;
    default:        page_404();
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
    render_footer();
}

function render_hero_guest()
{
    $ready = (int)db()->query('SELECT COUNT(*) FROM cj_lessons WHERE published = 1')->fetchColumn();
    ?>
    <section class="hero">
      <div class="hero-badge">&#127993; <?= e(t('stat_lang')) ?></div>
      <h1><?= e(t('tagline')) ?></h1>
      <p class="hero-sub"><?= e(t('hero_text')) ?></p>
      <a class="btn btn-primary btn-lg" href="?p=enter"><?= e(t('start_free')) ?> &rarr;</a>
      <div class="hero-stats">
        <div class="hstat"><b><?= $ready ?></b><span><?= e(t('stat_lessons')) ?></span></div>
        <div class="hstat"><b>100%</b><span><?= e(t('stat_free')) ?></span></div>
        <div class="hstat"><b>4</b><span><?= e(t('nav_home') === 'Главная' ? 'курса' : 'курс') ?></span></div>
      </div>
    </section>

    <section class="why">
      <h2 class="sec-title center"><?= e(t('why_title')) ?></h2>
      <div class="why-grid">
        <div class="why-card"><div class="why-ic">&#128483;</div><h3><?= e(t('why_1_t')) ?></h3><p><?= e(t('why_1_d')) ?></p></div>
        <div class="why-card"><div class="why-ic">&#129517;</div><h3><?= e(t('why_2_t')) ?></h3><p><?= e(t('why_2_d')) ?></p></div>
        <div class="why-card"><div class="why-ic">&#128187;</div><h3><?= e(t('why_3_t')) ?></h3><p><?= e(t('why_3_d')) ?></p></div>
        <div class="why-card"><div class="why-ic">&#128241;</div><h3><?= e(t('why_4_t')) ?></h3><p><?= e(t('why_4_d')) ?></p></div>
      </div>
    </section>
    <?php
    render_course_cards(null);
    render_top3();
}

function render_dashboard()
{
    global $user;
    $uid = (int)$user['id'];
    ?>
    <section class="dash">
      <div class="dash-hi">
        <div class="dash-av"><?= e(mb_strtoupper(mb_substr($user['name'], 0, 1))) ?></div>
        <div>
          <h1><?= e(t('welcome_back')) ?>, <?= e($user['name']) ?>!</h1>
          <div class="dash-stats">
            <span class="chip chip-star">&#11088; <?= (int)$user['points'] ?></span>
            <span class="chip chip-fire">&#128293; <?= (int)$user['streak_days'] ?></span>
          </div>
        </div>
      </div>
    </section>
    <?php
    // Тавсияи дарси навбатӣ
    $best = null;
    foreach (courses() as $slug => $c) {
        if ($slug === 'full' && !full_course_unlocked($uid)) {
            continue;
        }
        $n = next_lesson_num($uid, $slug);
        $st = db()->prepare('SELECT id, num, title_tj, title_ru FROM cj_lessons WHERE course = ? AND num = ? AND published = 1');
        $st->execute(array($slug, $n));
        $L = $st->fetch();
        if ($L) {
            $done = course_done_count($uid, $slug);
            if ($best === null || $done > $best['done']) {
                $best = array('c' => $c, 'slug' => $slug, 'L' => $L, 'done' => $done);
            }
        }
    }
    if ($best !== null): ?>
      <a class="resume" href="?p=lesson&id=<?= (int)$best['L']['id'] ?>" style="--cc:<?= e($best['c']['color']) ?>">
        <div class="resume-ic"><?= $best['c']['icon'] ?></div>
        <div class="resume-txt">
          <span class="resume-label"><?= e(t('keep_going')) ?></span>
          <b><?= e(t('lesson_of')) ?> <?= (int)$best['L']['num'] ?> &middot; <?= e(fld('title', $best['L'])) ?></b>
        </div>
        <div class="resume-go">&rarr;</div>
      </a>
    <?php endif;

    echo '<h2 class="sec-title">' . e(t('home_title')) . '</h2>';
    render_course_cards($uid);
    render_top3();
}

function render_course_cards($userId)
{
    $fullOpen = $userId !== null ? full_course_unlocked($userId) : false;
    $counts = array();
    foreach (db()->query('SELECT course, COUNT(*) c FROM cj_lessons WHERE published = 1 GROUP BY course') as $r) {
        $counts[$r['course']] = (int)$r['c'];
    }
    ?>
    <section class="courses">
    <?php foreach (courses() as $slug => $c):
        $locked = ($slug === 'full') && ($userId === null || !$fullOpen);
        $done = $userId !== null ? course_done_count($userId, $slug) : 0;
        $ready = isset($counts[$slug]) ? $counts[$slug] : 0;
        $pct = (int)round($done / LESSONS_PER_COURSE * 100);
        ?>
        <div class="ccard <?= $locked ? 'locked' : '' ?>" style="--cc:<?= e($c['color']) ?>">
          <div class="ccard-head">
            <span class="ccard-ic"><?= $c['icon'] ?></span>
            <div>
              <div class="ccard-name"><?= e(fld('name', $c)) ?></div>
              <div class="ccard-meta"><?= $ready ?> <?= e(t('stat_lessons')) ?></div>
            </div>
            <?php if ($locked): ?><span class="ccard-lock">&#128274;</span><?php endif; ?>
          </div>
          <p class="ccard-desc"><?= e(fld('desc', $c)) ?></p>
          <?php if ($userId !== null && !$locked): ?>
            <div class="bar"><div class="bar-in" style="width:<?= $pct ?>%"></div></div>
            <div class="ccard-prog"><?= $done ?>/<?= LESSONS_PER_COURSE ?> <?= e(t('done_word')) ?></div>
          <?php endif; ?>
          <?php if ($locked): ?>
            <p class="ccard-hint"><?= e(t('full_locked_hint')) ?></p>
          <?php elseif ($ready > 0): ?>
            <a class="btn btn-cc" href="?p=course&c=<?= e($slug) ?>">
              <?= e(($userId !== null && $done > 0) ? t('continue') : t('open_course')) ?>
            </a>
          <?php else: ?>
            <span class="ccard-hint"><?= e(t('lesson_soon')) ?></span>
          <?php endif; ?>
        </div>
    <?php endforeach; ?>
    </section>
    <?php
}

function render_top3()
{
    $rows = db()->query(
        "SELECT name, city, points FROM cj_users WHERE banned = 0 AND points > 0
         ORDER BY points DESC, id ASC LIMIT 3"
    )->fetchAll();
    if (!$rows) {
        return;
    }
    $medals = array('&#129351;', '&#129352;', '&#129353;');
    ?>
    <section class="top3">
      <h2 class="sec-title"><?= e(t('top_students')) ?></h2>
      <div class="top3-list">
      <?php foreach ($rows as $i => $r): ?>
        <div class="top3-row">
          <span class="top3-medal"><?= $medals[$i] ?></span>
          <span class="top3-name"><?= e($r['name']) ?><?php if ($r['city'] !== ''): ?>
            <small><?= e($r['city']) ?></small><?php endif; ?></span>
          <span class="top3-pts"><?= (int)$r['points'] ?></span>
        </div>
      <?php endforeach; ?>
      </div>
    </section>
    <?php
}

/* ---------- Воридшавӣ ---------- */

function auth_err()
{
    if (empty($_SESSION['auth_err'])) {
        return null;
    }
    $k = $_SESSION['auth_err'];
    unset($_SESSION['auth_err']);
    return $k;
}

function page_enter()
{
    $err = auth_err();
    render_header(t('enter'), true);
    ?>
    <section class="auth">
      <div class="auth-ic">&#128241;</div>
      <h1><?= e(t('enter')) ?></h1>
      <p class="muted"><?= e(t('phone_hint')) ?></p>
      <?php if ($err !== null): ?><div class="alert alert-err"><?= e(t($err)) ?></div><?php endif; ?>
      <form method="post" action="index.php">
        <?= csrf_field() ?>
        <input type="hidden" name="action" value="phone">
        <label><?= e(t('phone')) ?>
          <div class="phone-row">
            <span class="phone-code">+992</span>
            <input type="tel" name="phone" inputmode="numeric" autocomplete="tel"
                   placeholder="<?= e(t('phone_ph')) ?>" required autofocus>
          </div>
        </label>
        <button class="btn btn-primary btn-block" type="submit"><?= e(t('phone_next')) ?> &rarr;</button>
      </form>
    </section>
    <?php
    render_footer();
}

function page_name()
{
    if (empty($_SESSION['reg_phone'])) {
        redirect('?p=enter');
    }
    $isFirst = ((int)db()->query('SELECT COUNT(*) FROM cj_users')->fetchColumn() === 0);
    $err = auth_err();
    render_header(t('name_title'), true);
    ?>
    <section class="auth">
      <div class="auth-ic">&#128075;</div>
      <h1><?= e(t('name_title')) ?></h1>
      <p class="muted"><?= e(t('name_hint')) ?></p>
      <div class="phone-shown"><?= e(pretty_phone($_SESSION['reg_phone'])) ?></div>
      <?php if ($err !== null): ?><div class="alert alert-err"><?= e(t($err)) ?></div><?php endif; ?>
      <form method="post" action="index.php">
        <?= csrf_field() ?>
        <input type="hidden" name="action" value="signup">
        <label><?= e(t('name')) ?>
          <input type="text" name="name" required maxlength="64" placeholder="<?= e(t('name_ph')) ?>" autofocus>
        </label>
        <label><?= e(t('city')) ?> <small>(<?= e(t('city_opt')) ?>)</small>
          <input type="text" name="city" maxlength="64" placeholder="<?= e(t('city_ph')) ?>">
        </label>
        <?php if ($isFirst): ?>
          <div class="alert alert-info"><?= e(t('pin_hint')) ?></div>
          <label><?= e(t('pin')) ?>
            <input type="text" name="pin" inputmode="numeric" pattern="[0-9]{4,6}" maxlength="6" required>
          </label>
        <?php endif; ?>
        <button class="btn btn-primary btn-block" type="submit"><?= e(t('start_learn')) ?> &rarr;</button>
      </form>
    </section>
    <?php
    render_footer();
}

function page_pin()
{
    if (empty($_SESSION['pin_uid'])) {
        redirect('?p=enter');
    }
    $err = auth_err();
    render_header(t('pin_title'), true);
    ?>
    <section class="auth">
      <div class="auth-ic">&#128274;</div>
      <h1><?= e(t('pin_title')) ?></h1>
      <p class="muted"><?= e(t('pin_ask')) ?></p>
      <?php if ($err !== null): ?><div class="alert alert-err"><?= e(t($err)) ?></div><?php endif; ?>
      <form method="post" action="index.php">
        <?= csrf_field() ?>
        <input type="hidden" name="action" value="pin">
        <label><?= e(t('pin')) ?>
          <input type="password" name="pin" inputmode="numeric" maxlength="6" required autofocus>
        </label>
        <button class="btn btn-primary btn-block" type="submit"><?= e(t('enter')) ?></button>
      </form>
    </section>
    <?php
    render_footer();
}

/* ---------- Курс ---------- */

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
        redirect('?p=enter');
    }
    if ($slug === 'full' && !full_course_unlocked((int)$user['id'])) {
        redirect('?p=home');
    }
    $c = $all[$slug];
    $uid = (int)$user['id'];

    $st = db()->prepare('SELECT id, num, title_tj, title_ru FROM cj_lessons WHERE course = ? AND published = 1 ORDER BY num');
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
    <section class="chead" style="--cc:<?= e($c['color']) ?>">
      <a class="back" href="?p=home">&larr; <?= e(t('back')) ?></a>
      <div class="chead-in">
        <span class="chead-ic"><?= $c['icon'] ?></span>
        <div>
          <h1><?= e(fld('name', $c)) ?></h1>
          <p class="muted"><?= e(fld('desc', $c)) ?></p>
        </div>
      </div>
      <div class="bar big"><div class="bar-in" style="width:<?= $pct ?>%"></div></div>
      <div class="chead-prog"><?= $doneCnt ?> <?= e(t('of')) ?> <?= LESSONS_PER_COURSE ?> <?= e(t('done_word')) ?> &middot; <?= $pct ?>%</div>
    </section>

    <?php foreach (levels() as $lvl => $lname):
        $from = ($lvl - 1) * LESSONS_PER_LEVEL + 1;
        $to = $lvl * LESSONS_PER_LEVEL;
        $hasAny = false;
        for ($n = $from; $n <= $to; $n++) {
            if (isset($lessons[$n])) { $hasAny = true; break; }
        }
        if (!$hasAny && $lvl > 1) {
            continue;   // сатҳҳои холиро нишон намедиҳем
        }
        ?>
        <section class="lvl" style="--cc:<?= e($c['color']) ?>">
          <div class="lvl-head">
            <h2><?= e(t('level')) ?> <?= $lvl ?> &mdash; <?= e(isset($lname[$lang]) ? $lname[$lang] : $lname['tj']) ?></h2>
          </div>
          <div class="lessons">
            <?php for ($n = $from; $n <= $to; $n++):
                $L = isset($lessons[$n]) ? $lessons[$n] : null;
                $isDone = isset($doneMap[$n]);
                $open = $L !== null && lesson_unlocked($uid, $slug, $n);
                if ($L === null): ?>
                  <div class="lrow soon">
                    <span class="lrow-n">&middot;&middot;&middot;</span>
                    <span class="lrow-t"><?= e(t('lesson_soon')) ?></span>
                  </div>
                <?php elseif ($open): ?>
                  <a class="lrow <?= $isDone ? 'done' : 'open' ?>" href="?p=lesson&id=<?= (int)$L['id'] ?>">
                    <span class="lrow-n"><?= $isDone ? '&check;' : $n ?></span>
                    <span class="lrow-t"><?= e(fld('title', $L)) ?></span>
                    <span class="lrow-go">&rarr;</span>
                  </a>
                <?php else: ?>
                  <div class="lrow lock">
                    <span class="lrow-n">&#128274;</span>
                    <span class="lrow-t"><?= e(fld('title', $L)) ?>
                      <small><?= e(t('lesson_locked')) ?></small></span>
                  </div>
                <?php endif;
            endfor; ?>
          </div>
        </section>
    <?php endforeach; ?>
    <?php
    render_footer();
}

/* ---------- Дарс: қадам ба қадам ---------- */

function page_lesson()
{
    global $user;
    if ($user === null) {
        flash_set('err', 'err_need_login');
        redirect('?p=enter');
    }
    $id = (int)(isset($_GET['id']) ? $_GET['id'] : 0);
    $st = db()->prepare('SELECT * FROM cj_lessons WHERE id = ? AND published = 1');
    $st->execute(array($id));
    $L = $st->fetch();
    if (!$L) {
        page_404();
        return;
    }
    $uid = (int)$user['id'];
    $slug = (string)$L['course'];
    $num = (int)$L['num'];

    if ($slug === 'full' && !full_course_unlocked($uid)) {
        redirect('?p=home');
    }
    if (!lesson_unlocked($uid, $slug, $num)) {
        redirect('?p=course&c=' . $slug);
    }
    $c = courses()[$slug];

    $st = db()->prepare('SELECT * FROM cj_drafts WHERE user_id = ? AND lesson_id = ?');
    $st->execute(array($uid, $id));
    $draft = $st->fetch();

    $startCode = (string)$L['task_start_code'];
    $htmlCode = $draft ? (string)$draft['html_code'] : $startCode;
    $cssCode  = $draft ? (string)$draft['css_code'] : '';
    $jsCode   = $draft ? (string)$draft['js_code'] : '';
    if (!$draft && $startCode === '') {
        $htmlCode = (string)$L['example_code'];
    }

    $st = db()->prepare('SELECT id, num, q_tj, q_ru, options_tj, options_ru, explain_tj, explain_ru FROM cj_questions WHERE lesson_id = ? ORDER BY num ASC, id ASC');
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

    $st = db()->prepare('SELECT id FROM cj_lessons WHERE course = ? AND num = ? AND published = 1');
    $st->execute(array($slug, $num + 1));
    $nextId = (int)$st->fetchColumn();

    $steps = theory_steps(fld('theory', $L));

    render_header(fld('title', $L));
    ?>
    <section class="lesson" style="--cc:<?= e($c['color']) ?>">
      <a class="back" href="?p=course&c=<?= e($slug) ?>">&larr; <?= e(fld('name', $c)) ?></a>
      <div class="lesson-title">
        <span class="lesson-num"><?= $num ?></span>
        <h1><?= e(fld('title', $L)) ?></h1>
      </div>

      <?php if ($steps): ?>
      <div class="card steps-card" id="steps">
        <div class="steps-top">
          <span class="steps-count"><?= e(t('step')) ?> <b id="stepNow">1</b> / <?= count($steps) ?></span>
          <div class="steps-dots" id="stepDots">
            <?php for ($i = 0; $i < count($steps); $i++): ?>
              <span class="dot <?= $i === 0 ? 'act' : '' ?>"></span>
            <?php endfor; ?>
          </div>
        </div>
        <?php foreach ($steps as $i => $s): ?>
          <div class="step <?= $i === 0 ? '' : 'hidden' ?>" data-step="<?= $i ?>">
            <?php if ($s['title'] !== ''): ?><h2 class="step-h"><?= e($s['title']) ?></h2><?php endif; ?>
            <div class="prose"><?= $s['body'] ?></div>
          </div>
        <?php endforeach; ?>
        <div class="steps-nav">
          <button class="btn btn-ghost" id="stepPrev" disabled>&larr; <?= e(t('step_prev')) ?></button>
          <button class="btn btn-primary" id="stepNext"><?= e(t('step_next')) ?> &rarr;</button>
        </div>
        <div class="steps-end hidden" id="stepsEnd">
          <b>&#127881; <?= e(t('step_done')) ?></b>
          <a class="btn btn-primary" href="#practice"><?= e(t('to_practice')) ?> &darr;</a>
        </div>
      </div>
      <?php endif; ?>

      <?php if ((string)$L['example_code'] !== ''): ?>
      <div class="card">
        <h2 class="card-h">&#128161; <?= e(t('example')) ?></h2>
        <pre class="code"><code id="exampleCode"><?= e((string)$L['example_code']) ?></code></pre>
        <button class="btn btn-ghost btn-sm" id="loadExample"><?= e(t('open_in_editor')) ?></button>
      </div>
      <?php endif; ?>

      <?php if (fld('task_text', $L) !== ''): ?>
      <div class="card task-card">
        <h2 class="card-h">&#9997;&#65039; <?= e(t('task')) ?></h2>
        <div class="prose"><?= fld('task_text', $L) ?></div>
      </div>
      <?php endif; ?>

      <div class="card" id="practice">
        <h2 class="card-h">&#128187; <?= e(t('practice')) ?></h2>
        <?php render_editor($id, $htmlCode, $cssCode, $jsCode, $startCode); ?>
      </div>

      <?php if ($questions): ?>
        <div class="card" id="test">
          <h2 class="card-h">&#128221; <?= e(t('test')) ?></h2>
          <?php render_test($id, $questions, $result, $testErr, $nextId); ?>
        </div>
      <?php endif; ?>
    </section>

    <script>
    (function () {
      var steps = document.querySelectorAll('.step');
      if (!steps.length) { return; }
      var dots = document.querySelectorAll('#stepDots .dot');
      var now = document.getElementById('stepNow');
      var prev = document.getElementById('stepPrev');
      var next = document.getElementById('stepNext');
      var end = document.getElementById('stepsEnd');
      var i = 0;
      function show(k) {
        i = Math.max(0, Math.min(steps.length - 1, k));
        for (var j = 0; j < steps.length; j++) {
          steps[j].classList.toggle('hidden', j !== i);
          if (dots[j]) { dots[j].classList.toggle('act', j <= i); }
        }
        now.textContent = i + 1;
        prev.disabled = (i === 0);
        next.classList.toggle('hidden', i === steps.length - 1);
        end.classList.toggle('hidden', i !== steps.length - 1);
        document.getElementById('steps').scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      prev.addEventListener('click', function () { show(i - 1); });
      next.addEventListener('click', function () { show(i + 1); });
    })();
    </script>
    <?php
    render_footer();
}

function render_editor($lessonId, $html, $css, $js, $startCode)
{
    ?>
    <div class="ed" id="edWrap" data-view="code">
      <div class="ed-bar">
        <div class="ed-tabs">
          <button class="ed-tab act" data-pane="html">HTML</button>
          <button class="ed-tab" data-pane="css">CSS</button>
          <button class="ed-tab" data-pane="js">JS</button>
        </div>
        <div class="ed-acts">
          <button class="ed-btn" id="btnRun">&#9654;</button>
          <button class="ed-btn" id="btnSave">&#128190;</button>
          <button class="ed-btn" id="btnReset">&#8635;</button>
          <button class="ed-btn" id="btnFull">&#9974;</button>
        </div>
      </div>
      <div class="ed-switch">
        <button class="sw act" data-view="code"><?= e(t('code')) ?></button>
        <button class="sw" data-view="preview"><?= e(t('preview')) ?></button>
        <button class="sw" data-view="console"><?= e(t('console')) ?> <b id="conBadge" class="hidden">0</b></button>
      </div>
      <div class="ed-body">
        <div class="ed-code">
          <div class="gutter" id="gutter">1</div>
          <textarea id="ta_html" class="ta" spellcheck="false"><?= e($html) ?></textarea>
          <textarea id="ta_css" class="ta hidden" spellcheck="false"><?= e($css) ?></textarea>
          <textarea id="ta_js" class="ta hidden" spellcheck="false"><?= e($js) ?></textarea>
        </div>
        <div class="ed-prev">
          <div class="ed-prev-bar"><span></span><span></span><span></span><i><?= e(t('preview')) ?></i></div>
          <iframe id="edFrame" sandbox="allow-scripts allow-modals" title="preview"></iframe>
        </div>
        <div class="ed-con">
          <div class="con-bar">
            <b>&gt;_ <?= e(t('console')) ?></b>
            <button class="ed-btn" id="conClear"><?= e(t('con_clear')) ?></button>
          </div>
          <div class="con-out" id="conOut"><div class="con-empty"><?= e(t('con_empty')) ?></div></div>
        </div>
      </div>
      <div class="ed-status">
        <span id="edSaveState" class="muted"></span>
        <span id="edErr" class="ed-err"></span>
      </div>
    </div>

    <div class="ai-box">
      <button class="btn btn-ai btn-block" id="aiBtn">&#129302; <?= e(t('ai_check')) ?></button>
      <p class="ai-note muted"><?= e(t('ai_need')) ?></p>
      <div id="aiOut"></div>
    </div>

    <script>
    (function () {
      var LESSON_ID = <?= (int)$lessonId ?>;
      var START = <?= json_encode((string)$startCode, JSON_UNESCAPED_UNICODE) ?>;
      var TXT = {
        saved: <?= json_encode(t('saved'), JSON_UNESCAPED_UNICODE) ?>,
        saving: <?= json_encode(t('saving'), JSON_UNESCAPED_UNICODE) ?>,
        saveErr: <?= json_encode(t('save_err'), JSON_UNESCAPED_UNICODE) ?>,
        checking: <?= json_encode(t('ai_checking'), JSON_UNESCAPED_UNICODE) ?>,
        aiErr: <?= json_encode(t('ai_err'), JSON_UNESCAPED_UNICODE) ?>,
        passed: <?= json_encode(t('ai_passed'), JSON_UNESCAPED_UNICODE) ?>,
        failed: <?= json_encode(t('ai_failed'), JSON_UNESCAPED_UNICODE) ?>,
        errs: <?= json_encode(t('ai_errors'), JSON_UNESCAPED_UNICODE) ?>,
        advice: <?= json_encode(t('ai_advice'), JSON_UNESCAPED_UNICODE) ?>,
        line: <?= json_encode(t('ai_line'), JSON_UNESCAPED_UNICODE) ?>,
        left: <?= json_encode(t('ai_left'), JSON_UNESCAPED_UNICODE) ?>,
        sec: <?= json_encode(t('ai_sec'), JSON_UNESCAPED_UNICODE) ?>,
        check: <?= json_encode(t('ai_check'), JSON_UNESCAPED_UNICODE) ?>,
        conEmpty: <?= json_encode(t('con_empty'), JSON_UNESCAPED_UNICODE) ?>
      };
      var csrfEl = document.querySelector('input[name="csrf"]');
      var CSRF = csrfEl ? csrfEl.value : '';
      var areas = { html: document.getElementById('ta_html'), css: document.getElementById('ta_css'), js: document.getElementById('ta_js') };
      var frame = document.getElementById('edFrame');
      var errBox = document.getElementById('edErr');
      var saveState = document.getElementById('edSaveState');
      var wrap = document.getElementById('edWrap');
      var pasted = false, timer = null;

      function val(k) { return areas[k] ? areas[k].value : ''; }

      function build() {
        var h = val('html'), c = val('css'), j = val('js');
        var doc = h;
        if (h.toLowerCase().indexOf('<html') === -1) {
          doc = '<!doctype html><html><head><meta charset="utf-8">'
              + '<meta name="viewport" content="width=device-width,initial-scale=1">'
              + '<style>body{font-family:system-ui,sans-serif;padding:14px;line-height:1.6;color:#111}</style>'
              + '<style>' + c + '</style></head><body>' + h + '</body></html>';
        } else if (c) {
          doc = doc.replace(/<\/head>/i, '<style>' + c + '</style></head>');
        }
        // Пули терминал: console.log-и дохили iframe-ро ба мо мефиристад
        var bridge = '<' + 'script>(function(){'
          + 'function send(t,a){try{parent.postMessage({cjLog:1,type:t,args:Array.prototype.slice.call(a).map(function(x){'
          + 'try{return (typeof x==="object"&&x!==null)?JSON.stringify(x):String(x)}catch(e){return String(x)}})},"*")}catch(e){}}'
          + 'var c=window.console||{};["log","info","warn","error"].forEach(function(m){'
          + 'var o=c[m];c[m]=function(){send(m,arguments);if(o){try{o.apply(c,arguments)}catch(e){}}}});window.console=c;'
          + 'window.onerror=function(m,s,l){send("error",[m+" ("+TXTLINE+" "+l+")"]);parent.postMessage({codetjErr:m,line:l},"*");return true};'
          + 'window.addEventListener("unhandledrejection",function(e){send("error",[String(e.reason)])});'
          + '})();<' + '/script>';
        bridge = bridge.replace('TXTLINE', JSON.stringify(TXT.line));
        if (doc.toLowerCase().indexOf('<head') !== -1) {
          doc = doc.replace(/<head([^>]*)>/i, '<head$1>' + bridge);
        } else {
          doc = bridge + doc;
        }

        if (j) {
          var s = '<' + 'script>try{' + j + '\n}catch(e){console.error(e.message)}<' + '/script>';
          if (doc.toLowerCase().indexOf('</body>') !== -1) {
            doc = doc.replace(/<\/body>/i, s + '</body>');
          } else { doc += s; }
        }
        return doc;
      }

      /* ---- терминал ---- */
      var conOut = document.getElementById('conOut');
      var conBadge = document.getElementById('conBadge');
      var conCount = 0;
      function conAdd(type, text) {
        var empty = conOut.querySelector('.con-empty');
        if (empty) { empty.remove(); }
        var row = document.createElement('div');
        row.className = 'con-row con-' + type;
        var t = new Date();
        var hh = ('0' + t.getHours()).slice(-2) + ':' + ('0' + t.getMinutes()).slice(-2) + ':' + ('0' + t.getSeconds()).slice(-2);
        row.innerHTML = '<span class="con-time">' + hh + '</span><span class="con-txt"></span>';
        row.querySelector('.con-txt').textContent = text;
        conOut.appendChild(row);
        conOut.scrollTop = conOut.scrollHeight;
        conCount++;
        if (conBadge) {
          conBadge.textContent = conCount;
          conBadge.classList.remove('hidden');
        }
      }
      function conReset() {
        conOut.innerHTML = '<div class="con-empty"></div>';
        conOut.firstChild.textContent = TXT.conEmpty;
        conCount = 0;
        if (conBadge) { conBadge.classList.add('hidden'); }
      }
      document.getElementById('conClear').addEventListener('click', conReset);

      function run() { errBox.textContent = ''; conReset(); frame.srcdoc = build(); }

      window.addEventListener('message', function (ev) {
        if (!ev.data) { return; }
        if (ev.data.cjLog) {
          conAdd(ev.data.type, (ev.data.args || []).join(' '));
          return;
        }
        if (ev.data.codetjErr) {
          errBox.textContent = 'JS: ' + ev.data.codetjErr + (ev.data.line ? ' (' + ev.data.line + ')' : '');
        }
      });

      /* ---- рақами сатрҳо ---- */
      var gutter = document.getElementById('gutter');
      function syncGutter() {
        var a = null;
        Object.keys(areas).forEach(function (k) {
          if (areas[k] && !areas[k].classList.contains('hidden')) { a = areas[k]; }
        });
        if (!a || !gutter) { return; }
        var n = a.value.split('\n').length;
        var s = '';
        for (var i = 1; i <= n; i++) { s += i + '\n'; }
        gutter.textContent = s;
        gutter.scrollTop = a.scrollTop;
      }
      function schedule() { syncGutter(); if (timer) { clearTimeout(timer); } timer = setTimeout(run, 600); }

      Object.keys(areas).forEach(function (k) {
        if (!areas[k]) { return; }
        areas[k].addEventListener('input', schedule);
        areas[k].addEventListener('scroll', function () { if (gutter) { gutter.scrollTop = this.scrollTop; } });
        areas[k].addEventListener('paste', function () { pasted = true; });
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

      var tabs = document.querySelectorAll('.ed-tab');
      for (var i = 0; i < tabs.length; i++) {
        tabs[i].addEventListener('click', function () {
          for (var j = 0; j < tabs.length; j++) { tabs[j].classList.remove('act'); }
          this.classList.add('act');
          var pane = this.getAttribute('data-pane');
          Object.keys(areas).forEach(function (k) {
            if (areas[k]) { areas[k].classList.toggle('hidden', k !== pane); }
          });
          syncGutter();
        });
      }
      var sw = document.querySelectorAll('.sw');
      for (var m = 0; m < sw.length; m++) {
        sw[m].addEventListener('click', function () {
          for (var n = 0; n < sw.length; n++) { sw[n].classList.remove('act'); }
          this.classList.add('act');
          wrap.setAttribute('data-view', this.getAttribute('data-view'));
          run();
        });
      }
      document.getElementById('btnRun').addEventListener('click', function () {
        wrap.setAttribute('data-view', 'preview');
        for (var n = 0; n < sw.length; n++) { sw[n].classList.toggle('act', sw[n].getAttribute('data-view') === 'preview'); }
        run();
      });
      document.getElementById('btnFull').addEventListener('click', function () {
        wrap.classList.toggle('full');
        document.body.classList.toggle('noscroll', wrap.classList.contains('full'));
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
        fd.append('action', 'savedraft'); fd.append('csrf', CSRF);
        fd.append('lesson_id', LESSON_ID);
        fd.append('html', val('html')); fd.append('css', val('css')); fd.append('js', val('js'));
        fd.append('pasted', pasted ? '1' : '0');
        fetch('index.php', { method: 'POST', body: fd, credentials: 'same-origin' })
          .then(function (r) { return r.json(); })
          .then(function (d) { saveState.textContent = d && d.ok ? TXT.saved : TXT.saveErr; })
          .catch(function () { saveState.textContent = TXT.saveErr; });
      }
      document.getElementById('btnSave').addEventListener('click', function () { save(false); });
      setInterval(function () { save(true); }, 20000);

      var loadEx = document.getElementById('loadExample');
      if (loadEx) {
        loadEx.addEventListener('click', function () {
          var ex = document.getElementById('exampleCode');
          if (ex && areas.html) {
            areas.html.value = ex.textContent;
            syncGutter();
            run();
            document.getElementById('practice').scrollIntoView({ behavior: 'smooth' });
          }
        });
      }

      /* ---- санҷиши AI ---- */
      var aiBtn = document.getElementById('aiBtn');
      var aiOut = document.getElementById('aiOut');
      var busy = false;

      function esc(s) {
        var d = document.createElement('div');
        d.textContent = String(s == null ? '' : s);
        return d.innerHTML;
      }
      function aiMsg(cls, html) { aiOut.innerHTML = '<div class="ai-res ' + cls + '">' + html + '</div>'; }

      aiBtn.addEventListener('click', function () {
        if (busy) { return; }
        busy = true;
        aiBtn.disabled = true;
        aiMsg('wait', '<div class="ai-spin"></div><b>' + esc(TXT.checking) + '</b>');

        var fd = new FormData();
        fd.append('action', 'ai_check'); fd.append('csrf', CSRF);
        fd.append('lesson_id', LESSON_ID);
        fd.append('html', val('html')); fd.append('css', val('css')); fd.append('js', val('js'));

        fetch('index.php', { method: 'POST', body: fd, credentials: 'same-origin' })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (!d || !d.ok) {
              var m = (d && d.msg) ? d.msg : TXT.aiErr;
              if (d && d.wait) { m += ' — ' + d.wait + ' ' + TXT.sec; }
              aiMsg('bad', esc(m));
              return;
            }
            var r = d.res, h = '';
            h += '<div class="ai-top"><span class="ai-badge ' + (r.passed ? 'ok' : 'no') + '">'
               + (r.passed ? '&#9989; ' + esc(TXT.passed) : '&#128260; ' + esc(TXT.failed))
               + '</span><span class="ai-score">' + (r.score | 0) + '/100</span></div>';
            if (r.praise) { h += '<p class="ai-praise">' + esc(r.praise) + '</p>'; }
            if (r.errors && r.errors.length) {
              h += '<div class="ai-sec"><b>' + esc(TXT.errs) + '</b><ul class="ai-errs">';
              for (var i = 0; i < r.errors.length; i++) {
                var er = r.errors[i];
                h += '<li>' + (er.line ? '<code>' + esc(TXT.line) + ' ' + (er.line | 0) + '</code> ' : '')
                   + esc(er.text) + '</li>';
              }
              h += '</ul></div>';
            }
            if (r.advice) {
              h += '<div class="ai-sec"><b>&#128161; ' + esc(TXT.advice) + '</b><p>' + esc(r.advice) + '</p></div>';
            }
            h += '<div class="ai-foot">' + esc(TXT.left) + ': ' + (r.left | 0) + '</div>';
            aiMsg(r.passed ? 'good' : 'bad', h);
            if (r.passed) {
              setTimeout(function () {
                var tst = document.getElementById('test');
                if (tst) { tst.scrollIntoView({ behavior: 'smooth' }); }
              }, 1200);
            }
          })
          .catch(function () { aiMsg('bad', esc(TXT.aiErr)); })
          .then(function () { busy = false; aiBtn.disabled = false; });
      });

      syncGutter();
      run();
    })();
    </script>
    <?php
}

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
      <?php
      // Баҳо аз рӯи шумораи ҷавобҳои дуруст (аз 10): 0–3, 4–6, 7–8, 9–10
      $ratio = $result['total'] > 0 ? $result['correct'] / $result['total'] : 0;
      if ($ratio >= 0.9)      { $gk = 'grade_4'; $ge = '&#127942;'; }
      elseif ($ratio >= 0.7)  { $gk = 'grade_3'; $ge = '&#128077;'; }
      elseif ($ratio >= 0.4)  { $gk = 'grade_2'; $ge = '&#128076;'; }
      else                    { $gk = 'grade_1'; $ge = '&#128218;'; }
      ?>
      <div class="tres <?= $result['passed'] ? 'ok' : 'bad' ?>">
        <div class="tres-score"><?= (int)$result['correct'] ?><small>/<?= (int)$result['total'] ?></small></div>
        <div>
          <b><?= e($result['passed'] ? t('test_passed') : t('test_failed')) ?></b>
          <div class="tres-grade"><?= $ge ?> <?= e(t('grade_word')) ?>: <b><?= e(t($gk)) ?></b></div>
          <div class="muted"><?= (int)$result['correct'] ?> <?= e(t('answers_right')) ?> &middot;
            <?= e(t('you_got')) ?> +<?= (int)$result['gained'] ?></div>
        </div>
      </div>
      <?php if (!empty($result['newly'])): ?>
        <div class="done-box">
          <div class="done-emoji">&#127881;</div>
          <b><?= e(t('lesson_done')) ?></b>
          <p class="muted"><?= e(t('lesson_done_txt')) ?></p>
          <?php if ($nextId > 0): ?>
            <a class="btn btn-primary" href="?p=lesson&id=<?= (int)$nextId ?>"><?= e(t('next_lesson')) ?> &rarr;</a>
          <?php endif; ?>
        </div>
      <?php endif; ?>
    <?php else: ?>
      <p class="muted"><?= e(t('test_intro')) ?></p>
    <?php endif; ?>

    <?php if ($testErr !== null): ?><div class="alert alert-err"><?= e(t($testErr)) ?></div><?php endif; ?>

    <form method="post" action="index.php" class="tform">
      <?= csrf_field() ?>
      <input type="hidden" name="action" value="test">
      <input type="hidden" name="lesson_id" value="<?= (int)$lessonId ?>">
      <?php foreach ($questions as $qi => $q):
          $qid = (int)$q['id'];
          // Агар тарҷумаи русӣ набошад — тоҷикиро нишон медиҳем.
          $optRaw = ($lang === 'ru' && trim((string)$q['options_ru']) !== '') ? $q['options_ru'] : $q['options_tj'];
          $opts = json_decode((string)$optRaw, true);
          if (!is_array($opts) || !$opts) {
              $opts = json_decode((string)$q['options_tj'], true);
          }
          if (!is_array($opts)) { $opts = array(); }
          $qText = ($lang === 'ru' && trim((string)$q['q_ru']) !== '') ? $q['q_ru'] : $q['q_tj'];
          $exText = ($lang === 'ru' && trim((string)$q['explain_ru']) !== '') ? $q['explain_ru'] : $q['explain_tj'];
          $order = array_keys($opts);
          shuffle($order);
          $d = isset($detail[$qid]) ? $detail[$qid] : null;
          ?>
          <div class="q <?= $d ? ($d['right'] ? 'q-ok' : 'q-bad') : '' ?>">
            <div class="q-t"><span class="q-n"><?= $qi + 1 ?></span> <?= e($qText) ?></div>
            <div class="q-opts">
              <?php foreach ($order as $oi):
                  $checked = ($d !== null && (int)$d['given'] === (int)$oi);
                  $isCorrect = ($d !== null && (int)$d['correct'] === (int)$oi);
                  ?>
                  <label class="opt <?= $isCorrect ? 'good' : '' ?> <?= ($checked && !$isCorrect) ? 'wrong' : '' ?>">
                    <input type="radio" name="a[<?= $qid ?>]" value="<?= (int)$oi ?>" <?= $checked ? 'checked' : '' ?> required>
                    <span><?= e((string)$opts[$oi]) ?></span>
                  </label>
              <?php endforeach; ?>
            </div>
            <?php if ($d !== null):
                $ex = $exText;
                if (!empty($d['reveal']) && (string)$ex !== ''): ?>
                  <div class="q-ex"><?= $d['right'] ? '&#9989; ' : '&#128161; ' ?><?= e((string)$ex) ?></div>
                <?php elseif (!$d['right']): ?>
                  <div class="q-ex">&#128260; <?= e(t('try_once_more')) ?></div>
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

function page_rating()
{
    global $user;
    $rows = db()->query(
        "SELECT name, city, points, streak_days FROM cj_users WHERE banned = 0 AND points > 0
         ORDER BY points DESC, id ASC LIMIT 50"
    )->fetchAll();
    render_header(t('nav_rating'));
    ?>
    <h1 class="page-h">&#127942; <?= e(t('top_students')) ?></h1>
    <?php if (!$rows): ?>
      <p class="muted"><?= e(t('no_students')) ?></p>
    <?php else: ?>
      <div class="rank-list">
        <?php foreach ($rows as $i => $r):
            $me = ($user !== null && $r['name'] === $user['name']);
            $medal = $i === 0 ? '&#129351;' : ($i === 1 ? '&#129352;' : ($i === 2 ? '&#129353;' : (string)($i + 1)));
            ?>
            <div class="rank <?= $me ? 'me' : '' ?>">
              <span class="rank-n"><?= $medal ?></span>
              <span class="rank-name"><?= e($r['name']) ?>
                <?php if ($r['city'] !== ''): ?><small><?= e($r['city']) ?></small><?php endif; ?></span>
              <span class="rank-pts">&#11088; <?= (int)$r['points'] ?></span>
            </div>
        <?php endforeach; ?>
      </div>
    <?php endif;
    render_footer();
}

function page_profile()
{
    global $user;
    $uid = (int)$user['id'];
    $st = db()->prepare('SELECT COUNT(*) + 1 FROM cj_users WHERE banned = 0 AND points > ?');
    $st->execute(array((int)$user['points']));
    $rank = (int)$st->fetchColumn();

    render_header(t('nav_profile'));
    ?>
    <section class="prof">
      <div class="prof-av"><?= e(mb_strtoupper(mb_substr($user['name'], 0, 1))) ?></div>
      <h1><?= e($user['name']) ?></h1>
      <?php if ($user['city'] !== ''): ?><p class="muted">&#128205; <?= e($user['city']) ?></p><?php endif; ?>
      <?php if ((string)$user['phone'] !== ''): ?>
        <p class="muted small"><?= e(pretty_phone($user['phone'])) ?></p>
      <?php endif; ?>
      <div class="prof-stats">
        <div class="pstat"><b><?= (int)$user['points'] ?></b><span><?= e(t('points')) ?></span></div>
        <div class="pstat"><b><?= (int)$user['streak_days'] ?></b><span><?= e(t('streak')) ?></span></div>
        <div class="pstat"><b><?= $rank ?></b><span><?= e(t('rank')) ?></span></div>
      </div>
    </section>
    <h2 class="sec-title"><?= e(t('my_progress')) ?></h2>
    <section class="prof-prog">
      <?php foreach (courses() as $slug => $c):
          $done = course_done_count($uid, $slug);
          $pct = (int)round($done / LESSONS_PER_COURSE * 100);
          ?>
          <div class="prow" style="--cc:<?= e($c['color']) ?>">
            <span class="prow-name"><?= $c['icon'] ?> <?= e(fld('name', $c)) ?></span>
            <div class="bar"><div class="bar-in" style="width:<?= $pct ?>%"></div></div>
            <span class="prow-n"><?= $done ?>/<?= LESSONS_PER_COURSE ?></span>
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
    <section class="auth" style="text-align:center">
      <div class="auth-ic">&#129335;</div>
      <p><?= e(t('err_not_found')) ?></p>
      <a class="btn btn-primary" href="?p=home"><?= e(t('nav_home')) ?></a>
    </section>
    <?php
    render_footer();
}

/* ============================================================
 *  ҚОЛИБ
 * ============================================================ */

function render_header($title, $bare = false)
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
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0a0e1a">
<title><?= e($title) ?> — CodeTJ</title>
<meta name="description" content="<?= e(t('tagline')) ?>">
<style><?php render_css(); ?></style>
</head>
<body>
<header class="top">
  <a class="logo" href="?p=home"><span class="logo-d">&lt;/&gt;</span> Code<b>TJ</b></a>
  <div class="top-right">
    <form method="post" action="index.php" class="lang">
      <?= csrf_field() ?>
      <input type="hidden" name="action" value="setlang">
      <input type="hidden" name="back" value="<?= e($backUrl) ?>">
      <button type="submit" name="lang" value="tj" class="lang-b <?= $lang === 'tj' ? 'act' : '' ?>"><?= e(t('lang_tj')) ?></button>
      <button type="submit" name="lang" value="ru" class="lang-b <?= $lang === 'ru' ? 'act' : '' ?>"><?= e(t('lang_ru')) ?></button>
    </form>
    <button id="themeBtn" class="ibtn"><?= $theme === 'light' ? '&#127769;' : '&#9728;&#65039;' ?></button>
    <?php if ($user !== null): ?>
      <form method="post" action="index.php" style="display:inline">
        <?= csrf_field() ?>
        <input type="hidden" name="action" value="logout">
        <button type="submit" class="ibtn">&#8617;</button>
      </form>
    <?php elseif (!$bare): ?>
      <a class="btn btn-primary btn-sm" href="?p=enter"><?= e(t('enter')) ?></a>
    <?php endif; ?>
  </div>
</header>
<main class="wrap">
<?php if ($flash !== null): ?>
  <div class="alert <?= $flash['type'] === 'ok' ? 'alert-ok' : 'alert-err' ?>"><?= e(t($flash['key'])) ?></div>
<?php endif; ?>
    <?php
}

function render_footer()
{
    global $user, $p;
    ?>
</main>
<?php if ($user !== null): ?>
<nav class="tabbar">
  <a href="?p=home" class="<?= $p === 'home' ? 'act' : '' ?>"><span>&#127968;</span><i><?= e(t('nav_home')) ?></i></a>
  <a href="?p=rating" class="<?= $p === 'rating' ? 'act' : '' ?>"><span>&#127942;</span><i><?= e(t('nav_rating')) ?></i></a>
  <a href="?p=profile" class="<?= $p === 'profile' ? 'act' : '' ?>"><span>&#128100;</span><i><?= e(t('nav_profile')) ?></i></a>
</nav>
<?php endif; ?>
<footer class="foot"><b>CodeTJ</b> &middot; <?= e(t('footer_note')) ?></footer>
<script>
(function () {
  var b = document.getElementById('themeBtn');
  if (!b) { return; }
  b.addEventListener('click', function () {
    var light = document.documentElement.classList.toggle('light');
    b.innerHTML = light ? '&#127769;' : '&#9728;&#65039;';
    document.cookie = 'codetj_theme=' + (light ? 'light' : 'dark') + ';path=/;max-age=31536000;samesite=Lax';
    var c = document.querySelector('input[name="csrf"]');
    if (c) {
      var fd = new FormData();
      fd.append('action', 'settheme'); fd.append('theme', light ? 'light' : 'dark'); fd.append('csrf', c.value);
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
  --bg:#0a0e1a;--bg2:#111729;--card:#151d33;--card2:#1b2542;--line:#26304d;
  --txt:#eef2fb;--mut:#8b9ac0;--acc:#5b8cff;--acc2:#a855f7;
  --ok:#22c55e;--err:#f43f5e;--warn:#f59e0b;
  --r:20px;--sh:0 8px 32px rgba(0,0,0,.4);
}
html.light{
  --bg:#f6f8fd;--bg2:#eef2fa;--card:#fff;--card2:#f7f9fd;--line:#e2e8f4;
  --txt:#0f172a;--mut:#5a6b8c;--sh:0 6px 24px rgba(15,23,42,.08);
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Noto Sans',system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;
 background:var(--bg);color:var(--txt);line-height:1.65;min-height:100vh;
 display:flex;flex-direction:column;-webkit-font-smoothing:antialiased;
 -webkit-tap-highlight-color:transparent}
body.noscroll{overflow:hidden}
a{color:var(--acc);text-decoration:none}
h1,h2,h3{line-height:1.25;font-weight:800;letter-spacing:-.02em}
.hidden{display:none!important}
.muted{color:var(--mut)}
.small{font-size:.85rem}
.center{text-align:center}
.wrap{width:100%;max-width:900px;margin:0 auto;padding:16px 14px 90px;flex:1}

/* ---- шапка ---- */
.top{position:sticky;top:0;z-index:60;display:flex;align-items:center;justify-content:space-between;
 gap:10px;padding:10px 14px;background:rgba(10,14,26,.85);backdrop-filter:blur(14px);
 border-bottom:1px solid var(--line)}
html.light .top{background:rgba(246,248,253,.85)}
.logo{font-size:1.15rem;font-weight:800;color:var(--txt);display:flex;align-items:center;gap:7px}
.logo b{background:linear-gradient(135deg,var(--acc),var(--acc2));-webkit-background-clip:text;
 background-clip:text;-webkit-text-fill-color:transparent}
.logo-d{font-family:ui-monospace,monospace;color:var(--acc);font-size:.9rem;opacity:.7}
.top-right{display:flex;align-items:center;gap:7px}
.lang{display:flex;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.lang-b{background:none;border:0;color:var(--mut);padding:6px 9px;font:700 .78rem inherit;cursor:pointer}
.lang-b.act{background:var(--acc);color:#fff}
.ibtn{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:6px 10px;
 cursor:pointer;font-size:.95rem;color:var(--txt);line-height:1}

/* ---- кнопки ---- */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;border:0;cursor:pointer;
 font:700 1rem inherit;padding:13px 24px;border-radius:14px;color:var(--txt);transition:transform .12s,filter .12s}
.btn:active{transform:scale(.97)}
.btn-primary{background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;
 box-shadow:0 6px 20px rgba(91,140,255,.32)}
.btn-ghost{background:var(--card2);border:1px solid var(--line)}
.btn-ghost:disabled{opacity:.4}
.btn-sm{padding:8px 14px;font-size:.88rem;border-radius:11px}
.btn-lg{padding:16px 32px;font-size:1.05rem}
.btn-block{width:100%}
.btn-cc{background:var(--cc);color:#fff;width:100%;padding:12px}

/* ---- уведомления ---- */
.alert{padding:12px 16px;border-radius:14px;margin-bottom:14px;font-weight:600;font-size:.92rem}
.alert-ok{background:rgba(34,197,94,.14);border:1px solid var(--ok);color:var(--ok)}
.alert-err{background:rgba(244,63,94,.14);border:1px solid var(--err);color:var(--err)}
.alert-info{background:rgba(91,140,255,.12);border:1px solid var(--acc);color:var(--txt);font-weight:400}

/* ---- главная ---- */
.hero{text-align:center;padding:38px 6px 30px}
.hero-badge{display:inline-block;background:var(--card);border:1px solid var(--line);
 border-radius:99px;padding:6px 16px;font-size:.82rem;font-weight:700;color:var(--mut);margin-bottom:16px}
.hero h1{font-size:clamp(1.75rem,7vw,2.9rem);
 background:linear-gradient(135deg,var(--txt) 30%,var(--acc));-webkit-background-clip:text;
 background-clip:text;-webkit-text-fill-color:transparent}
.hero-sub{color:var(--mut);max-width:520px;margin:14px auto 24px;font-size:1.02rem}
.hero-stats{display:flex;gap:10px;justify-content:center;margin-top:32px;flex-wrap:wrap}
.hstat{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:12px 22px;min-width:98px}
.hstat b{display:block;font-size:1.4rem;color:var(--acc)}
.hstat span{color:var(--mut);font-size:.78rem}

.sec-title{font-size:1.2rem;margin:26px 0 14px}
.page-h{font-size:1.5rem;margin:8px 0 18px}
.why-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.why-card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:20px}
.why-ic{font-size:1.7rem;margin-bottom:8px}
.why-card h3{font-size:1rem;margin-bottom:5px}
.why-card p{color:var(--mut);font-size:.9rem}

/* ---- дашборд ---- */
.dash-hi{display:flex;align-items:center;gap:14px;padding:14px 0 4px}
.dash-av{width:56px;height:56px;border-radius:18px;flex-shrink:0;font-size:1.5rem;font-weight:800;
 background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;
 display:flex;align-items:center;justify-content:center}
.dash-hi h1{font-size:1.25rem}
.dash-stats{display:flex;gap:6px;margin-top:6px}
.chip{background:var(--card);border:1px solid var(--line);border-radius:99px;padding:4px 12px;
 font-size:.85rem;font-weight:700}
.chip-star{color:var(--warn)}
.chip-fire{color:#fb7185}

.resume{display:flex;align-items:center;gap:14px;background:var(--card);border:1px solid var(--line);
 border-left:4px solid var(--cc);border-radius:var(--r);padding:16px;margin-top:16px;color:var(--txt);
 box-shadow:var(--sh)}
.resume-ic{font-size:1.8rem}
.resume-txt{flex:1;min-width:0}
.resume-label{display:block;font-size:.75rem;color:var(--mut);text-transform:uppercase;letter-spacing:.06em}
.resume-txt b{display:block;font-size:.98rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.resume-go{font-size:1.3rem;color:var(--cc)}

/* ---- курсы ---- */
.courses{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.ccard{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:18px;
 display:flex;flex-direction:column;gap:10px;position:relative;overflow:hidden}
.ccard::before{content:'';position:absolute;inset:0 0 auto 0;height:4px;background:var(--cc)}
.ccard.locked{opacity:.6}
.ccard-head{display:flex;align-items:center;gap:11px}
.ccard-ic{font-size:1.7rem}
.ccard-name{font-size:1.15rem;font-weight:800}
.ccard-meta{font-size:.78rem;color:var(--mut)}
.ccard-lock{margin-left:auto}
.ccard-desc{color:var(--mut);font-size:.89rem;flex:1}
.ccard-prog{font-size:.8rem;color:var(--mut)}
.ccard-hint{font-size:.83rem;color:var(--mut);background:var(--bg2);border-radius:12px;padding:10px 12px}
.bar{height:8px;background:var(--bg2);border-radius:99px;overflow:hidden}
.bar.big{height:11px;margin-top:14px}
.bar-in{height:100%;background:var(--cc,var(--acc));border-radius:99px;transition:width .5s}

/* ---- топ-3 ---- */
.top3-list{display:flex;flex-direction:column;gap:8px}
.top3-row,.rank{display:flex;align-items:center;gap:12px;background:var(--card);
 border:1px solid var(--line);border-radius:15px;padding:11px 15px}
.top3-medal,.rank-n{font-size:1.15rem;width:30px;text-align:center;font-weight:800;color:var(--mut)}
.top3-name,.rank-name{flex:1;font-weight:700;min-width:0}
.top3-name small,.rank-name small{display:block;font-weight:400;color:var(--mut);font-size:.78rem}
.top3-pts,.rank-pts{font-weight:800;color:var(--warn)}
.rank-list{display:flex;flex-direction:column;gap:7px}
.rank.me{border-color:var(--acc);background:rgba(91,140,255,.1)}

/* ---- вход ---- */
.auth{max-width:400px;margin:26px auto;background:var(--card);border:1px solid var(--line);
 border-radius:24px;padding:30px 24px;box-shadow:var(--sh);text-align:center}
.auth-ic{font-size:2.6rem;margin-bottom:10px}
.auth h1{font-size:1.4rem;margin-bottom:8px}
.auth form{display:flex;flex-direction:column;gap:14px;margin-top:20px;text-align:left}
.auth label{display:flex;flex-direction:column;gap:6px;font-weight:700;font-size:.88rem}
.auth label small{font-weight:400;color:var(--mut)}
.auth input{background:var(--bg2);border:2px solid var(--line);border-radius:14px;padding:14px;
 color:var(--txt);font:1.05rem inherit;width:100%}
.auth input:focus{outline:0;border-color:var(--acc)}
.phone-row{display:flex;align-items:center;gap:8px;background:var(--bg2);border:2px solid var(--line);
 border-radius:14px;padding-left:14px}
.phone-row:focus-within{border-color:var(--acc)}
.phone-row input{border:0;background:none;padding-left:0;letter-spacing:.06em}
.phone-code{font-weight:800;color:var(--mut)}
.phone-shown{background:var(--bg2);border-radius:12px;padding:9px;font-weight:800;
 letter-spacing:.04em;margin-top:12px}

/* ---- курс ---- */
.back{color:var(--mut);font-weight:700;font-size:.88rem;display:inline-block;padding:6px 0}
.chead{padding:4px 0 10px}
.chead-in{display:flex;gap:13px;align-items:center;margin:8px 0}
.chead-ic{font-size:2.1rem}
.chead h1{font-size:1.6rem}
.chead p{font-size:.88rem}
.chead-prog{font-size:.83rem;color:var(--mut);margin-top:7px}
.lvl{margin-top:22px}
.lvl-head h2{font-size:1rem;color:var(--mut);text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px}
.lessons{display:flex;flex-direction:column;gap:8px}
.lrow{display:flex;align-items:center;gap:13px;background:var(--card);border:1px solid var(--line);
 border-radius:15px;padding:13px 15px;color:var(--txt)}
.lrow-n{width:32px;height:32px;flex-shrink:0;border-radius:11px;background:var(--bg2);
 display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.9rem;color:var(--mut)}
.lrow-t{flex:1;font-weight:600;font-size:.94rem;min-width:0}
.lrow-t small{display:block;font-size:.76rem;color:var(--mut);font-weight:400}
.lrow-go{color:var(--cc);font-size:1.1rem}
.lrow.open{border-color:var(--cc)}
.lrow.open .lrow-n{background:var(--cc);color:#fff}
.lrow.done .lrow-n{background:var(--ok);color:#fff}
.lrow.lock,.lrow.soon{opacity:.5}

/* ---- урок ---- */
.lesson-title{display:flex;align-items:flex-start;gap:12px;margin:10px 0 6px}
.lesson-num{width:38px;height:38px;flex-shrink:0;border-radius:13px;background:var(--cc);color:#fff;
 display:flex;align-items:center;justify-content:center;font-weight:800}
.lesson-title h1{font-size:1.35rem;padding-top:4px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:20px;margin-top:14px}
.card-h{font-size:1.02rem;margin-bottom:12px}
.task-card{border-left:4px solid var(--cc)}

/* шаги */
.steps-card{padding-top:14px}
.steps-top{display:flex;align-items:center;justify-content:space-between;gap:10px;
 padding-bottom:12px;border-bottom:1px solid var(--line);margin-bottom:16px}
.steps-count{font-size:.8rem;color:var(--mut);font-weight:700}
.steps-count b{color:var(--cc);font-size:1rem}
.steps-dots{display:flex;gap:5px}
.dot{width:7px;height:7px;border-radius:99px;background:var(--line);transition:background .3s}
.dot.act{background:var(--cc)}
.step-h{font-size:1.15rem;margin-bottom:10px;color:var(--cc)}
.steps-nav{display:flex;gap:10px;margin-top:18px}
.steps-nav .btn{flex:1}
.steps-end{text-align:center;margin-top:18px;padding-top:16px;border-top:1px solid var(--line)}
.steps-end b{display:block;margin-bottom:12px}

/* текст теории */
.prose p{margin:9px 0}
.prose ul,.prose ol{padding-left:20px;margin:9px 0}
.prose li{margin:5px 0}
.prose b{color:var(--txt)}
.prose code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.87em;background:var(--bg2);
 padding:2px 7px;border-radius:7px;color:var(--acc);word-break:break-word}
.prose pre{background:#0b1020;border:1px solid var(--line);border-radius:13px;padding:14px;
 overflow-x:auto;margin:12px 0}
.prose pre code{background:none;color:#c5d5f5;padding:0;white-space:pre}
.code{background:#0b1020;border:1px solid var(--line);border-radius:13px;padding:15px;
 overflow-x:auto;margin-bottom:12px}
.code code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.83rem;color:#c5d5f5;white-space:pre}

/* ---- редактор ---- */
.ed{border:1px solid var(--line);border-radius:15px;overflow:hidden;background:#0b1020}
.ed.full{position:fixed;inset:0;z-index:200;border-radius:0}
.ed-bar{display:flex;justify-content:space-between;gap:8px;background:#111729;
 border-bottom:1px solid var(--line);padding:6px}
.ed-tabs{display:flex;gap:3px}
.ed-tab{background:none;border:0;color:#8b9ac0;padding:7px 13px;border-radius:9px;cursor:pointer;
 font:700 .82rem inherit}
.ed-tab.act{background:#26304d;color:#eef2fb}
.ed-acts{display:flex;gap:3px}
.ed-btn{background:#1b2542;border:1px solid #26304d;color:#c5d5f5;border-radius:9px;
 padding:7px 11px;cursor:pointer;font-size:.85rem;line-height:1}
.ed-switch{display:flex;gap:4px;background:#111729;border-bottom:1px solid var(--line);padding:6px}
.sw{flex:1;background:none;border:0;color:#8b9ac0;padding:9px;border-radius:9px;cursor:pointer;
 font:700 .85rem inherit}
.sw.act{background:#26304d;color:#eef2fb}
.ed-body{display:block;height:400px}
.ed.full .ed-body{height:calc(100vh - 108px)}
.ed-code,.ed-prev,.ed-con{height:100%}
.ed-code{display:flex}
.ed[data-view="preview"] .ed-code,.ed[data-view="console"] .ed-code{display:none}
.ed[data-view="code"] .ed-prev,.ed[data-view="console"] .ed-prev{display:none}
.ed[data-view="code"] .ed-con,.ed[data-view="preview"] .ed-con{display:none}
.gutter{flex-shrink:0;width:38px;padding:13px 6px 13px 0;text-align:right;overflow:hidden;
 background:#0b1020;color:#3f4d70;font-family:ui-monospace,Menlo,Consolas,monospace;
 font-size:13px;line-height:1.65;white-space:pre;user-select:none;border-right:1px solid #1b2542}
.ta{flex:1;width:100%;height:100%;border:0;outline:0;resize:none;background:#0b1020;color:#c5d5f5;
 font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;line-height:1.65;padding:13px 13px 13px 8px;display:block}

/* ---- терминал ---- */
.ed-con{background:#080c18;display:flex;flex-direction:column}
.con-bar{display:flex;align-items:center;justify-content:space-between;padding:7px 11px;
 background:#111729;border-bottom:1px solid var(--line);flex-shrink:0}
.con-bar b{font-family:ui-monospace,monospace;font-size:.8rem;color:#6ee7b7}
.con-out{flex:1;overflow-y:auto;padding:8px 0;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px}
.con-empty{color:#4a5878;padding:10px 13px;font-size:12px}
.con-row{display:flex;gap:9px;padding:4px 13px;border-bottom:1px solid rgba(255,255,255,.03);
 word-break:break-word}
.con-time{color:#3f4d70;flex-shrink:0}
.con-txt{white-space:pre-wrap}
.con-log .con-txt{color:#c5d5f5}
.con-info .con-txt{color:#7dd3fc}
.con-warn .con-txt{color:#fbbf24}
.con-error .con-txt{color:#fb7185}
.sw b{background:var(--err);color:#fff;border-radius:99px;padding:0 6px;font-size:.7rem;margin-left:3px}

/* ---- проверка AI ---- */
.ai-box{margin-top:14px}
.btn-ai{background:linear-gradient(135deg,#10b981,#0ea5e9);color:#fff;box-shadow:0 6px 20px rgba(16,185,129,.28)}
.btn-ai:disabled{opacity:.6}
.ai-note{font-size:.78rem;text-align:center;margin-top:7px}
.ai-res{margin-top:12px;border-radius:15px;padding:16px;border:1px solid var(--line);background:var(--bg2)}
.ai-res.good{border-color:var(--ok);background:rgba(34,197,94,.09)}
.ai-res.bad{border-color:var(--warn);background:rgba(245,158,11,.09)}
.ai-res.wait{text-align:center;color:var(--mut)}
.ai-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}
.ai-badge{font-weight:800;font-size:.95rem}
.ai-badge.ok{color:var(--ok)}
.ai-badge.no{color:var(--warn)}
.ai-score{font-weight:800;color:var(--mut)}
.ai-praise{font-size:.94rem;margin-bottom:10px}
.ai-sec{margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}
.ai-sec b{display:block;margin-bottom:7px;font-size:.88rem}
.ai-sec p{font-size:.9rem;color:var(--mut)}
.ai-errs{list-style:none;display:flex;flex-direction:column;gap:8px}
.ai-errs li{background:var(--card);border-radius:11px;padding:10px 12px;font-size:.89rem}
.ai-errs code{background:var(--bg2);color:var(--err);padding:1px 7px;border-radius:6px;
 font-size:.8rem;font-weight:700;margin-right:5px}
.ai-foot{margin-top:12px;font-size:.76rem;color:var(--mut);text-align:right}
.ai-spin{width:26px;height:26px;margin:0 auto 10px;border:3px solid var(--line);
 border-top-color:var(--acc);border-radius:99px;animation:sp .8s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
.ed-prev{background:#fff;display:flex;flex-direction:column}
.ed-prev-bar{display:flex;align-items:center;gap:5px;padding:7px 11px;background:#e8ecf5;flex-shrink:0}
.ed-prev-bar span{width:9px;height:9px;border-radius:99px;background:#c3ccdd}
.ed-prev-bar span:first-child{background:#ff5f57}
.ed-prev-bar span:nth-child(2){background:#febc2e}
.ed-prev-bar span:nth-child(3){background:#28c840}
.ed-prev-bar i{margin-left:8px;font-style:normal;font-size:.74rem;color:#7a879e}
.ed-prev iframe{flex:1;width:100%;border:0;background:#fff}
.ed-status{display:flex;justify-content:space-between;gap:10px;padding:7px 12px;background:#111729;
 border-top:1px solid var(--line);font-size:.78rem;flex-wrap:wrap;min-height:31px}
.ed-err{color:#fb7185;font-family:ui-monospace,monospace;word-break:break-word}

/* ---- тест ---- */
.tform{margin-top:12px}
.q{background:var(--bg2);border:1px solid var(--line);border-radius:15px;padding:15px;margin-bottom:10px}
.q-ok{border-color:var(--ok)}
.q-bad{border-color:var(--err)}
.q-t{font-weight:700;margin-bottom:11px;display:flex;gap:9px;align-items:flex-start;font-size:.96rem}
.q-n{background:var(--acc);color:#fff;width:23px;height:23px;border-radius:99px;flex-shrink:0;
 display:flex;align-items:center;justify-content:center;font-size:.78rem}
.q-opts{display:flex;flex-direction:column;gap:7px}
.opt{display:flex;gap:10px;align-items:flex-start;background:var(--card);border:2px solid var(--line);
 border-radius:12px;padding:11px 13px;cursor:pointer;font-size:.93rem}
.opt input{margin-top:4px;flex-shrink:0;accent-color:var(--acc)}
.opt:has(input:checked){border-color:var(--acc)}
.opt.good{border-color:var(--ok);background:rgba(34,197,94,.1)}
.opt.wrong{border-color:var(--err);background:rgba(244,63,94,.1)}
.q-ex{margin-top:10px;font-size:.86rem;color:var(--mut);background:var(--card);border-radius:10px;padding:10px 12px}
.tres{display:flex;gap:15px;align-items:center;border:1px solid var(--line);border-radius:15px;
 padding:15px;margin-bottom:12px;background:var(--bg2)}
.tres.ok{border-color:var(--ok)}
.tres.bad{border-color:var(--err)}
.tres-score{font-size:2rem;font-weight:800;color:var(--acc);line-height:1;flex-shrink:0}
.tres-score small{font-size:1rem;color:var(--mut);font-weight:700}
.tres-grade{font-weight:700;font-size:.92rem;margin:3px 0}
.done-box{background:rgba(34,197,94,.1);border:1px solid var(--ok);border-radius:16px;
 padding:20px;margin-bottom:12px;text-align:center}
.done-emoji{font-size:2.2rem}
.done-box .btn{margin-top:12px}

/* ---- профиль ---- */
.prof{text-align:center;padding:16px 0}
.prof-av{width:88px;height:88px;border-radius:28px;margin:0 auto 12px;font-size:2.2rem;font-weight:800;
 background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;
 display:flex;align-items:center;justify-content:center}
.prof h1{font-size:1.4rem}
.prof-stats{display:flex;gap:9px;justify-content:center;margin-top:18px}
.pstat{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:13px 18px;min-width:88px}
.pstat b{display:block;font-size:1.35rem;color:var(--acc)}
.pstat span{font-size:.74rem;color:var(--mut)}
.prof-prog{display:flex;flex-direction:column;gap:11px}
.prow{display:grid;grid-template-columns:120px 1fr 52px;gap:10px;align-items:center}
.prow-name{font-weight:700;font-size:.9rem}
.prow-n{font-size:.8rem;color:var(--mut);text-align:right}

/* ---- нижняя панель ---- */
.tabbar{position:fixed;left:0;right:0;bottom:0;z-index:70;display:flex;
 background:rgba(10,14,26,.94);backdrop-filter:blur(14px);border-top:1px solid var(--line);
 padding-bottom:env(safe-area-inset-bottom)}
html.light .tabbar{background:rgba(246,248,253,.94)}
.tabbar a{flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;padding:9px 0 7px;color:var(--mut)}
.tabbar a span{font-size:1.2rem;line-height:1}
.tabbar a i{font-style:normal;font-size:.68rem;font-weight:700}
.tabbar a.act{color:var(--acc)}
.foot{text-align:center;color:var(--mut);font-size:.8rem;padding:18px 14px 100px}

@media (min-width:760px){
  .ed-body{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr auto;height:480px}
  .ed-switch{display:none}
  /* дар экрани калон: код ва натиҷа паҳлӯи ҳам, терминал дар поён */
  .ed[data-view="preview"] .ed-code,.ed[data-view="console"] .ed-code{display:flex}
  .ed[data-view="code"] .ed-prev,.ed[data-view="console"] .ed-prev{display:flex}
  .ed[data-view="code"] .ed-con,.ed[data-view="preview"] .ed-con{display:flex}
  .ed-con{grid-column:1/-1;height:140px;border-top:1px solid var(--line)}
  .ed-code{border-right:1px solid var(--line)}
  .tabbar{position:static;background:none;border:0;max-width:900px;margin:0 auto;
    border-top:1px solid var(--line)}
  .wrap{padding-bottom:20px}
  .foot{padding-bottom:24px}
}
    <?php
}
