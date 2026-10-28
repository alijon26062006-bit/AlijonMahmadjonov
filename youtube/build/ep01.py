"""Урок 1, часть «Установка Python»: озвучка, тайминги и звуковая дорожка.

Озвучивает каждую фразу, раскладывает фразы и события (клики, печать) по времени
и пишет:
  src/data/ep01.json        — тайминги для Remotion (секунды)
  public/ep01/soundtrack.wav — голос + клики + клавиши + музыка

Запуск: python3 youtube/build/ep01.py
"""

import json
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "..", "reels"))
import engine as E  # noqa: E402

SR = E.SR
LEAD, GAP, TAIL = 0.6, 0.35, 0.9

# Английские слова в озвучке пишем так, как их произносят.
SCENES = [
    {"id": "intro", "lines": [
        "Привет! Это курс Пайтон с нуля.",
        "В первом уроке мы установим Пайтон и редактор кода ви-эс код, и запустим первую программу.",
    ], "ev": [("title", 0, 0.0), ("subtitle", 1, 0.0)]},

    {"id": "plan", "lines": [
        "План простой. Первое — скачать Пайтон с официального сайта.",
        "Второе — установить его на компьютер.",
        "И третье — поставить редактор и написать первую программу.",
    ], "ev": [("card1", 0, 1.0), ("card2", 1, 0.0), ("card3", 2, 0.0)]},

    {"id": "browser", "lines": [
        "Открываем браузер.",
        "В адресной строке пишем: пайтон точка орг.",
        "Это официальный сайт языка. Наводим на кнопку даунлоуд и нажимаем.",
        "Файл установщика скачался. Открываем его.",
    ], "ev": [("move_browser", 0, 0.0), ("click_browser", 0, 0.9), ("window", 0, 1.1),
              ("click_address", 1, 0.2), ("type:url", 1, 0.6, "python.org", 9), ("enter_url", 1, 2.0),
              ("move_download", 2, 1.4), ("click_download", 2, 3.0),
              ("download_done", 3, 0.0), ("move_file", 3, 0.6), ("click_file", 3, 1.6)]},

    {"id": "installer", "lines": [
        "Запустился установщик. Сейчас самый важный момент!",
        "Внизу ставим галочку: эд пайтон точка экзе ту пас.",
        "Без неё компьютер не найдёт Пайтон, и программы не будут запускаться.",
        "Теперь нажимаем инстолл нау.",
    ], "ev": [("zoom_in", 0, 1.8), ("move_check", 1, 0.3), ("click_check", 1, 2.2), ("callout", 1, 2.4),
              ("zoom_out", 2, 2.6), ("move_install", 3, 0.2), ("click_install", 3, 1.3)]},

    {"id": "progress", "lines": [
        "Идёт установка. Обычно это занимает одну-две минуты.",
        "Готово! Сетап воз саксесфул — установка прошла успешно.",
    ], "ev": [("progress", 0, 0.0), ("success", 1, 0.0)]},

    {"id": "terminal", "lines": [
        "Проверим, что всё работает. Открываем командную строку.",
        "Пишем: пайтон, пробел, два дефиса, вёршн, и нажимаем энтер.",
        "Видим версию Пайтона — значит, установка прошла правильно.",
    ], "ev": [("window", 0, 2.0), ("type:cmd", 1, 0.4, "python --version", 7), ("enter_cmd", 1, 3.4),
              ("output", 1, 3.6)]},

    {"id": "outro", "lines": [
        "Отлично, Пайтон установлен! Дальше ставим редактор ви-эс код.",
    ], "ev": [("title", 0, 0.0)]},
]

SFX_FOR = {"click": ("key", 0.9), "window": ("pop_soft", 1.0), "card": ("pop_soft", 1.0),
           "success": ("chime", 1.2), "callout": ("pop", 0.8), "download_done": ("tick", 1.0),
           "zoom_in": ("whoosh", 0.5), "zoom_out": ("whoosh", 0.4), "output": ("pop_soft", 0.8),
           "enter": ("enter", 0.9)}


def main():
    t = 0.0
    voices, sfx, scenes_out = [], [], []
    for sc in SCENES:
        start = t
        cur = start + LEAD
        lines = []
        for text in sc["lines"]:
            v = E.tts(text)
            dur = len(v) / SR
            lines.append({"start": round(cur - start, 3), "dur": round(dur, 3), "text": text})
            voices.append((cur, v))
            cur += dur + GAP
        ev = {}
        for e in sc["ev"]:
            name, li, off = e[0], e[1], e[2]
            et = lines[li]["start"] + off
            if name.startswith("type:"):
                text, cps = e[3], e[4]
                times = [round(et + i / cps, 3) for i in range(1, len(text) + 1)]
                ev[name] = {"t": et, "text": text, "times": times}
                for tt in times:
                    sfx.append((start + tt, "key", 0.6))
                continue
            ev[name] = round(et, 3)
            kind = name if name in SFX_FOR else name.split("_")[0]
            if kind in ("card1", "card2", "card3"):
                kind = "card"
            if kind in SFX_FOR:
                snd, vol = SFX_FOR[kind]
                sfx.append((start + et, snd, vol))
        end_rel = max(cur - GAP - start + TAIL, max([v if isinstance(v, float) else v["times"][-1]
                                                      for v in ev.values()]) + 1.0)
        dur = round(end_rel, 3)
        scenes_out.append({"id": sc["id"], "start": round(start, 3), "dur": dur, "lines": lines, "ev": ev})
        sfx.append((start + 0.02, "whoosh", 0.35))
        t = start + dur
    total = round(t + 0.5, 3)

    # ---- звуковая дорожка ----
    n = int((total + 0.5) * SR)
    voice = np.zeros(n, dtype=np.float32)
    for t0, v in voices:
        i = int(t0 * SR)
        voice[i:i + len(v)] += v[: n - i]
    mix = voice.copy()
    rng = np.random.default_rng(1)
    for t0, kind, vol in sfx:
        s = E.sfx_sound(kind, rng).astype(np.float32) * vol
        i = int(t0 * SR)
        if i < n:
            mix[i:i + len(s)] += s[: n - i]
    bed = E.music_bed(n)
    env = np.convolve(np.abs(voice), np.ones(int(0.3 * SR)) / int(0.3 * SR), mode="same")
    mix += bed * 0.8 * (1 - 0.6 * np.clip(env / 0.05, 0, 1))
    mix = mix / (np.max(np.abs(mix)) or 1) * 0.89
    os.makedirs(os.path.join(ROOT, "public", "ep01"), exist_ok=True)
    with wave.open(os.path.join(ROOT, "public", "ep01", "soundtrack.wav"), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((mix * 32767).astype(np.int16).tobytes())

    os.makedirs(os.path.join(ROOT, "src", "data"), exist_ok=True)
    with open(os.path.join(ROOT, "src", "data", "ep01.json"), "w") as f:
        json.dump({"total": total, "scenes": scenes_out}, f, ensure_ascii=False, indent=1)
    print(f"Готово: {total:.1f} c, сцен {len(scenes_out)}")
    for s in scenes_out:
        print(f"  {s['id']:10s} {s['start']:6.1f} +{s['dur']:.1f}")


if __name__ == "__main__":
    main()
