"""Генератор вертикального видео-урока по Python (1080x1920, 30 fps).

Стиль: тёмный фон, жёлтый заголовок «Python» с логотипом, окно терминала,
в котором печатается код, и жёлтый человечек за ноутбуком.

Запуск:  python3 reels/make_video.py
Результат: reels/python_for_loop.mp4 (со звуком клавиш) и
           reels/python_for_loop_silent.mp4 (без звука).
"""

import math
import os
import random
import re
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = "/usr/share/fonts/truetype/jetbrains-mono"

W, H = 1080, 1920
S = 2  # суперсэмплинг для сглаживания линий
FPS = 30

# ---------- урок ----------
CODE = [
    "# Урок: цикл for",
    'fruits = ["яблоко", "банан", "киви"]',
    "",
    "for fruit in fruits:",
    '    print("Я люблю", fruit)',
]
RUN_CMD = "$ python main.py"
OUTPUT = ["Я люблю яблоко", "Я люблю банан", "Я люблю киви"]
CAPTION = ["for перебирает список", "и повторяет код для", "каждого элемента"]

# ---------- цвета ----------
BG = (32, 32, 32)
TERM_BG = (19, 19, 19)
TERM_BORDER = (52, 52, 52)
YELLOW = (247, 224, 122)
FIG = (246, 218, 74)
DOTS = [(237, 95, 87), (245, 192, 66), (86, 168, 84)]
C_DEFAULT = (212, 212, 212)
C_COMMENT = (106, 153, 85)
C_KEYWORD = (197, 134, 192)
C_BUILTIN = (220, 220, 170)
C_STRING = (206, 145, 120)
C_NUMBER = (181, 206, 168)
C_NAME = (156, 220, 254)
C_PROMPT = (120, 120, 120)
C_OUT = (235, 235, 235)

# ---------- тайминг (сек) ----------
T_TYPE_START = 0.9
CPS = 16  # символов в секунду
NEWLINE_PAUSE = 0.3


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def tokenize(line):
    """Возвращает список цветов для каждого символа строки."""
    colors = [C_DEFAULT] * len(line)
    rules = [
        (r"#.*", C_COMMENT),
        (r'"[^"]*"', C_STRING),
        (r"\b(for|in|if|elif|else|while|def|return|import|from|True|False|None)\b", C_KEYWORD),
        (r"\b(print|range|len|input|int|str)\b", C_BUILTIN),
        (r"\b\d+\b", C_NUMBER),
        (r"\b[A-Za-z_]\w*\b", C_NAME),
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


# ---------- расписание печати ----------
def build_schedule():
    """Время появления каждого символа кода: список (строка, кол-во символов, время)."""
    events = []  # (time, line_idx, chars_visible)
    rnd = random.Random(7)
    t = T_TYPE_START
    for li, line in enumerate(CODE):
        for ci in range(1, len(line) + 1):
            t += (1 / CPS) * rnd.uniform(0.6, 1.4)
            events.append((t, li, ci, line[ci - 1] != " "))
        t += NEWLINE_PAUSE
        events.append((t, li + 1, 0, False))
    return events, t


EVENTS, T_TYPE_END = build_schedule()
T_RUN_START = T_TYPE_END + 0.5
T_RUN_END = T_RUN_START + len(RUN_CMD) / 30
T_OUT = [T_RUN_END + 0.45 + i * 0.4 for i in range(len(OUTPUT))]
T_CAPTION = T_OUT[-1] + 0.5
DURATION = T_CAPTION + 3.2


def typed_state(t):
    """Сколько строк/символов кода напечатано к моменту t."""
    line, chars = 0, 0
    for et, li, ci, _ in EVENTS:
        if et > t:
            break
        line, chars = li, ci
    return line, chars


def key_times():
    return [et for et, _, _, visible in EVENTS if visible] + [
        T_RUN_START + i / 30 for i in range(len(RUN_CMD))
    ]


# ---------- шрифты ----------
def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), int(size * S))


F_TITLE = font("JetBrainsMono-ExtraBold.ttf", 118)
F_CODE = font("JetBrainsMono-Regular.ttf", 37)
F_CODE_B = font("JetBrainsMono-Bold.ttf", 37)
F_CAPTION = font("JetBrainsMono-Medium.ttf", 42)
CHAR_W = F_CODE.getlength("a") / S
LINE_H = 56

# ---------- геометрия ----------
TERM = (20, 420, W - 20, 1110)  # x0, y0, x1, y1
CODE_X = TERM[0] + 44
CODE_Y = TERM[1] + 100


def p(*xy):
    return tuple(int(v * S) for v in xy)


def thick_line(d, pts, width, color):
    """Ломаная с круглыми концами и стыками."""
    w = int(width * S)
    sp = [p(*pt) for pt in pts]
    d.line(sp, fill=color, width=w, joint="curve")
    r = w / 2
    for x, y in sp:
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def draw_logo(d, x, y, size):
    s = size
    r = s * 0.22
    # синяя половинка
    d.rounded_rectangle(p(x, y, x + s * 0.68, y + s * 0.68), radius=int(r * S), fill=(55, 110, 175))
    # жёлтая половинка
    d.rounded_rectangle(
        p(x + s * 0.32, y + s * 0.32, x + s, y + s), radius=int(r * S), fill=(247, 205, 70)
    )
    # синяя поверх в зоне пересечения, чтобы получился «замок»
    d.rounded_rectangle(
        p(x, y, x + s * 0.68, y + s * 0.55), radius=int(r * S), fill=(55, 110, 175)
    )
    e = s * 0.06
    cx, cy = x + s * 0.2, y + s * 0.2
    d.ellipse(p(cx - e, cy - e, cx + e, cy + e), fill=(240, 240, 240))
    cx, cy = x + s * 0.8, y + s * 0.8
    d.ellipse(p(cx - e, cy - e, cx + e, cy + e), fill=(40, 40, 40))


def draw_title(d):
    text = "Python"
    tw = F_TITLE.getlength(text) / S
    logo = 90
    gap = 28
    total = tw + gap + logo
    x = (W - total) / 2
    d.text(p(x, 175), text, font=F_TITLE, fill=YELLOW)
    draw_logo(d, x + tw + gap, 205, logo)


def draw_terminal(d, t):
    x0, y0, x1, y1 = TERM
    d.rounded_rectangle(p(x0, y0, x1, y1), radius=36 * S, fill=TERM_BG, outline=TERM_BORDER, width=3 * S)
    for i, c in enumerate(DOTS):
        cx, cy, r = x0 + 48 + i * 40, y0 + 42, 11
        d.ellipse(p(cx - r, cy - r, cx + r, cy + r), fill=c)

    line, chars = typed_state(t)
    typing_code = t < T_TYPE_END
    cursor_pos = None

    for li, text in enumerate(CODE):
        if li > line:
            break
        visible = text if li < line else text[:chars]
        colors = tokenize(text)
        y = CODE_Y + li * LINE_H
        for ci, ch in enumerate(visible):
            d.text(p(CODE_X + ci * CHAR_W, y), ch, font=F_CODE, fill=colors[ci])
        if li == line and typing_code:
            cursor_pos = (CODE_X + len(visible) * CHAR_W, y)

    base_y = CODE_Y + (len(CODE) + 1) * LINE_H
    if t >= T_RUN_START:
        n = min(len(RUN_CMD), int((t - T_RUN_START) * 30) + 1)
        d.text(p(CODE_X, base_y), RUN_CMD[:n], font=F_CODE, fill=C_PROMPT)
        if t < T_OUT[0]:
            cursor_pos = (CODE_X + n * CHAR_W, base_y)
    elif not typing_code:
        cursor_pos = (CODE_X, base_y)

    for i, out in enumerate(OUTPUT):
        if t >= T_OUT[i]:
            d.text(p(CODE_X, base_y + (i + 1) * LINE_H), out, font=F_CODE_B, fill=C_OUT)

    if t >= T_OUT[-1]:
        cursor_pos = None

    if cursor_pos:
        busy = typing_code or (T_RUN_START <= t < T_RUN_END)
        if busy or int(t * 2) % 2 == 0:
            cx, cy = cursor_pos
            d.rectangle(p(cx + 2, cy + 6, cx + 6, cy + 46), fill=YELLOW)


def draw_caption(d, t):
    if t < T_CAPTION:
        return 0
    a = ease((t - T_CAPTION) / 0.5)
    col = tuple(int(BG[i] + (C_OUT[i] - BG[i]) * a) for i in range(3))
    y0 = 1165 + (1 - a) * 20
    for i, line in enumerate(CAPTION):
        tw = F_CAPTION.getlength(line) / S
        x = (W - tw) / 2
        if i == 0:
            # «for» выделяем жёлтым
            d.text(p(x, y0), "for", font=F_CAPTION, fill=tuple(
                int(BG[k] + (YELLOW[k] - BG[k]) * a) for k in range(3)))
            d.text(p(x + F_CAPTION.getlength("for ") / S, y0), line[4:], font=F_CAPTION, fill=col)
        else:
            d.text(p(x, y0 + i * 58), line, font=F_CAPTION, fill=col)
    return a


def draw_figure(d, t):
    """Жёлтый человечек на коленях за ноутбуком."""
    ox, oy = 40, 70  # общий сдвиг фигуры
    typing = (T_TYPE_START <= t < T_TYPE_END) or (T_RUN_START <= t < T_RUN_END)
    happy = ease((t - T_OUT[-1]) / 0.45) if t >= T_OUT[-1] else 0.0

    bob = math.sin(t * 9) * 3 if typing else math.sin(t * 2.2) * 2
    if happy:
        bob = -abs(math.sin(t * 6)) * 10 * happy

    # ноутбук
    lx, ly = 490 + ox, 1590 + oy
    d.polygon([p(lx, ly), p(lx + 108, ly), p(lx + 141, ly + 78), p(lx + 26, ly + 78)], fill=(232, 232, 232))
    if typing:  # свечение экрана при печати
        d.polygon([p(lx + 14, ly + 10), p(lx + 98, ly + 10), p(lx + 122, ly + 66), p(lx + 36, ly + 66)],
                  fill=(244, 244, 244))
    thick_line(d, [(lx + 22, ly + 86), (lx + 160, ly + 86)], 11, (150, 150, 150))

    # тело
    sh = (648 + ox, 1478 + oy + bob)        # плечи
    mid = (760 + ox, 1530 + oy + bob * 0.5)  # спина
    hip = (792 + ox, 1596 + oy)
    thick_line(d, [sh, mid, hip], 20, FIG)
    # ноги
    thick_line(d, [hip, (792 + ox, 1686 + oy), (848 + ox, 1686 + oy)], 20, FIG)
    thick_line(d, [hip, (704 + ox, 1596 + oy), (704 + ox, 1688 + oy)], 20, FIG)

    # руки
    if typing:
        a1 = math.sin(t * 28) * 7
        a2 = math.sin(t * 28 + math.pi) * 7
    else:
        a1 = a2 = 0
    hand1 = (622 + ox, 1652 + oy + a1)
    hand2 = (652 + ox, 1644 + oy + a2)
    elbow1 = (628 + ox, 1565 + oy + bob * 0.7)
    elbow2 = (660 + ox, 1560 + oy + bob * 0.7)
    if happy:
        # вторая рука поднимается вверх — «получилось!»
        up_hand = (735 + ox, 1345 + oy + bob)
        up_elbow = (712 + ox, 1420 + oy + bob)
        hand2 = tuple(hand2[k] + (up_hand[k] - hand2[k]) * happy for k in range(2))
        elbow2 = tuple(elbow2[k] + (up_elbow[k] - elbow2[k]) * happy for k in range(2))
    thick_line(d, [sh, elbow1, hand1], 17, FIG)
    thick_line(d, [sh, elbow2, hand2], 17, FIG)

    # голова
    hx, hy, r = 616 + ox, 1420 + oy + bob, 45
    d.ellipse(p(hx - r, hy - r, hx + r, hy + r), fill=FIG)
    blink = (t % 3.1) < 0.12
    ex, ey = hx - 21, hy - 3
    if blink:
        thick_line(d, [(ex - 5, ey), (ex + 5, ey)], 3, (30, 30, 30))
    else:
        d.ellipse(p(ex - 5, ey - 5, ex + 5, ey + 5), fill=(30, 30, 30))
    if happy:
        # улыбка
        d.arc(p(hx - 36, hy - 4, hx - 6, hy + 22), start=40, end=150, fill=(30, 30, 30), width=3 * S)
        # искорки над головой
        for k, (dx, dy) in enumerate([(-60, -70), (40, -85), (95, -30)]):
            s_ = 10 * happy * (0.7 + 0.3 * math.sin(t * 8 + k))
            cx, cy = hx + dx, hy + dy
            thick_line(d, [(cx - s_, cy), (cx + s_, cy)], 4, YELLOW)
            thick_line(d, [(cx, cy - s_), (cx, cy + s_)], 4, YELLOW)


def render_frame(t):
    img = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(img)
    draw_title(d)
    draw_terminal(d, t)
    draw_caption(d, t)
    draw_figure(d, t)
    img = img.resize((W, H), Image.LANCZOS)
    if t < 0.6:  # плавное появление
        bg = Image.new("RGB", (W, H), BG)
        img = Image.blend(bg, img, ease(t / 0.6))
    return img


# ---------- звук ----------
def make_audio(path):
    sr = 44100
    n = int((DURATION + 0.5) * sr)
    audio = np.zeros(n, dtype=np.float32)
    rnd = np.random.default_rng(3)
    for kt in key_times():
        length = int(0.035 * sr)
        env = np.exp(-np.linspace(0, 9, length))
        click = rnd.standard_normal(length) * env * rnd.uniform(0.18, 0.3)
        tone = np.sin(2 * np.pi * rnd.uniform(1800, 2600) * np.arange(length) / sr) * env * 0.08
        i = int(kt * sr)
        audio[i:i + length] += (click + tone)[: max(0, n - i)]
    # мягкий «дзынь» при выводе результата
    for k, ot in enumerate(T_OUT):
        length = int(0.5 * sr)
        tt = np.arange(length) / sr
        f = [880, 1108.7, 1318.5][k]
        ding = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 7) * 0.22
        i = int(ot * sr)
        audio[i:i + length] += ding[: max(0, n - i)]
    audio = np.clip(audio, -1, 1)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((audio * 32767).astype(np.int16).tobytes())


def main():
    out_silent = os.path.join(HERE, "python_for_loop_silent.mp4")
    out = os.path.join(HERE, "python_for_loop.mp4")
    wav = os.path.join(HERE, "_clicks.wav")
    frames = int(DURATION * FPS)
    print(f"Длительность {DURATION:.1f} c, кадров {frames}")

    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
         "-movflags", "+faststart", out_silent],
        stdin=subprocess.PIPE,
    )
    for f in range(frames):
        ff.stdin.write(render_frame(f / FPS).tobytes())
        if f % 60 == 0:
            print(f"  кадр {f}/{frames}")
    ff.stdin.close()
    ff.wait()

    make_audio(wav)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", out_silent, "-i", wav,
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", out],
        check=True,
    )
    os.remove(wav)
    print("Готово:", out)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        for sec in sys.argv[2:]:
            render_frame(float(sec)).save(os.path.join(HERE, f"_preview_{sec}.png"))
    else:
        main()
