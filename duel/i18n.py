"""Тексты на русском и таджикском. Один источник и для бота, и для Mini App."""

from __future__ import annotations

DEFAULT_LANG = "ru"
LANGS = ("ru", "tg")
LANG_NAMES = {"ru": "Русский", "tg": "Тоҷикӣ"}

# Ключи с точкой: ui.* видит Mini App, bot.* — сообщения бота.
STRINGS: dict[str, dict[str, str]] = {
    "ru": {
        "ui.title": "Перетягивание каната: математика",
        "ui.play": "Найти соперника",
        "ui.friend": "Позвать друга",
        "ui.join": "Войти по коду",
        "ui.top": "Таблица лидеров",
        "ui.profile": "Профиль",
        "ui.duration": "Сколько играем",
        "ui.level": "Сложность",
        "ui.level.easy": "Лёгкий",
        "ui.level.normal": "Средний",
        "ui.level.hard": "Трудный",
        "ui.level.auto": "По рейтингу",
        "ui.level.easy.hint": "Счёт до 100",
        "ui.level.normal.hint": "Таблица умножения",
        "ui.level.hard.hint": "Двузначные и деление",
        "ui.level.auto.hint": "Подстроится под тебя",
        "ui.sec": "сек",
        "ui.min": "мин",
        "ui.endless": "До победы",
        "ui.searching": "Ищем соперника",
        "ui.searching.hint": "Обычно занимает несколько секунд",
        "ui.waiting_players": "в очереди сейчас",
        "ui.cancel": "Отмена",
        "ui.found": "Соперник найден",
        "ui.vs": "против",
        "ui.go": "Марш!",
        "ui.you": "Ты",
        "ui.opponent": "Соперник",
        "ui.streak": "серия",
        "ui.correct": "Верно",
        "ui.wrong": "Мимо",
        "ui.double": "Двойной рывок!",
        "ui.win": "Победа!",
        "ui.loss": "Поражение",
        "ui.draw": "Ничья",
        "ui.win.rope": "Ты перетянул канат",
        "ui.win.time": "Время вышло — канат на твоей стороне",
        "ui.win.left": "Соперник не вернулся",
        "ui.loss.rope": "Соперник перетянул канат",
        "ui.loss.time": "Время вышло — канат ушёл к сопернику",
        "ui.loss.left": "Ты вышел из матча",
        "ui.loss.cheat": "Матч остановлен: ответы быстрее человеческих",
        "ui.draw.time": "Ровно посередине",
        "ui.result.score": "Верных ответов",
        "ui.result.accuracy": "Точность",
        "ui.result.streak": "Лучшая серия",
        "ui.result.speed": "Среднее время ответа",
        "ui.result.fastest": "Самый быстрый ответ",
        "ui.result.rating": "Рейтинг",
        "ui.again": "Ещё раз",
        "ui.home": "В меню",
        "ui.rank": "Место",
        "ui.rating": "Рейтинг",
        "ui.games": "Матчей",
        "ui.wins": "Побед",
        "ui.losses": "Поражений",
        "ui.draws": "Ничьих",
        "ui.best_streak": "Лучшая серия",
        "ui.total_correct": "Всего решено",
        "ui.no_games": "Ещё ни одного матча",
        "ui.top.empty": "Пока никто не сыграл. Будь первым.",
        "ui.room.title": "Комната для друга",
        "ui.room.hint": "Отправь другу ссылку или продиктуй код",
        "ui.room.share": "Отправить другу",
        "ui.room.code": "Код комнаты",
        "ui.room.waiting": "Ждём друга",
        "ui.room.enter": "Введи код комнаты",
        "ui.room.bad": "Такой комнаты нет или она уже закрыта",
        "ui.offline": "Связь пропала. Пробуем вернуться…",
        "ui.reconnected": "Связь вернулась",
        "ui.opp_offline": "У соперника пропала связь",
        "ui.error": "Что-то пошло не так",
        "ui.auth_error": "Открой игру из Telegram — так проверяется, кто ты",
        "ui.frozen": "Пауза после ошибки",
        "ui.lang": "Язык",
        "ui.sound": "Звук",
        "ui.back": "Назад",
        "bot.start": (
            "⚔️ Математическая дуэль\n\n"
            "Двое решают примеры наперегонки и тянут канат на себя. "
            "Кто быстрее считает — тот и перетянул.\n\n"
            "Жми кнопку и ищи соперника."
        ),
        "bot.play": "⚔️ Играть",
        "bot.menu.play": "Играть",
        "bot.top": "🏆 Таблица лидеров",
        "bot.me": "👤 Мой профиль",
        "bot.lang": "🌐 Язык",
        "bot.lang.choose": "Выбери язык",
        "bot.lang.done": "Готово, теперь по-русски",
        "bot.rules": "📖 Правила",
        "bot.rules.text": (
            "📖 Как играть\n\n"
            "• Обоим одновременно идут примеры: сложение, вычитание, умножение, деление.\n"
            "• Верный ответ тянет канат на твою сторону, сразу приходит новый пример.\n"
            "• Три верных подряд — рывок вдвое сильнее.\n"
            "• Ошибка — полторы секунды паузы, канат стоит.\n"
            "• Дотянул канат до края — досрочная победа.\n"
            "• Кончилось время — победил тот, на чьей стороне канат.\n\n"
            "Ответы проверяет сервер, поэтому подсмотреть их в браузере нельзя."
        ),
        "bot.result.win": "🏆 Победа над {opponent}!",
        "bot.result.loss": "Поражение от {opponent}",
        "bot.result.draw": "Ничья с {opponent}",
        "bot.result.body": (
            "Верных ответов: {score} : {opp_score}\n"
            "Рейтинг: {rating} ({delta})"
        ),
        "bot.profile": (
            "👤 {name}\n\n"
            "Рейтинг: {rating} — {title}\n"
            "Место: {place}\n"
            "Матчей: {games} · побед {wins} · поражений {losses} · ничьих {draws}\n"
            "Решено верно: {correct} · лучшая серия: {streak}"
        ),
        "bot.profile.empty": "👤 {name}\n\nМатчей ещё не было. Жми «Играть».",
        "bot.top.header": "🏆 Лучшие игроки\n",
        "bot.top.empty": "Пока никто не сыграл ни одного матча. Будь первым.",
        "bot.invite": "{name} зовёт тебя на дуэль. Открой игру и нажми «Войти по коду»: {code}",
        "bot.only_private": "Игра открывается в личной переписке с ботом.",
    },
    "tg": {
        "ui.title": "Кашиши арғамчин: математика",
        "ui.play": "Рақиб ёфтан",
        "ui.friend": "Дӯстро даъват кардан",
        "ui.join": "Бо рамз даромадан",
        "ui.top": "Ҷадвали пешсафон",
        "ui.profile": "Профил",
        "ui.duration": "Чанд вақт бозӣ мекунем",
        "ui.level": "Душворӣ",
        "ui.level.easy": "Осон",
        "ui.level.normal": "Миёна",
        "ui.level.hard": "Душвор",
        "ui.level.auto": "Аз рӯи рейтинг",
        "ui.level.easy.hint": "Ҳисоб то 100",
        "ui.level.normal.hint": "Ҷадвали зарб",
        "ui.level.hard.hint": "Дурақама ва тақсим",
        "ui.level.auto.hint": "Худаш мувофиқ мекунад",
        "ui.sec": "сония",
        "ui.min": "дақ",
        "ui.endless": "То ғалаба",
        "ui.searching": "Рақиб меҷӯем",
        "ui.searching.hint": "Одатан чанд сония тӯл мекашад",
        "ui.waiting_players": "ҳозир дар навбат",
        "ui.cancel": "Бекор кардан",
        "ui.found": "Рақиб ёфт шуд",
        "ui.vs": "бар зидди",
        "ui.go": "Сар кун!",
        "ui.you": "Ту",
        "ui.opponent": "Рақиб",
        "ui.streak": "пайдарпай",
        "ui.correct": "Дуруст",
        "ui.wrong": "Хато",
        "ui.double": "Кашиши дукарата!",
        "ui.win": "Ғалаба!",
        "ui.loss": "Мағлубият",
        "ui.draw": "Баробар",
        "ui.win.rope": "Ту арғамчинро кашидӣ",
        "ui.win.time": "Вақт тамом — арғамчин дар тарафи ту",
        "ui.win.left": "Рақиб барнагашт",
        "ui.loss.rope": "Рақиб арғамчинро кашид",
        "ui.loss.time": "Вақт тамом — арғамчин ба тарафи рақиб рафт",
        "ui.loss.left": "Ту аз бозӣ баромадӣ",
        "ui.loss.cheat": "Бозӣ қатъ шуд: ҷавобҳо аз имкони инсон тезтаранд",
        "ui.draw.time": "Дақиқ дар мобайн",
        "ui.result.score": "Ҷавобҳои дуруст",
        "ui.result.accuracy": "Дақиқӣ",
        "ui.result.streak": "Беҳтарин пайдарпай",
        "ui.result.speed": "Вақти миёнаи ҷавоб",
        "ui.result.fastest": "Тезтарин ҷавоб",
        "ui.result.rating": "Рейтинг",
        "ui.again": "Боз як бор",
        "ui.home": "Ба меню",
        "ui.rank": "Ҷой",
        "ui.rating": "Рейтинг",
        "ui.games": "Бозиҳо",
        "ui.wins": "Ғалабаҳо",
        "ui.losses": "Мағлубиятҳо",
        "ui.draws": "Баробар",
        "ui.best_streak": "Беҳтарин пайдарпай",
        "ui.total_correct": "Ҳамагӣ ҳал шуд",
        "ui.no_games": "Ҳанӯз ягон бозӣ нест",
        "ui.top.empty": "Ҳанӯз касе бозӣ накардааст. Аввалин шав.",
        "ui.room.title": "Ҳуҷра барои дӯст",
        "ui.room.hint": "Ба дӯстат истинод фирист ё рамзро гӯй",
        "ui.room.share": "Ба дӯст фиристодан",
        "ui.room.code": "Рамзи ҳуҷра",
        "ui.room.waiting": "Дӯстро интизорем",
        "ui.room.enter": "Рамзи ҳуҷраро ворид кун",
        "ui.room.bad": "Чунин ҳуҷра нест ё аллакай пӯшида шуд",
        "ui.offline": "Пайваст канда шуд. Кӯшиш карда истодаем…",
        "ui.reconnected": "Пайваст баргашт",
        "ui.opp_offline": "Пайвасти рақиб канда шуд",
        "ui.error": "Чизе нодуруст шуд",
        "ui.auth_error": "Бозиро аз Telegram кушо — ҳамин тавр шинохта мешавӣ",
        "ui.frozen": "Таваққуф баъди хато",
        "ui.lang": "Забон",
        "ui.sound": "Овоз",
        "ui.back": "Бозгашт",
        "bot.start": (
            "⚔️ Дуэли математикӣ\n\n"
            "Ду нафар мисолҳоро мусобиқавор ҳал мекунанд ва арғамчинро ба тарафи худ "
            "мекашанд. Кӣ тезтар ҳисоб кунад, ҳамон мекашад.\n\n"
            "Тугмаро пахш кун ва рақиб ёб."
        ),
        "bot.play": "⚔️ Бозӣ",
        "bot.menu.play": "Бозӣ",
        "bot.top": "🏆 Ҷадвали пешсафон",
        "bot.me": "👤 Профили ман",
        "bot.lang": "🌐 Забон",
        "bot.lang.choose": "Забонро интихоб кун",
        "bot.lang.done": "Тайёр, акнун бо тоҷикӣ",
        "bot.rules": "📖 Қоидаҳо",
        "bot.rules.text": (
            "📖 Чӣ тавр бозӣ кардан\n\n"
            "• Ба ҳар ду якбора мисолҳо меоянд: ҷамъ, тарҳ, зарб, тақсим.\n"
            "• Ҷавоби дуруст арғамчинро ба тарафи ту мекашад ва мисоли нав меояд.\n"
            "• Се ҷавоби дурусти пайдарпай — кашиш ду баробар мешавад.\n"
            "• Хато — якуним сония таваққуф, арғамчин намеҷунбад.\n"
            "• Арғамчинро то канор кашидӣ — ғалабаи пеш аз мӯҳлат.\n"
            "• Вақт тамом шуд — ғолиб он аст, ки арғамчин дар тарафи ӯст.\n\n"
            "Ҷавобҳоро сервер месанҷад, бинобар ин онҳоро дар браузер дидан мумкин нест."
        ),
        "bot.result.win": "🏆 Ғалаба бар {opponent}!",
        "bot.result.loss": "Мағлубият аз {opponent}",
        "bot.result.draw": "Баробар бо {opponent}",
        "bot.result.body": (
            "Ҷавобҳои дуруст: {score} : {opp_score}\n"
            "Рейтинг: {rating} ({delta})"
        ),
        "bot.profile": (
            "👤 {name}\n\n"
            "Рейтинг: {rating} — {title}\n"
            "Ҷой: {place}\n"
            "Бозиҳо: {games} · ғалаба {wins} · мағлубият {losses} · баробар {draws}\n"
            "Дуруст ҳал шуд: {correct} · беҳтарин пайдарпай: {streak}"
        ),
        "bot.profile.empty": "👤 {name}\n\nҲанӯз бозӣ набуд. «Бозӣ»-ро пахш кун.",
        "bot.top.header": "🏆 Беҳтарин бозигарон\n",
        "bot.top.empty": "Ҳанӯз касе бозӣ накардааст. Аввалин шав.",
        "bot.invite": "{name} туро ба дуэл даъват мекунад. Бозиро кушо ва «Бо рамз даромадан»-ро пахш кун: {code}",
        "bot.only_private": "Бозӣ дар чати шахсӣ бо бот кушода мешавад.",
    },
}

# Звания на таджикском — на русском они лежат в rating.title().
TITLES_TG = {
    "новичок": "навомӯз",
    "ученик": "шогирд",
    "счетовод": "ҳисобчӣ",
    "мастер": "устод",
    "снайпер": "тирандоз",
    "гроссмейстер": "гроссмейстер",
    "легенда": "афсона",
}


def normalize(lang: str | None) -> str:
    """Приводит код языка Telegram к нашему. Таджикский — только явный tg."""

    if not lang:
        return DEFAULT_LANG
    code = lang.strip().lower().replace("_", "-").split("-")[0]
    return code if code in LANGS else DEFAULT_LANG


def t(key: str, lang: str = DEFAULT_LANG, **kwargs: object) -> str:
    """Строка по ключу. Нет перевода — отдаём русский, а не пустоту."""

    table = STRINGS.get(normalize(lang), STRINGS[DEFAULT_LANG])
    text = table.get(key) or STRINGS[DEFAULT_LANG].get(key, key)
    return text.format(**kwargs) if kwargs else text


def ui_strings(lang: str = DEFAULT_LANG) -> dict[str, str]:
    """Все строки для Mini App одним словарём — их сервер вшивает в страницу."""

    table = STRINGS[normalize(lang)]
    fallback = STRINGS[DEFAULT_LANG]
    return {
        key[len("ui.") :]: table.get(key, fallback[key])
        for key in fallback
        if key.startswith("ui.")
    }


def title(name: str, lang: str = DEFAULT_LANG) -> str:
    """Звание на нужном языке."""

    return TITLES_TG.get(name, name) if normalize(lang) == "tg" else name
