"""Движок видео-уроков «Python с нуля» (вертикальное видео 1080x1920).

Урок описывается списком «битов»: что говорит диктор (say), какие субтитры
показать (sub) и что происходит на экране (do). Движок сам озвучивает текст
голосом RHVoice, подгоняет тайминг под длину фраз, печатает код со звуком
клавиш, добавляет звуковые эффекты, фоновую музыку и анимирует человечка.

Нужно: ffmpeg, RHVoice (apt install rhvoice rhvoice-russian), numpy, Pillow.
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

# ---------- тайминг ----------
CPS = 13          # скорость печати кода, символов/с
RUN_CPS = 30      # скорость «ввода» команды запуска
TRANSITION = 0.4  # смена сцены
BEAT_GAP = 0.5    # пауза между фразами
INTRO = 0.7
OUTRO = 1.5


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


def Beat(say=None, sub=None, do=()):
    return {"say": say, "sub": sub if sub is not None else say, "do": list(do)}


MODE_TYPES = {"title", "card", "syntax", "term"}
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
    """Синтез речи RHVoice -> numpy float32 @ 44.1 кГц (с кэшем)."""
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.md5(f"{VOICE}|{VOICE_RATE}|{text}".encode()).hexdigest()
    path = os.path.join(CACHE, key + ".wav")
    if not os.path.exists(path):
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
        rnd = random.Random(lesson["number"])
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
            a["cmd_times"] = times
            a["out_times"] = outs
            return (outs[-1] if outs else cmd_end) - t0 + 0.3
        raise ValueError(f"неизвестное действие {typ}")

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
    tw = text_w(F_TITLE, "Python")
    logo, gap = 82, 26
    x = (W - (tw + gap + logo)) / 2
    d.text(p(x, 110), "Python", font=F_TITLE, fill=YELLOW)
    draw_logo(d, x + tw + gap, 138, logo)
    badge = f"Урок {lesson['number']} · {lesson['topic']}"
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


def draw_figure(d, st, t, f):
    ox, oy = 40, 70
    typing = st["typing"]
    happy, confused = st["happy"], st["confused"]
    mouth = TL.mouth[min(f, len(TL.mouth) - 1)]

    bob = math.sin(t * 9) * 3 if typing else math.sin(t * 2.2) * 2
    if happy:
        bob = -abs(math.sin(t * 6)) * 10 * happy

    # ноутбук
    lx, ly = 490 + ox, 1590 + oy
    d.polygon([p(lx, ly), p(lx + 108, ly), p(lx + 141, ly + 78), p(lx + 26, ly + 78)], fill=(232, 232, 232))
    if typing:
        d.polygon([p(lx + 14, ly + 10), p(lx + 98, ly + 10), p(lx + 122, ly + 66), p(lx + 36, ly + 66)],
                  fill=(248, 248, 248))
    thick_line(d, [(lx + 22, ly + 86), (lx + 160, ly + 86)], 11, (150, 150, 150))

    sh = (648 + ox, 1478 + oy + bob)
    mid = (760 + ox, 1530 + oy + bob * 0.5)
    hip = (792 + ox, 1596 + oy)
    thick_line(d, [sh, mid, hip], 20, FIG)
    thick_line(d, [hip, (792 + ox, 1686 + oy), (848 + ox, 1686 + oy)], 20, FIG)
    thick_line(d, [hip, (704 + ox, 1596 + oy), (704 + ox, 1688 + oy)], 20, FIG)

    a1 = math.sin(t * 28) * 7 if typing else 0
    a2 = math.sin(t * 28 + math.pi) * 7 if typing else 0
    hand1 = (622 + ox, 1652 + oy + a1)
    hand2 = (652 + ox, 1644 + oy + a2)
    elbow1 = (628 + ox, 1565 + oy + bob * 0.7)
    elbow2 = (660 + ox, 1560 + oy + bob * 0.7)
    hx, hy, r = 616 + ox, 1420 + oy + bob, 45

    def toward(pt, target, k):
        return tuple(pt[i] + (target[i] - pt[i]) * k for i in range(2))

    if happy:
        hand2 = toward(hand2, (735 + ox, 1345 + oy + bob), happy)
        elbow2 = toward(elbow2, (712 + ox, 1420 + oy + bob), happy)
    if confused:
        scratch = math.sin(t * 14) * 5
        hand2 = toward(hand2, (hx + 34 + scratch, hy - 36), confused)
        elbow2 = toward(elbow2, (hx + 95, hy + 20), confused)
        hx += -6 * confused
    thick_line(d, [sh, elbow1, hand1], 17, FIG)
    thick_line(d, [sh, elbow2, hand2], 17, FIG)

    d.ellipse(p(hx - r, hy - r, hx + r, hy + r), fill=FIG)
    dark = (30, 30, 30)
    ex, ey = hx - 21, hy - 5
    if (t % 3.3) < 0.12:
        thick_line(d, [(ex - 5, ey), (ex + 5, ey)], 3, dark)
    else:
        d.ellipse(p(ex - 5, ey - 5, ex + 5, ey + 5), fill=dark)
    mx, my = hx - 24, hy + 18
    if mouth > 0.08:
        mh = 3 + 11 * mouth
        d.ellipse(p(mx - 8, my - mh / 2, mx + 8, my + mh / 2), fill=dark)
    elif happy:
        d.arc(p(hx - 38, hy - 4, hx - 8, hy + 22), start=40, end=150, fill=dark, width=3 * S)
    else:
        thick_line(d, [(mx - 6, my), (mx + 5, my)], 3, dark)

    if happy:
        for k, (dx, dy) in enumerate([(-60, -70), (40, -85), (95, -30)]):
            s_ = 10 * happy * (0.7 + 0.3 * math.sin(t * 8 + k))
            cx, cy = hx + dx, hy + dy
            thick_line(d, [(cx - s_, cy), (cx + s_, cy)], 4, YELLOW)
            thick_line(d, [(cx, cy - s_), (cx, cy + s_)], 4, YELLOW)
    if confused:
        q = "?"
        col = lerp_col(BG, YELLOW, confused)
        d.text(p(hx - 70, hy - 130 + math.sin(t * 5) * 4), q, font=F_MID, fill=col)


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
    if mode and k < 1:  # плавное появление новой сцены
        region = p(PX0 + 10, PY0 + 70, PX1 - 10, PY1 - 10)
        crop = img.crop(region)
        img.paste(Image.blend(Image.new("RGB", crop.size, PANEL), crop, k), region[:2])

    draw_subs(d, t)
    draw_figure(d, st, t, f)

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


def prepare(lesson):
    set_code_size(lesson.get("code_size", 40))
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
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", out], check=True)
        os.remove(wav)
        outputs.append(out)
    os.remove(silent)
    for o in outputs:
        print("Готово:", o)
    return outputs
