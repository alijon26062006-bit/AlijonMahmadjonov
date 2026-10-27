"""Короткое видео для Instagram на таджикском: защита сайта от DDoS.

Показывает, как запросы идут на сервер, что происходит при DDoS и какую защиту
поставить. Как проводить атаку — не показывается.

Голос: текст на таджикском читает русский голос Piper (таджикского голоса нет),
поэтому буквы ҳ, ҷ, қ, ғ, ӣ, ӯ заменяются на близкие русские, а термины
записываются так, как их произносят. Субтитры остаются на таджикском.

Запуск:   python3 reels/shorts/vaibcoder02_ddos_tj.py
Превью:   python3 reels/shorts/vaibcoder02_ddos_tj.py preview 5 20
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from engine import (Beat, Bullet, Card, Net, NetState, Pop, Term, Title, Type,  # noqa: E402
                    preview, render)

# как читать термины вслух
SPOKEN = [
    ("DDoS", "ди-дос"), ("CDN", "си-ди-эн"), ("Cloudflare", "клаудфлэр"),
    ("IP", "ай-пи"), ("nginx", "энджин-икс"),
]
LETTERS = str.maketrans({"ҳ": "х", "Ҳ": "Х", "ҷ": "дж", "Ҷ": "Дж", "қ": "к", "Қ": "К",
                         "ғ": "г", "Ғ": "Г", "ӣ": "и", "Ӣ": "И", "ӯ": "у", "Ӯ": "У"})


def voice(text):
    text = text.replace("`", "")
    for term, spoken in SPOKEN:
        text = re.sub(rf"\b{term}\b", spoken, text)
    return text.translate(LETTERS)


def B(text, do=()):
    """Бит: субтитры на таджикском, озвучка — тот же текст в «читаемом» виде."""
    return Beat(say=voice(text), sub=text, do=do)


LESSON = {
    "number": 102,
    "topic": "DDoS",
    "code_size": 38,
    "text_font": "inter",
    "header": "Ҳимояи сайт",
    "logo": "shield",
    "badge": "Хатои вайбкодер",
    "net_hidden_label": "пинҳон",
    "auto_walk": False,
    "voice_speed": 0.8,
    "beats": [
        B("Сайти шумо ногаҳон аз кор монд? Шояд ин ҳамлаи `DDoS` буд. "
          "Биёед бубинем, ки он чӣ тавр кор мекунад ва чӣ тавр худро ҳимоя кунем.",
          do=[Title("Сайт аз кор монд?", "DDoS", "Чӣ тавр ҳимоя кунем?")]),
        B("Дар ҳолати оддӣ корбарон ба сервер дархост мефиристанд ва сервер ба онҳо ҷавоб медиҳад. "
          "Сарборӣ кам аст ва сайт хуб кор мекунад.",
          do=[Net("normal")]),
        B("Ҳангоми ҳамлаи `DDoS` ҳазорон компютер якбора ба як сервер дархост мефиристанд.",
          do=[NetState("flood")]),
        B("Сервер ба ин сарборӣ тоб намеоварад ва сайт барои ҳамаи корбарон кор намекунад.",
          do=[Pop("Вой!", color="red")]),
        B("Қадами якум: ҳимоя аз `DDoS` дар `CDN`, масалан `Cloudflare`. Ҳамаи дархостҳо аввал аз филтр "
          "мегузаранд ва танҳо дархостҳои тоза ба сервер мерасанд.",
          do=[NetState("shield")]),
        B("Қадами дуюм: `IP`-и асосии серверро пинҳон кунед. Агар суроғаи сервер маълум набошад, "
          "филтрро давр зада намешавад.",
          do=[NetState("hide_ip")]),
        B("Қадами сеюм: маҳдудияти дархост. Аз як суроға дар як сония танҳо чанд дархост қабул мешавад. "
          "Масалан, дар `nginx` ин тавр навишта мешавад.",
          do=[Term(), Type("# 10 requests/sec per IP",
                           "limit_req_zone $binary_remote_addr",
                           "    zone=one:10m rate=10r/s;",
                           "limit_req zone=one burst=20;")]),
        B("Қадами чорум: расмҳо ва файлҳоро дар `CDN` кэш кунед, то сервер камтар бор гирад.",
          do=[Card("Боз чӣ кор кунем?"), Bullet("Расм ва файлҳоро дар `CDN` кэш кунед")]),
        B("Қадами панҷум: мониторинг гузоред, то афзоиши ногаҳонии трафикро фавран бинед.",
          do=[Bullet("Мониторинг ва огоҳинома гузоред")]),
        B("Қадами шашум: панели админро аз интернет пӯшед.",
          do=[Bullet("Панели админро аз интернет пӯшед")]),
        B("Ҳимояро аз рӯзи аввал гузоред, на баъд аз ҳамла. "
          "Обуна шавед, боз хатоҳои вайбкодеронро таҳлил мекунем!",
          do=[Pop("Офарин!"), Title("Обуна шавед", "Ҳимоя", "аз рӯзи аввал")]),
    ],
}

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "..", "out")
    os.makedirs(out_dir, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        preview(LESSON, [float(x) for x in sys.argv[2:]], out_dir)
    else:
        render(LESSON, os.path.join(out_dir, "vaibcoder02_ddos_tj"))
