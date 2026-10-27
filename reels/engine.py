"""Движок видео-уроков «Python с нуля» (вертикальное видео 1080x1920).

Урок описывается списком «битов»: что говорит диктор (say), какие субтитры
показать (sub) и что происходит на экране (do). Движок сам озвучивает текст
голосом RHVoice, подгоняет тайминг под длину фраз, печатает код со звуком
клавиш, добавляет звуковые эффекты, фоновую музыку и анимирует человечка.

Нужно: ffmpeg, numpy, Pillow и голос Piper (reels/setup_voice.sh).
"""

import bisect
import hashlib
import math
import multiprocessing as mp
import os
import random
import re
import subprocess
import tempfile
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
FONT_DIR = "/usr/share/fonts/truetype/jetbrains-mono"

W, H = 1080, 1920
S = 2  # суперсэмплинг для сглаживания
FPS = 30
SR = 44100

# Голос: "piper" — нейросетевой (живой), "rhvoice" — запасной.
# Piper ставится скриптом reels/setup_voice.sh.
VOICE_ENGINE = "piper"
TOOLS = os.path.join(HERE, ".tools")
PIPER_BIN = os.path.join(TOOLS, "piper", "piper")
PIPER_MODEL = os.path.join(TOOLS, "ru-irinia-medium.onnx")
PIPER_SPEED = 0.92  # length_scale: меньше — быстрее речь
VOICE = "aleksandr-hq"
VOICE_RATE = 112

# ---------- цвета ----------
BG = (32, 32, 32)
PANEL = (19, 19, 19)
PANEL_BORDER = (52, 52, 52)
YELLOW = (247, 224, 122)
FIG = (246, 218, 74)
DOTS = [(237, 95, 87), (245, 192, 66), (86, 168, 84)]
WHITE = (235, 235, 235)
GREY = (130, 130, 130)
RED = (241, 106, 106)
C_DEFAULT = (212, 212, 212)
C_COMMENT = (106, 153, 85)
C_KEYWORD = (197, 134, 192)
C_BUILTIN = (220, 220, 170)
C_STRING = (206, 145, 120)
C_NUMBER = (181, 206, 168)
C_NAME = (156, 220, 254)

# ---------- геометрия ----------
PANEL_BOX = (20, 380, W - 20, 1110)
PX0, PY0, PX1, PY1 = PANEL_BOX
CODE_X = PX0 + 44
CODE_Y = PY0 + 100
LINE_H = 60
SUB_Y = 1150
POP_POS = (W - 220, PY1 - 8)  # где выпрыгивают слова и клавиша ENTER

# ---------- тайминг ----------
CPS = 13          # скорость печати кода, символов/с
RUN_CPS = 30      # скорость «ввода» команды запуска
TRANSITION = 0.4  # смена сцены
BEAT_GAP = 0.5    # пауза между фразами
INTRO = 0.7
OUTRO = 1.5

# места человечка: x бедра и направление (1 — смотрит влево, -1 — вправо)
SPOTS = {"right": (832, 1), "center": (620, 1), "left": (250, -1)}
WALK_SPEED = 430  # px/с
STAND_T = 0.35    # встать / сесть
POP_WORDS_OK = ["Ура!", "Работает!", "Супер!", "Готово!", "Отлично!", "Есть!"]
POP_WORDS_ERR = ["Ой!", "Упс!", "Ошибка!"]


# ======================================================================
#  Действия на экране (используются в файлах уроков)
# ======================================================================
def Title(top, big, bottom):
    """Заставка: маленькая строка, крупный заголовок, подзаголовок."""
    return {"type": "title", "top": top, "big": big, "bottom": bottom}


def Card(title):
    """Карточка с заголовком; пункты добавляются через Bullet."""
    return {"type": "card", "title": title}


def Bullet(text):
    return {"type": "bullet", "text": text}


def Syntax(code, parts):
    """Разбор строки кода. parts: [(начало, конец, подпись, 'up'|'down'), ...]."""
    return {"type": "syntax", "code": code, "parts": parts}


def Hl(i):
    """Подсветить часть i в разборе Syntax."""
    return {"type": "hl", "i": i}


def Term():
    """Пустой терминал."""
    return {"type": "term"}


def Type(*lines):
    """Напечатать строки кода в терминале."""
    return {"type": "type", "lines": list(lines)}


def Run(*outputs, error=False):
    """Запустить программу и показать вывод (error=True — красный вывод ошибки)."""
    return {"type": "run", "outputs": list(outputs), "error": error}


def Boxes():
    """Сцена с «коробками»-переменными."""
    return {"type": "boxes"}


def Box(name, value):
    """Положить значение в коробку name (если коробка есть — заменить значение)."""
    return {"type": "box", "name": name, "value": value}


def Walk(spot):
    """Человечек встаёт и переходит на место spot: "left", "right" или "center"."""
    return {"type": "walk", "spot": spot}


def Pop(text, color="yellow"):
    """Слово выпрыгивает над терминалом (color: yellow, red, white)."""
    return {"type": "pop", "text": text, "color": color}


def Net(state="normal"):
    """Сцена «интернет → сервер»: запросы летят на сервер, видна нагрузка и статус."""
    return {"type": "net", "state": state}


def NetState(state):
    """Меняет сцену «сеть»: "normal", "flood" (DDoS), "shield" (защита CDN), "hide_ip"."""
    return {"type": "netstate", "state": state}


def Beat(say=None, sub=None, do=()):
    return {"say": say, "sub": sub if sub is not None else say, "do": list(do)}


MODE_TYPES = {"title", "card", "syntax", "term", "boxes", "net"}
RUN_CMD = "$ python main.py"


# ======================================================================
#  Утилиты
# ======================================================================
def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp_col(a, b, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), int(size * S))


F_TITLE = font("JetBrainsMono-ExtraBold.ttf", 108)
F_BADGE = font("JetBrainsMono-SemiBold.ttf", 34)
F_CODE = font("JetBrainsMono-Regular.ttf", 40)
F_CODE_B = font("JetBrainsMono-Bold.ttf", 40)
F_SUB = font("JetBrainsMono-Medium.ttf", 44)
F_CARD_T = font("JetBrainsMono-ExtraBold.ttf", 54)
F_CARD = font("JetBrainsMono-Medium.ttf", 46)
F_BIG = font("JetBrainsMono-ExtraBold.ttf", 128)
F_MID = font("JetBrainsMono-Bold.ttf", 58)
F_SMALL = font("JetBrainsMono-Medium.ttf", 40)
F_SYN = font("JetBrainsMono-Bold.ttf", 76)
F_LABEL = font("JetBrainsMono-SemiBold.ttf", 36)
CHAR_W = F_CODE.getlength("a") / S


def p(*xy):
    return tuple(int(round(v * S)) for v in xy)


def text_w(f, s):
    return f.getlength(s) / S


def thick_line(d, pts, width, color):
    w = int(width * S)
    sp = [p(*pt) for pt in pts]
    d.line(sp, fill=color, width=w, joint="curve")
    r = w / 2
    for x, y in sp:
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def tokenize(line):
    """Цвет подсветки синтаксиса для каждого символа строки."""
    colors = [C_DEFAULT] * len(line)
    rules = [
        (r"#.*", C_COMMENT),
        (r'"[^"]*"?', C_STRING),
        (r"\b(for|in|if|elif|else|while|def|return|import|from|and|or|not|True|False|None)\b", C_KEYWORD),
        (r"\b(print|range|len|input|int|str|float|type)\b", C_BUILTIN),
        (r"\b\d+(\.\d+)?\b", C_NUMBER),
        (r"\b[^\W\d]\w*\b", C_NAME),
    ]
    taken = [False] * len(line)
    for pattern, color in rules:
        for m in re.finditer(pattern, line):
            if any(taken[m.start():m.end()]):
                continue
            for i in range(m.start(), m.end()):
                colors[i] = color
                taken[i] = True
    return colors


def wrap(text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        cand = (cur + " " + wd).strip()
        if text_w(f, cand) <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


# ======================================================================
#  Озвучка
# ======================================================================
def tts(text):
    """Синтез речи (Piper или RHVoice) -> numpy float32 @ 44.1 кГц (с кэшем)."""
    os.makedirs(CACHE, exist_ok=True)
    if VOICE_ENGINE == "piper":
        key = hashlib.md5(f"piper|{PIPER_MODEL}|{PIPER_SPEED}|{text}".encode()).hexdigest()
    else:
        key = hashlib.md5(f"{VOICE}|{VOICE_RATE}|{text}".encode()).hexdigest()
    path = os.path.join(CACHE, key + ".wav")
    if not os.path.exists(path):
        if VOICE_ENGINE == "piper":
            subprocess.run([PIPER_BIN, "-m", PIPER_MODEL, "--length_scale", str(PIPER_SPEED),
                            "--sentence_silence", "0.25", "-f", path, "-q"],
                           input=text.encode(), check=True, stdout=subprocess.DEVNULL)
        else:
            subprocess.run(["RHVoice-test", "-p", VOICE, "-r", str(VOICE_RATE), "-o", path],
                           input=text.encode(), check=True)
    with wave.open(path) as wf:
        sr = wf.getframerate()
        data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        if wf.getnchannels() == 2:
            data = data[::2]
    # обрезаем тишину по краям
    nz = np.nonzero(np.abs(data) > 0.01)[0]
    if len(nz):
        data = data[max(0, nz[0] - 200): nz[-1] + 2000]
    n_out = int(len(data) * SR / sr)
    data = np.interp(np.linspace(0, len(data) - 1, n_out), np.arange(len(data)), data).astype(np.float32)
    peak = np.max(np.abs(data)) or 1
    return data / peak * 0.9


# ======================================================================
#  Построение таймлайна
# ======================================================================
class Timeline:
    def __init__(self, lesson):
        self.lesson = lesson
        self.actions = []
        self.voices = []      # (t0, samples)
        self.subs = []        # (t0, t1, [строки])
        self.sfx = []         # (t, kind)
        self.typing = []      # (t0, t1)
        self.pops = []        # выпрыгивающие слова и клавиша ENTER
        self.walks = []       # переходы человечка
        rnd = random.Random(lesson["number"])
        self.rnd = rnd
        t = INTRO
        for beat in lesson["beats"]:
            cur = t
            switch = any(a["type"] in MODE_TYPES for a in beat["do"])
            beat_actions = []
            for a in beat["do"]:
                a = dict(a, t0=cur)
                cur += self._prepare(a, rnd)
                a["t1"] = cur
                beat_actions.append(a)
            vend = cur
            if beat["say"]:
                vstart = t + (TRANSITION + 0.05 if switch else 0.15)
                v = tts(beat["say"])
                self.voices.append((vstart, v))
                vend = vstart + len(v) / SR
                self._add_subs(beat["sub"], vstart, vend)
            end = max(cur, vend) + BEAT_GAP
            for a in beat_actions:
                a["beat_end"] = end
            self.actions.extend(beat_actions)
            t = end
        self.duration = t + OUTRO
        self.frames = int(self.duration * FPS)
        self._plan_walks(lesson.get("auto_walk", True))
        self._voice_env()

    def _prepare(self, a, rnd):
        """Считает длительность действия, расписание символов и звуки."""
        typ, t0 = a["type"], a["t0"]
        if typ in MODE_TYPES:
            self.sfx.append((t0, "whoosh"))
            if typ == "title":
                self.sfx.append((t0 + 0.25, "sparkle"))
            return TRANSITION
        if typ == "bullet":
            self.sfx.append((t0, "pop_soft"))
            return 0.5
        if typ == "hl":
            self.sfx.append((t0, "tick"))
            return 0.3
        if typ == "box":
            self.sfx.append((t0 + 0.35, "pop"))
            return 0.7
        if typ == "netstate":
            snd = {"flood": "alarm", "shield": "chime", "hide_ip": "tick", "normal": "pop_soft"}[a["state"]]
            self.sfx.append((t0, snd))
            if a["state"] == "shield":
                self.sfx.append((t0, "whoosh"))
            return 0.6
        if typ == "walk":
            return 0  # идёт параллельно с остальным, см. _plan_walks
        if typ == "pop":
            self._add_pop(a["text"], {"yellow": YELLOW, "red": RED, "white": WHITE}[a["color"]], t0)
            return 0
        if typ == "type":
            t = t0
            lines = []
            for line in a["lines"]:
                times = []
                for ch in line:
                    t += (1 / CPS) * rnd.uniform(0.55, 1.45)
                    times.append(t)
                    self.sfx.append((t, "space" if ch == " " else "key"))
                t += 0.12
                self.sfx.append((t, "enter"))
                t += 0.2
                lines.append((line, times))
            a["typed"] = lines
            self.typing.append((t0, t))
            return t - t0 + 0.15
        if typ == "run":
            times = [t0 + (i + 1) / RUN_CPS for i in range(len(RUN_CMD))]
            for tt, ch in zip(times, RUN_CMD):
                self.sfx.append((tt, "space" if ch == " " else "key"))
            cmd_end = times[-1] + 0.1
            self.sfx.append((cmd_end, "enter"))
            self.typing.append((t0, cmd_end))
            outs = [cmd_end + 0.45 + i * 0.4 for i in range(len(a["outputs"]))]
            for ot in outs:
                self.sfx.append((ot, "error" if a["error"] else "pop"))
            if outs and not a["error"]:
                self.sfx.append((outs[-1] + 0.15, "chime"))
            # клавиша ENTER нажимается, затем выпрыгивает слово
            self.pops.append({"kind": "key", "t0": cmd_end - 0.25, "t1": cmd_end + 0.4, "press": cmd_end})
            words = POP_WORDS_ERR if a["error"] else POP_WORDS_OK
            self._add_pop(rnd.choice(words), RED if a["error"] else YELLOW,
                          (outs[0] if outs else cmd_end + 0.45), shake=a["error"], sound=not a["error"])
            a["cmd_times"] = times
            a["out_times"] = outs
            return (outs[-1] if outs else cmd_end) - t0 + 0.3
        raise ValueError(f"неизвестное действие {typ}")

    def _add_pop(self, text, color, t0, shake=False, sound=True):
        self.pops.append({"kind": "word", "text": text, "color": color, "t0": t0, "t1": t0 + 1.6,
                          "rot": self.rnd.uniform(-8, 8), "shake": shake})
        if sound:
            self.sfx.append((t0, "boing"))

    def _plan_walks(self, auto):
        """Когда человечек встаёт и переходит. Авто: на каждой второй смене карточки/разбора."""
        cur, n, busy = "right", 0, 0.0
        nxt = {"right": "left", "left": "right", "center": "left"}
        for a in self.actions:
            target, manual = None, False
            if a["type"] == "walk":
                target, manual = a["spot"], True
            elif auto and a["type"] in ("card", "syntax", "boxes"):
                n += 1
                if n % 2 == 0:
                    target = nxt[cur]
            if not target or target == cur or a["t0"] < busy:
                continue
            x0, x1 = SPOTS[cur][0], SPOTS[target][0]
            t0 = a["t0"] + 0.1
            t_up = t0 + STAND_T
            t_move = t_up + abs(x1 - x0) / WALK_SPEED
            t_end = t_move + STAND_T
            # автоматически не ходим, пока человечек печатает
            if not manual and any(b["type"] in ("type", "run") and b["t0"] < t_end and t0 < b["t1"]
                                  for b in self.actions):
                continue
            self.walks.append({"t0": t0, "t_up": t_up, "t_move": t_move, "t_end": t_end,
                               "from": cur, "to": target})
            step = 38 * math.pi  # шаг — пол-оборота фазы ходьбы
            dist = step / 2
            while dist < abs(x1 - x0):
                self.sfx.append((t_up + dist / WALK_SPEED, "step"))
                dist += step
            cur, busy = target, t_end

    def _add_subs(self, text, t0, t1):
        """Делит субтитры на куски по 2 строки и распределяет по времени фразы."""
        words = text.split()
        chunks, cur_lines, cur = [], [], ""
        max_w = W - 120
        for wd in words:
            cand = (cur + " " + wd).strip()
            if text_w(F_SUB, cand.replace("`", "")) <= max_w and len(cand) <= 30 or not cur:
                cur = cand
            else:
                cur_lines.append(cur)
                cur = wd
                if len(cur_lines) == 2:
                    chunks.append(cur_lines)
                    cur_lines = []
        if cur:
            cur_lines.append(cur)
        if cur_lines:
            chunks.append(cur_lines)
        total = sum(len(" ".join(c)) for c in chunks) or 1
        t = t0
        for c in chunks:
            dt = (t1 - t0) * len(" ".join(c)) / total
            self.subs.append((t, t + dt, c))
            t += dt

    def _voice_env(self):
        """Громкость голоса по кадрам — для движения рта человечка."""
        track = np.zeros(int((self.duration + 1) * SR), dtype=np.float32)
        for t0, v in self.voices:
            i = int(t0 * SR)
            track[i:i + len(v)] += v[: len(track) - i]
        self.voice_track = track
        hop = SR // FPS
        env = np.array([np.sqrt(np.mean(track[f * hop:(f + 1) * hop] ** 2)) for f in range(self.frames + 1)])
        ref = np.percentile(env[env > 0.01], 90) if np.any(env > 0.01) else 1
        self.mouth = np.clip(env / ref, 0, 1)

    # ------------------------------------------------------------------
    def state(self, t):
        st = {"mode": None, "mode_t": 0, "bullets": [], "hls": [], "lines": [],
              "typing": any(a <= t < b for a, b in self.typing), "happy": 0.0, "confused": 0.0}
        for a in self.actions:
            if a["t0"] > t:
                break
            typ = a["type"]
            if typ in MODE_TYPES:
                st["mode"], st["mode_t"] = typ, a["t0"]
            if typ == "title":
                st["title"] = a
            elif typ == "card":
                st["card"], st["bullets"] = a, []
            elif typ == "bullet":
                st["bullets"].append((a["text"], a["t0"]))
            elif typ == "syntax":
                st["syntax"], st["hls"] = a, []
            elif typ == "boxes":
                st["boxes"] = []
            elif typ == "box":
                for b in st["boxes"]:
                    if b["name"] == a["name"]:
                        b.update(old=b["value"], value=a["value"], t0=a["t0"])
                        break
                else:
                    st["boxes"].append({"name": a["name"], "value": a["value"], "old": None, "t0": a["t0"]})
            elif typ == "net":
                st["net"] = [(a["state"], a["t0"])]
                st["ip_hidden"] = None
            elif typ == "netstate":
                if a["state"] == "hide_ip":
                    st["ip_hidden"] = a["t0"]
                else:
                    st["net"].append((a["state"], a["t0"]))
            elif typ == "hl":
                st["hls"].append((a["i"], a["t0"]))
            elif typ == "term":
                st["lines"] = []
            elif typ == "type":
                for line, times in a["typed"]:
                    st["lines"].append({"text": line, "kind": "code", "times": times})
            elif typ == "run":
                st["lines"].append({"text": "", "kind": "blank", "times": []})
                st["lines"].append({"text": RUN_CMD, "kind": "cmd", "times": a["cmd_times"]})
                kind = "err" if a["error"] else "out"
                for out, ot in zip(a["outputs"], a["out_times"]):
                    st["lines"].append({"text": out, "kind": kind, "times": [ot] * len(out)})
                last = a["out_times"][-1] if a["out_times"] else a["t1"]
                if last <= t < a["beat_end"]:
                    k = ease((t - last) / 0.4) * ease((a["beat_end"] - t) / 0.3)
                    st["confused" if a["error"] else "happy"] = k
        return st


# ======================================================================
#  Отрисовка
# ======================================================================
TL = None          # Timeline (глобально — для дочерних процессов)
STATIC = None      # заранее нарисованный фон


def draw_logo(d, x, y, s):
    r = int(s * 0.22 * S)
    d.rounded_rectangle(p(x + s * 0.32, y + s * 0.32, x + s, y + s), radius=r, fill=(247, 205, 70))
    d.rounded_rectangle(p(x, y, x + s * 0.68, y + s * 0.55), radius=r, fill=(55, 110, 175))
    d.rounded_rectangle(p(x, y, x + s * 0.55, y + s * 0.68), radius=r, fill=(55, 110, 175))
    e = s * 0.06
    for cx, cy, c in ((x + s * 0.2, y + s * 0.2, (240, 240, 240)), (x + s * 0.8, y + s * 0.8, (40, 40, 40))):
        d.ellipse(p(cx - e, cy - e, cx + e, cy + e), fill=c)


def build_static(lesson):
    img = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(img)
    header = lesson.get("header", "Python")
    logo_kind = lesson.get("logo", "python")
    tw = text_w(F_TITLE, header)
    logo, gap = (82, 26) if logo_kind else (0, 0)
    x = (W - (tw + gap + logo)) / 2
    d.text(p(x, 110), header, font=F_TITLE, fill=YELLOW)
    if logo_kind == "python":
        draw_logo(d, x + tw + gap, 138, logo)
    elif logo_kind == "shield":
        draw_shield(d, x + tw + gap + logo / 2, 182, 0.62, YELLOW, (60, 54, 24))
    badge = lesson.get("badge", f"Урок {lesson['number']} · {lesson['topic']}")
    bw = text_w(F_BADGE, badge) + 56
    bx = (W - bw) / 2
    d.rounded_rectangle(p(bx, 270, bx + bw, 330), radius=30 * S, outline=YELLOW, width=3 * S)
    d.text(p(bx + 28, 280), badge, font=F_BADGE, fill=YELLOW)
    d.rounded_rectangle(p(*PANEL_BOX), radius=36 * S, fill=PANEL, outline=PANEL_BORDER, width=3 * S)
    for i, c in enumerate(DOTS):
        cx, cy, r = PX0 + 48 + i * 40, PY0 + 42, 11
        d.ellipse(p(cx - r, cy - r, cx + r, cy + r), fill=c)
    return img


def draw_colored(d, x, y, text, colors, f):
    """Рисует строку кусками одного цвета (моноширинный шрифт)."""
    i = 0
    while i < len(text):
        j = i
        while j < len(text) and colors[j] == colors[i]:
            j += 1
        d.text(p(x + i * CHAR_W, y), text[i:j], font=f, fill=colors[i])
        i = j


def draw_terminal(d, st, t, dy):
    lines = st["lines"]
    visible = []
    for ln in lines:
        n = bisect.bisect_right(ln["times"], t) if ln["times"] else 0
        if ln["kind"] == "blank" or n > 0:
            visible.append((ln, n))
        else:
            break
    # пустые строки-разделители перед ещё не начатым запуском не показываем
    while visible and visible[-1][0]["kind"] == "blank":
        visible.pop()
    visible = visible[-int((PY1 - CODE_Y - 20) // LINE_H):]
    cursor = None
    for row, (ln, n) in enumerate(visible):
        y = CODE_Y + row * LINE_H + dy
        text = ln["text"][:n]
        if ln["kind"] == "code":
            draw_colored(d, CODE_X, y, text, tokenize(ln["text"]), F_CODE)
        elif ln["kind"] == "cmd":
            d.text(p(CODE_X, y), text, font=F_CODE, fill=GREY)
        elif ln["kind"] == "out":
            d.text(p(CODE_X, y), text, font=F_CODE_B, fill=WHITE)
        elif ln["kind"] == "err":
            d.text(p(CODE_X, y), text, font=F_CODE_B, fill=RED)
        if ln["kind"] in ("code", "cmd"):
            cursor = (CODE_X + n * CHAR_W, y)
    has_output = any(ln["kind"] in ("out", "err") for ln, _ in visible)
    if not visible:
        cursor = (CODE_X, CODE_Y + dy)
    if cursor and not has_output and (st["typing"] or int(t * 2) % 2 == 0):
        cx, cy = cursor
        d.rectangle(p(cx + 2, cy + LINE_H * 0.1, cx + 6, cy + LINE_H * 0.85), fill=YELLOW)


def draw_title_card(d, st, t, dy):
    a = st["title"]
    k = t - a["t0"]
    cx = W / 2
    for i, (txt, f, col, y) in enumerate((
            (a["top"], F_SMALL, GREY, PY0 + 170),
            (a["big"], F_BIG, YELLOW, PY0 + 250),
            (a["bottom"], F_MID, WHITE, PY0 + 440))):
        e = ease((k - 0.15 * i) / 0.45)
        if e <= 0:
            continue
        d.text(p(cx - text_w(f, txt) / 2, y + (1 - e) * 30 + dy), txt, font=f, fill=lerp_col(PANEL, col, e))


def draw_card(d, st, t, dy):
    card = st["card"]
    x = PX0 + 50
    d.text(p(x, PY0 + 95 + dy), card["title"], font=F_CARD_T, fill=YELLOW)
    y = PY0 + 200 + dy
    for text, bt in st["bullets"]:
        e = ease((t - bt) / 0.4)
        off = (1 - e) * -30
        d.ellipse(p(x + off + 4, y + 22, x + off + 20, y + 38), fill=lerp_col(PANEL, YELLOW, e))
        for line in wrap(text, F_CARD, PX1 - x - 100):
            draw_markup(d, x + 44 + off, y, line, F_CARD, lerp_col(PANEL, WHITE, e), lerp_col(PANEL, YELLOW, e))
            y += 62
        y += 26


def draw_syntax(d, st, t, dy):
    syn = st["syntax"]
    code = syn["code"]
    cw = text_w(F_SYN, "a")
    x0 = W / 2 - cw * len(code) / 2
    y0 = PY0 + 300 + dy
    e0 = ease((t - st["mode_t"]) / 0.4)
    colors = tokenize(code)
    active = {i: ht for i, ht in st["hls"]}
    current = st["hls"][-1][0] if st["hls"] else None
    for pi, (s, e, label, side) in enumerate(syn["parts"]):
        if pi in active:
            k = ease((t - active[pi]) / 0.35)
            col = YELLOW if pi == current else (150, 140, 90)
            bx0, bx1 = x0 + s * cw - 6, x0 + e * cw + 6
            d.rounded_rectangle(p(bx0, y0 - 8, bx1, y0 + 100), radius=14 * S,
                                fill=lerp_col(PANEL, (45, 42, 25) if pi == current else (30, 30, 28), k))
            # скобка-указатель и подпись
            if side == "down":
                yb = y0 + 118
                thick_line(d, [(bx0 + 4, yb), (bx0 + 4, yb + 14), (bx1 - 4, yb + 14), (bx1 - 4, yb)], 4,
                           lerp_col(PANEL, col, k))
                ly = yb + 40
            else:
                yb = y0 - 26
                thick_line(d, [(bx0 + 4, yb), (bx0 + 4, yb - 14), (bx1 - 4, yb - 14), (bx1 - 4, yb)], 4,
                           lerp_col(PANEL, col, k))
                ly = yb - 72
            lw = text_w(F_LABEL, label)
            lx = min(max((bx0 + bx1) / 2 - lw / 2, PX0 + 30), PX1 - 30 - lw)
            d.text(p(lx, ly + (1 - k) * 12), label, font=F_LABEL, fill=lerp_col(PANEL, col, k))
    for i, ch in enumerate(code):
        d.text(p(x0 + i * cw, y0), ch, font=F_SYN, fill=lerp_col(PANEL, colors[i], e0))


F_BOX_VAL = font("JetBrainsMono-Bold.ttf", 64)
F_BOX_NAME = font("JetBrainsMono-Bold.ttf", 46)


def draw_boxes(d, st, t, dy):
    boxes = st["boxes"]
    if not boxes:
        return
    gap = 60 if len(boxes) < 3 else 36
    bw = min(300, (980 - (len(boxes) - 1) * gap) / len(boxes))
    bh = 270
    total = len(boxes) * bw + (len(boxes) - 1) * gap
    x = (W - total) / 2
    top = PY0 + 250 + dy
    for b in boxes:
        first = b["old"] is None
        if first:
            ka = ease((t - b["t0"]) / 0.35)  # коробка появляется
        else:
            ka = 1.0
        if ka <= 0:
            x += bw + gap
            continue
        edge = lerp_col(PANEL, YELLOW, ka)
        body = lerp_col(PANEL, (58, 50, 26), ka)
        # значение «падает» в коробку сверху
        def drop(val, k, out=False):
            col = C_STRING if val.startswith('"') else C_NUMBER
            vw = text_w(F_BOX_VAL, val)
            if out:   # старое значение вылетает вверх и тает
                yy = top + 30 - k * 200
                c = lerp_col(PANEL, col, 1 - k)
            else:
                yy = top + 30 - (1 - k) * 170
                c = lerp_col(PANEL, col, k)
            d.text(p(x + bw / 2 - vw / 2, yy), val, font=F_BOX_VAL, fill=c)
        if not first:
            drop(b["old"], ease((t - b["t0"]) / 0.35), out=True)
        drop(b["value"], ease((t - b["t0"] - (0 if first else 0.2)) / 0.45))
        # передняя стенка коробки рисуется поверх нижней части значения
        d.rounded_rectangle(p(x, top + 110, x + bw, top + bh), radius=18 * S, fill=body, outline=edge, width=5 * S)
        thick_line(d, [(x - 14, top + 110), (x + bw + 14, top + 110)], 8, edge)
        # табличка с именем
        nw = text_w(F_BOX_NAME, b["name"]) + 40
        tx = x + bw / 2 - nw / 2
        d.rounded_rectangle(p(tx, top + 158, tx + nw, top + 222), radius=12 * S, fill=lerp_col(PANEL, (25, 25, 25), ka))
        d.text(p(tx + 20, top + 162), b["name"], font=F_BOX_NAME, fill=lerp_col(PANEL, C_NAME, ka))
        x += bw + gap


F_NET = font("JetBrainsMono-Bold.ttf", 32)
NET_SRC_X = PX0 + 110
NET_SRC_Y = [PY0 + 190 + i * 125 for i in range(5)]
NET_SHIELD_X = W / 2 - 10
NET_SRV = (PX1 - 250, PY0 + 210, PX1 - 90, PY0 + 500)  # сервер
NET_RATES = {"normal": 2.5, "flood": 34.0, "shield": 34.0}
NET_LOAD = {"normal": 0.18, "flood": 0.97, "shield": 0.32}
GOOD, BAD, REPLY = (120, 214, 140), (238, 92, 92), YELLOW
NET_HIDDEN_LABEL = "скрыт"


def draw_shield(d, cx, cy, k, edge, fill):
    """Щит с центром (cx, cy), k — масштаб."""
    w, h = 120 * k, 150 * k
    pts = [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h * 0.05),
           (cx, cy + h / 2), (cx - w / 2, cy + h * 0.05)]
    d.polygon([p(*q) for q in pts], fill=fill)
    thick_line(d, pts + [pts[0]], max(2, 6 * k), edge)


def _hash01(i, seed):
    v = math.sin(i * 12.9898 + seed * 78.233) * 43758.5453
    return v - math.floor(v)


def net_load(segs, t):
    load = NET_LOAD["normal"]
    for i, (state, ts) in enumerate(segs):
        if ts > t:
            break
        target = NET_LOAD[state]
        load = load + (target - load) * ease((t - ts) / 1.3)
    if [s for s, ts in segs if ts <= t][-1:] == ["flood"]:
        load += math.sin(t * 13) * 0.02
    return max(0.0, min(1.0, load))


def draw_net(d, st, t, dy):
    segs = st["net"]
    cur = [s for s, ts in segs if ts <= t][-1]
    flood = cur == "flood"
    shield_t = next((ts for s, ts in segs if s == "shield"), None)
    shield_k = ease((t - shield_t) / 0.5) if shield_t is not None and t >= shield_t else 0.0
    load = net_load(segs, t)
    sx0, sy0, sx1, sy1 = NET_SRV
    sy0, sy1 = sy0 + dy, sy1 + dy
    srv_cy = (sy0 + sy1) / 2

    # подписи
    d.text(p(NET_SRC_X - 70, PY0 + 95 + dy), "Интернет", font=F_NET, fill=GREY)
    lab = "Сервер"
    d.text(p((sx0 + sx1) / 2 - text_w(F_NET, lab) / 2, PY0 + 95 + dy), lab, font=F_NET, fill=GREY)

    # пакеты запросов (рисуем до иконок, чтобы они «вылетали» из компьютеров)
    for si, (state, ts) in enumerate(segs):
        te = segs[si + 1][1] if si + 1 < len(segs) else 1e9
        rate = NET_RATES.get(state, 0)
        if not rate:
            continue
        travel = 1.0 if state == "normal" else 0.75
        lo = max(ts, t - travel * 2)
        hi = min(t, te)
        if hi <= lo:
            continue
        for k in range(int(math.ceil((lo - ts) * rate)), int(math.floor((hi - ts) * rate)) + 1):
            spawn = ts + k / rate
            if spawn > t:
                break
            h = _hash01(k, si + 1)
            bad = state != "normal" and h < 0.88
            src_y = NET_SRC_Y[int(h * 997) % 5] + dy
            dst_y = srv_cy + (_hash01(k, si + 7) - 0.5) * 160
            u = (t - spawn) / travel
            x0, x1 = NET_SRC_X + 50, sx0 - 10
            if u <= 1:
                x = x0 + (x1 - x0) * u
                y = src_y + (dst_y - src_y) * u
                col, r = (BAD if bad else GOOD), 9
                if state == "shield" and bad:
                    us = (NET_SHIELD_X - 70 - x0) / (x1 - x0)
                    if u > us:  # отскок от щита
                        back = (u - us) * 1.4
                        x = x0 + (x1 - x0) * us - back * 140
                        y = src_y + (dst_y - src_y) * us + back * 60 * (1 if h > 0.44 else -1)
                        fade = max(0.0, 1 - back * 2.2)
                        if fade <= 0:
                            continue
                        col = lerp_col(PANEL, BAD, fade)
            elif not bad and state != "flood" and u <= 2:
                v = u - 1  # ответ сервера летит обратно
                x = x1 + (x0 - x1) * v
                y = dst_y + (src_y - dst_y) * v
                col, r = REPLY, 6
            else:
                continue
            d.ellipse(p(x - r, y - r, x + r, y + r), fill=col)

    # компьютеры в интернете
    for i, yy in enumerate(NET_SRC_Y):
        y = yy + dy
        hot = flood or (cur == "shield")
        edge = lerp_col(GREY, BAD, 0.8) if hot and i % 2 == 0 else GREY
        d.rounded_rectangle(p(NET_SRC_X - 45, y - 32, NET_SRC_X + 45, y + 24), radius=8 * S,
                            fill=(30, 30, 30), outline=edge, width=3 * S)
        thick_line(d, [(NET_SRC_X - 18, y + 34), (NET_SRC_X + 18, y + 34)], 5, edge)

    # щит CDN
    if shield_k > 0:
        cy = srv_cy
        draw_shield(d, NET_SHIELD_X, cy, 1.5 * _back_out_net(shield_k), YELLOW, (52, 47, 22))
        lab = "CDN"
        d.text(p(NET_SHIELD_X - text_w(F_NET, lab) / 2, cy - 30), lab, font=F_NET,
               fill=lerp_col(PANEL, YELLOW, shield_k))

    # сервер: три блока с лампочками
    led = GOOD if load < 0.6 else ((245, 192, 66) if load < 0.85 else BAD)
    blink = flood and int(t * 6) % 2 == 0
    for i in range(3):
        y0 = sy0 + i * (sy1 - sy0) / 3
        y1 = y0 + (sy1 - sy0) / 3 - 10
        d.rounded_rectangle(p(sx0, y0, sx1, y1), radius=10 * S, fill=(42, 42, 42), outline=(80, 80, 80),
                            width=3 * S)
        for j in range(3):
            lc = led if not (blink and j == i % 3) else (60, 30, 30)
            cx, cyy = sx0 + 28 + j * 26, (y0 + y1) / 2
            d.ellipse(p(cx - 7, cyy - 7, cx + 7, cyy + 7), fill=lc)
        thick_line(d, [(sx0 + 100, (y0 + y1) / 2), (sx1 - 20, (y0 + y1) / 2)], 5, (70, 70, 70))

    # нагрузка CPU
    by = sy1 + 26
    d.text(p(sx0, by), "CPU", font=F_NET, fill=GREY)
    bx0, bx1 = sx0 + 80, sx1
    d.rounded_rectangle(p(bx0, by + 6, bx1, by + 36), radius=8 * S, fill=(40, 40, 40))
    if load > 0.01:
        d.rounded_rectangle(p(bx0, by + 6, bx0 + (bx1 - bx0) * load, by + 36), radius=8 * S, fill=led)

    # статус ответа
    down = flood and load > 0.85
    status = "503" if down else "200 OK"
    scol = BAD if down else GOOD
    if not (down and int(t * 3) % 2 == 1):
        sw = text_w(F_NET, status)
        d.text(p((sx0 + sx1) / 2 - sw / 2, by + 60), status, font=F_NET, fill=scol)

    # IP сервера
    ip_t = st.get("ip_hidden")
    if ip_t is not None and t >= ip_t:
        k = ease((t - ip_t) / 0.4)
        ip, col = "IP: " + NET_HIDDEN_LABEL, lerp_col(GREY, GOOD, k)
    else:
        ip, col = "IP: 203.0.113.7", GREY
    d.text(p((sx0 + sx1) / 2 - text_w(F_NET, ip) / 2, by + 115), ip, font=F_NET, fill=col)


def _back_out_net(x):
    x = max(0.0, min(1.0, x))
    c1 = 1.7
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def draw_markup(d, x, y, line, f, base, accent, center=False):
    """Текст, где слова в `обратных кавычках` выделены цветом."""
    parts = re.split(r"(`[^`]*`)", line)
    clean = "".join(pt.strip("`") for pt in parts)
    if center:
        x = (W - text_w(f, clean)) / 2
    for pt in parts:
        if not pt:
            continue
        hl = pt.startswith("`")
        txt = pt.strip("`")
        d.text(p(x, y), txt, font=f, fill=accent if hl else base)
        x += text_w(f, txt)


def draw_subs(d, t):
    for t0, t1, lines in TL.subs:
        if t0 <= t < t1 + 0.15:
            k = ease((t - t0) / 0.15)
            # на стыке кусков не мигаем: «хвост» показываем, только если следующего нет
            for i, line in enumerate(lines):
                draw_markup(d, 0, SUB_Y + i * 62 + (1 - k) * 8, line, F_SUB,
                            lerp_col(BG, WHITE, k), lerp_col(BG, YELLOW, k), center=True)
            return


def figure_pose(t):
    """Где человечек и в какой позе: (x бедра, направление, «стоит» 0..1, фаза шага, идёт ли)."""
    x, face = SPOTS["right"]
    for w in TL.walks:
        if t < w["t0"]:
            break
        x0, f0 = SPOTS[w["from"]]
        x1, f1 = SPOTS[w["to"]]
        if t >= w["t_end"]:
            x, face = x1, f1
            continue
        go = 1 if x1 < x0 else -1  # идёт влево — смотрит влево
        if t < w["t_up"]:
            k = ease((t - w["t0"]) / STAND_T)
            return x0, (f0 if k < 0.5 else go), k, 0.0, False
        if t < w["t_move"]:
            frac = (t - w["t_up"]) / (w["t_move"] - w["t_up"])
            xx = x0 + (x1 - x0) * frac
            return xx, go, 1.0, abs(xx - x0) / 38, True
        k = 1 - ease((t - w["t_move"]) / STAND_T)
        return x1, (go if k > 0.5 else f1), k, 0.0, False
    return x, face, 0.0, 0.0, False


def draw_figure(d, st, t, f):
    typing = st["typing"]
    happy, confused = st["happy"], st["confused"]
    mouth = TL.mouth[min(f, len(TL.mouth) - 1)]
    X, face, stand, phase, walking = figure_pose(t)
    if stand > 0:
        typing = False

    def P(pt):  # локальные координаты -> экран (с зеркалом)
        return (X + face * pt[0], pt[1])

    def toward(pt, target, k):
        return tuple(pt[i] + (target[i] - pt[i]) * k for i in range(2))

    # --- поза «на коленях за ноутбуком» ---
    bob = math.sin(t * 9) * 3 if typing else math.sin(t * 2.2) * 2
    if happy:
        bob = -abs(math.sin(t * 6)) * 10 * happy
    a1 = math.sin(t * 28) * 7 if typing else 0
    a2 = math.sin(t * 28 + math.pi) * 7 if typing else 0
    kn = {
        "head": (-176, 1490 + bob), "sh": (-144, 1548 + bob), "mid": (-32, 1600 + bob * 0.5), "hip": (0, 1666),
        "ka": (0, 1711), "aa": (0, 1756), "ta": (56, 1756),
        "kb": (-88, 1666), "ab": (-88, 1758), "tb": (-88, 1758),
        "e1": (-164, 1635 + bob * 0.7), "h1": (-170, 1722 + a1),
        "e2": (-132, 1630 + bob * 0.7), "h2": (-140, 1714 + a2),
    }
    if happy:
        kn["h2"] = toward(kn["h2"], (-57, 1415 + bob), happy)
        kn["e2"] = toward(kn["e2"], (-80, 1490 + bob), happy)
    if confused:
        scratch = math.sin(t * 14) * 5
        hx0, hy0 = kn["head"]
        kn["h2"] = toward(kn["h2"], (hx0 + 34 + scratch, hy0 - 36), confused)
        kn["e2"] = toward(kn["e2"], (hx0 + 95, hy0 + 20), confused)
        kn["head"] = (hx0 - 6 * confused, hy0)

    # --- поза «стоит / идёт», ноутбук под мышкой ---
    g = 1758
    wb = -abs(math.sin(phase)) * 6 if walking else 0
    la = 0.5 * math.sin(phase) if walking else 0.0

    def limb(base, ang, length):
        return (base[0] - math.sin(ang) * length, base[1] + math.cos(ang) * length)

    hip = (0, g - 128 + wb)
    sh = (0, g - 244 + wb)
    ka, kb = limb(hip, la, 64), limb(hip, -la, 64)
    aa, ab = limb(hip, la, 126), limb(hip, -la, 126)
    e1 = limb(sh, -la * 0.8, 58)
    stn = {
        "head": (-6, g - 300 + wb), "sh": sh, "mid": (0, g - 186 + wb), "hip": hip,
        "ka": ka, "aa": aa, "ta": (aa[0] - 18, aa[1]),
        "kb": kb, "ab": ab, "tb": (ab[0] - 18, ab[1]),
        "e1": e1, "h1": limb(e1, -la * 0.8 - 0.35, 56),
        "e2": (16, g - 190 + wb), "h2": (-24, g - 150 + wb),
    }
    J = {k: toward(kn[k], stn[k], stand) for k in kn}

    # ноутбук: на полу или под мышкой
    if stand < 0.5:
        lx, ly = -302, 1660
        poly = [(lx, ly), (lx + 108, ly), (lx + 141, ly + 78), (lx + 26, ly + 78)]
        d.polygon([p(*P(q)) for q in poly], fill=(232, 232, 232))
        if typing:
            glow = [(lx + 14, ly + 10), (lx + 98, ly + 10), (lx + 122, ly + 66), (lx + 36, ly + 66)]
            d.polygon([p(*P(q)) for q in glow], fill=(248, 248, 248))
        thick_line(d, [P((lx + 22, ly + 86)), P((lx + 160, ly + 86))], 11, (150, 150, 150))
    else:
        hx2, hy2 = J["h2"]
        thick_line(d, [P((hx2 - 52, hy2 + 4)), P((hx2 + 44, hy2 + 4))], 18, (150, 150, 150))
        thick_line(d, [P((hx2 - 48, hy2 - 2)), P((hx2 + 40, hy2 - 2))], 7, (232, 232, 232))

    thick_line(d, [P(J["sh"]), P(J["mid"]), P(J["hip"])], 20, FIG)
    thick_line(d, [P(J["hip"]), P(J["ka"]), P(J["aa"]), P(J["ta"])], 20, FIG)
    thick_line(d, [P(J["hip"]), P(J["kb"]), P(J["ab"]), P(J["tb"])], 20, FIG)
    thick_line(d, [P(J["sh"]), P(J["e1"]), P(J["h1"])], 17, FIG)
    thick_line(d, [P(J["sh"]), P(J["e2"]), P(J["h2"])], 17, FIG)

    hx, hy = P(J["head"])
    r = 45
    d.ellipse(p(hx - r, hy - r, hx + r, hy + r), fill=FIG)
    dark = (30, 30, 30)
    ex, ey = hx - 21 * face, hy - 5
    if (t % 3.3) < 0.12:
        thick_line(d, [(ex - 5, ey), (ex + 5, ey)], 3, dark)
    else:
        d.ellipse(p(ex - 5, ey - 5, ex + 5, ey + 5), fill=dark)
    mx, my = hx - 24 * face, hy + 18
    if mouth > 0.08:
        mh = 3 + 11 * mouth
        d.ellipse(p(mx - 8, my - mh / 2, mx + 8, my + mh / 2), fill=dark)
    elif happy:
        bx = hx - 38 if face > 0 else hx + 8
        d.arc(p(bx, hy - 4, bx + 30, hy + 22), start=40 if face > 0 else 30, end=150 if face > 0 else 140,
              fill=dark, width=3 * S)
    else:
        thick_line(d, [(mx - 6, my), (mx + 5, my)], 3, dark)

    if happy:
        for k, (dx, dy) in enumerate([(-60, -70), (40, -85), (95, -30)]):
            s_ = 10 * happy * (0.7 + 0.3 * math.sin(t * 8 + k))
            cx, cy = hx + dx * face, hy + dy
            thick_line(d, [(cx - s_, cy), (cx + s_, cy)], 4, YELLOW)
            thick_line(d, [(cx, cy - s_), (cx, cy + s_)], 4, YELLOW)
    if confused:
        col = lerp_col(BG, YELLOW, confused)
        d.text(p(hx - 70 * face - (20 if face < 0 else 0), hy - 130 + math.sin(t * 5) * 4), "?", font=F_MID, fill=col)


# ---------- выпрыгивающие слова ----------
F_POP = font("JetBrainsMono-ExtraBold.ttf", 78)
F_KEY = font("JetBrainsMono-ExtraBold.ttf", 40)
_POP_CACHE = {}


def _pop_layer(pop, pressed=False):
    key = (pop["kind"], pop.get("text"), pop.get("color"), pressed)
    if key in _POP_CACHE:
        return _POP_CACHE[key]
    if pop["kind"] == "key":
        w, h, sh = 250 * S, 110 * S, (4 if pressed else 12) * S
        img = Image.new("RGBA", (w, h + 12 * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        top = 12 * S - sh + (8 * S if pressed else 0)
        d.rounded_rectangle((0, top + sh, w, top + h), radius=20 * S, fill=(150, 150, 150, 255))
        d.rounded_rectangle((0, top, w, top + h - sh), radius=20 * S, fill=(238, 238, 238, 255))
        label, arrow = "ENTER ", "↵"
        f_arrow = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44 * S)
        tw = F_KEY.getlength(label) + f_arrow.getlength(arrow)
        x0 = (w - tw) / 2
        ty = top + (h - sh) / 2 - 26 * S
        d.text((x0, ty), label, font=F_KEY, fill=(40, 40, 40, 255))
        d.text((x0 + F_KEY.getlength(label), ty - 4 * S), arrow, font=f_arrow, fill=(40, 40, 40, 255))
    else:
        text = pop["text"]
        stroke = 7 * S
        bbox = F_POP.getbbox(text, stroke_width=stroke)
        w, h = bbox[2] - bbox[0] + 20 * S, bbox[3] - bbox[1] + 26 * S
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        ox, oy = 10 * S - bbox[0], 8 * S - bbox[1]
        d.text((ox + 6 * S, oy + 9 * S), text, font=F_POP, fill=(0, 0, 0, 140),
               stroke_width=stroke, stroke_fill=(0, 0, 0, 140))
        d.text((ox, oy), text, font=F_POP, fill=pop["color"] + (255,),
               stroke_width=stroke, stroke_fill=(24, 24, 24, 255))
    _POP_CACHE[key] = img
    return img


def _back_out(x):
    x = max(0.0, min(1.0, x))
    c1 = 2.2
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def draw_pops(img, t):
    for pop in TL.pops:
        if not (pop["t0"] <= t < pop["t1"]):
            continue
        x = t - pop["t0"]
        left = pop["t1"] - t
        alpha = min(1.0, left / 0.25)
        cx, cy = POP_POS
        rot = 0.0
        if pop["kind"] == "key":
            pressed = pop["press"] <= t < pop["press"] + 0.15
            layer = _pop_layer(pop, pressed)
            scale = _back_out(x / 0.2)
        else:
            layer = _pop_layer(pop)
            scale = _back_out(x / 0.35) * (0.85 + 0.15 * alpha)
            rot = pop["rot"] + math.sin(x * 12) * 5 * math.exp(-x * 4)
            cy -= 18 * _back_out(x / 0.35) + math.sin(x * 3) * 4
            if pop["shake"]:
                cx += math.sin(x * 45) * 10 * math.exp(-x * 5)
        if scale <= 0.02 or alpha <= 0:
            continue
        lw, lh = max(1, int(layer.width * scale)), max(1, int(layer.height * scale))
        lay = layer.resize((lw, lh), Image.BICUBIC)
        if rot:
            lay = lay.rotate(rot, resample=Image.BICUBIC, expand=True)
        if alpha < 1:
            a = lay.getchannel("A").point(lambda v: int(v * alpha))
            lay.putalpha(a)
        px, py = int(cx * S - lay.width / 2), int(cy * S - lay.height / 2)
        img.paste(lay, (px, py), lay)


def render_frame(f):
    t = f / FPS
    st = TL.state(t)
    img = STATIC.copy()
    d = ImageDraw.Draw(img)

    # прогресс-бар сверху
    d.rectangle(p(0, 0, W * t / TL.duration, 8), fill=YELLOW)

    k = ease((t - st["mode_t"]) / TRANSITION) if st["mode"] else 0
    dy = (1 - k) * 30
    mode = st["mode"]
    if mode == "term":
        draw_terminal(d, st, t, dy)
    elif mode == "title":
        draw_title_card(d, st, t, dy)
    elif mode == "card":
        draw_card(d, st, t, dy)
    elif mode == "syntax":
        draw_syntax(d, st, t, dy)
    elif mode == "boxes":
        draw_boxes(d, st, t, dy)
    elif mode == "net":
        draw_net(d, st, t, dy)
    if mode and k < 1:  # плавное появление новой сцены
        region = p(PX0 + 10, PY0 + 70, PX1 - 10, PY1 - 10)
        crop = img.crop(region)
        img.paste(Image.blend(Image.new("RGB", crop.size, PANEL), crop, k), region[:2])

    draw_subs(d, t)
    draw_figure(d, st, t, f)
    draw_pops(img, t)

    img = img.resize((W, H), Image.LANCZOS)
    if t < 0.6:
        img = Image.blend(Image.new("RGB", (W, H), BG), img, ease(t / 0.6))
    return img.tobytes()


# ======================================================================
#  Звук
# ======================================================================
def _onepole_lowpass(x, cutoff):
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        a = 1 - math.exp(-2 * math.pi * cutoff[i] / SR)
        acc += a * (x[i] - acc)
        y[i] = acc
    return y


def sfx_sound(kind, rng):
    if kind in ("key", "space", "enter"):
        L = int(0.09 * SR)
        t = np.arange(L) / SR
        noise = rng.standard_normal(L)
        hp = np.diff(noise, prepend=0)
        click = hp * np.exp(-t * 500) * 0.28
        f0 = {"key": rng.uniform(190, 280), "space": rng.uniform(110, 140), "enter": rng.uniform(150, 180)}[kind]
        phase = 2 * np.pi * np.cumsum(f0 * (1 + 0.8 * np.exp(-t * 70))) / SR
        thock = np.sin(phase) * np.exp(-t * (45 if kind == "key" else 30)) * 0.55
        # «щелчок» дна клавиши
        bottom = np.zeros(L)
        j = int(rng.uniform(0.006, 0.011) * SR)
        bl = min(L - j, int(0.012 * SR))
        bottom[j:j + bl] = hp[:bl] * np.exp(-np.arange(bl) / SR * 700) * 0.18
        s = (click + thock + bottom) * rng.uniform(0.75, 1.0)
        if kind == "enter":
            s *= 1.3
            j = int(0.07 * SR)
            s[j:] += (click[: L - j] * 0.6)
        return s * 0.55
    if kind in ("pop", "pop_soft"):
        L = int(0.18 * SR)
        t = np.arange(L) / SR
        f = 420 + 700 * (1 - np.exp(-t * 60))
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 22)
        return s * (0.32 if kind == "pop" else 0.18)
    if kind == "alarm":
        L = int(1.5 * SR)
        t = np.arange(L) / SR
        fr = np.where((t * 4).astype(int) % 2 == 0, 880, 660)
        s = np.sign(np.sin(2 * np.pi * np.cumsum(fr) / SR)) * 0.5 + np.sin(2 * np.pi * np.cumsum(fr) / SR) * 0.5
        env = np.clip(1.5 - t, 0, 1) * (0.6 + 0.4 * ((t * 8) % 1 < 0.7))
        return s * env * 0.07
    if kind == "boing":
        L = int(0.4 * SR)
        t = np.arange(L) / SR
        f = 260 + 520 * (1 - np.exp(-t * 22)) + 40 * np.sin(2 * np.pi * 16 * t) * np.exp(-t * 5)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
        return s * 0.26
    if kind == "step":
        L = int(0.12 * SR)
        t = np.arange(L) / SR
        thump = np.sin(2 * np.pi * rng.uniform(85, 110) * t) * np.exp(-t * 40)
        scuff = _onepole_lowpass(rng.standard_normal(L), np.full(L, 1800.0)) * np.exp(-t * 60)
        return (thump * 0.4 + scuff * 0.25) * rng.uniform(0.7, 1.0)
    if kind == "tick":
        L = int(0.08 * SR)
        t = np.arange(L) / SR
        return np.sin(2 * np.pi * 1760 * t) * np.exp(-t * 60) * 0.18
    if kind == "chime":
        L = int(1.6 * SR)
        t = np.arange(L) / SR
        s = np.zeros(L)
        for i, fr in enumerate((1046.5, 1318.5, 1568.0, 2093.0)):
            j = int(i * 0.07 * SR)
            tt = t[: L - j]
            bell = (np.sin(2 * np.pi * fr * tt) + 0.35 * np.sin(2 * np.pi * fr * 2.01 * tt)
                    + 0.15 * np.sin(2 * np.pi * fr * 3.03 * tt)) * np.exp(-tt * 3.2)
            s[j:] += bell
        return s * 0.09
    if kind == "error":
        L = int(0.42 * SR)
        t = np.arange(L) / SR
        s = np.zeros(L)
        for i, fr in enumerate((233, 175)):
            j = int(i * 0.17 * SR)
            ln = int(0.2 * SR)
            tt = np.arange(ln) / SR
            tone = np.tanh(np.sin(2 * np.pi * fr * tt) * 3) * np.exp(-tt * 9)
            s[j:j + ln] += tone[: L - j]
        return s * 0.16
    if kind == "whoosh":
        L = int(0.5 * SR)
        t = np.arange(L) / SR
        env = np.sin(np.pi * t / t[-1]) ** 2
        cutoff = 300 + 3500 * np.sin(np.pi * t / t[-1]) ** 2
        s = _onepole_lowpass(rng.standard_normal(L), cutoff) * env
        return s * 0.35
    if kind == "sparkle":
        L = int(0.9 * SR)
        t = np.arange(L) / SR
        s = np.zeros(L)
        for i in range(7):
            j = int(rng.uniform(0, 0.45) * SR)
            fr = rng.uniform(2200, 4200)
            tt = t[: L - j]
            s[j:] += np.sin(2 * np.pi * fr * tt) * np.exp(-tt * 14)
        return s * 0.05
    raise ValueError(kind)


def music_bed(n):
    """Спокойная фоновая подложка: пэды + мягкие арпеджио, 80 BPM."""
    beat = 60 / 80
    chord_len = beat * 4
    chords = [
        [57, 60, 64, 67],  # Am7
        [53, 57, 60, 64],  # Fmaj7
        [48, 55, 60, 64],  # C
        [55, 59, 62, 67],  # G
    ]
    midi = lambda m: 440 * 2 ** ((m - 69) / 12)
    out = np.zeros(n, dtype=np.float32)
    t_total = n / SR
    ci = 0
    t0 = 0.0
    while t0 < t_total:
        chord = chords[ci % 4]
        L = int((chord_len + 1.5) * SR)
        tt = np.arange(L) / SR
        env = np.minimum(1, tt / 0.9) * np.exp(-np.maximum(0, tt - chord_len) * 3)
        pad = np.zeros(L)
        for m in chord:
            fr = midi(m - 12)
            pad += np.sin(2 * np.pi * fr * tt) + np.sin(2 * np.pi * fr * 1.004 * tt + 1)
        pad *= env * 0.012
        # арпеджио восьмыми
        for k in range(8):
            m = chord[[0, 2, 1, 3, 2, 1, 3, 2][k]] + 12
            j = int(k * beat / 2 * SR)
            pl = int(0.9 * SR)
            pt = np.arange(pl) / SR
            pluck = (np.sin(2 * np.pi * midi(m) * pt) + 0.3 * np.sin(4 * np.pi * midi(m) * pt)) * np.exp(-pt * 5)
            end = min(L, j + pl)
            pad[j:end] += pluck[: end - j] * 0.018
        i = int(t0 * SR)
        e = min(n, i + L)
        out[i:e] += pad[: e - i].astype(np.float32)
        t0 += chord_len
        ci += 1
    fade = int(2 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    out[: int(SR)] *= np.linspace(0, 1, int(SR))
    return out


def make_audio(tl, path, music=True):
    n = int((tl.duration + 0.5) * SR)
    mix = np.zeros(n, dtype=np.float32)
    voice = tl.voice_track[:n]
    voice = np.pad(voice, (0, n - len(voice)))
    mix += voice * 0.95
    rng = np.random.default_rng(tl.lesson["number"])
    for t, kind in tl.sfx:
        s = sfx_sound(kind, rng).astype(np.float32)
        i = int(t * SR)
        if i >= n:
            continue
        mix[i:i + len(s)] += s[: n - i]
    if music:
        bed = music_bed(n)
        # приглушаем музыку, когда говорит диктор
        env = np.abs(voice)
        win = int(0.3 * SR)
        env = np.convolve(env, np.ones(win) / win, mode="same")
        duck = 1 - 0.55 * np.clip(env / 0.05, 0, 1)
        mix += bed * duck
    peak = np.max(np.abs(mix)) or 1
    mix = mix / peak * 0.89
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((mix * 32767).astype(np.int16).tobytes())


# ======================================================================
#  Сборка видео
# ======================================================================
def _init(tl, static):
    global TL, STATIC
    TL, STATIC = tl, static


def set_code_size(size):
    global F_CODE, F_CODE_B, CHAR_W, LINE_H
    F_CODE = font("JetBrainsMono-Regular.ttf", size)
    F_CODE_B = font("JetBrainsMono-Bold.ttf", size)
    CHAR_W = F_CODE.getlength("a") / S
    LINE_H = int(size * 1.5)


INTER_DIR = "/usr/share/fonts/opentype/inter"


def set_text_font(family):
    """Шрифт для обычного текста. "inter" — для таджикских букв ҳ, ӣ, ӯ (их нет в JetBrains Mono)."""
    global F_TITLE, F_BADGE, F_SUB, F_CARD_T, F_CARD, F_BIG, F_MID, F_SMALL, F_LABEL, F_POP, F_NET
    if family != "inter":
        return

    def f(weight, size):
        return ImageFont.truetype(os.path.join(INTER_DIR, f"Inter-{weight}.otf"), int(size * S))

    F_TITLE, F_BADGE, F_SUB = f("ExtraBold", 96), f("SemiBold", 34), f("SemiBold", 46)
    F_CARD_T, F_CARD, F_BIG = f("ExtraBold", 56), f("Medium", 46), f("Black", 118)
    F_MID, F_SMALL, F_LABEL = f("Bold", 58), f("Medium", 40), f("SemiBold", 36)
    F_POP, F_NET = f("Black", 86), f("Bold", 34)


def prepare(lesson):
    set_code_size(lesson.get("code_size", 40))
    set_text_font(lesson.get("text_font", "mono"))
    global NET_HIDDEN_LABEL, PIPER_SPEED
    PIPER_SPEED = lesson.get("voice_speed", PIPER_SPEED)
    NET_HIDDEN_LABEL = lesson.get("net_hidden_label", NET_HIDDEN_LABEL)
    tl = Timeline(lesson)
    _init(tl, build_static(lesson))
    return tl


def preview(lesson, times, out_dir):
    prepare(lesson)
    for sec in times:
        f = int(sec * FPS)
        img = Image.frombytes("RGB", (W, H), render_frame(f))
        img.save(os.path.join(out_dir, f"_preview_{sec}.png"))
    print(f"Длительность урока: {TL.duration:.1f} c")


def render(lesson, out_base):
    tl = prepare(lesson)
    print(f"Урок {lesson['number']}: {tl.duration:.1f} c, {tl.frames} кадров")
    silent = out_base + "_video.mp4"
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", silent],
        stdin=subprocess.PIPE,
    )
    ctx = mp.get_context("fork")
    with ctx.Pool(os.cpu_count()) as pool:
        for i, frame in enumerate(pool.imap(render_frame, range(tl.frames), chunksize=6)):
            ff.stdin.write(frame)
            if i % 300 == 0:
                print(f"  кадр {i}/{tl.frames}", flush=True)
    ff.stdin.close()
    ff.wait()

    outputs = []
    for music, suffix in ((True, ""), (False, "_bez_muzyki")):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav = tmp.name
        make_audio(tl, wav, music=music)
        out = out_base + suffix + ".mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav,
                        "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100",
                        "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", out], check=True)
        os.remove(wav)
        outputs.append(out)
    os.remove(silent)
    for o in outputs:
        print("Готово:", o)
    return outputs
