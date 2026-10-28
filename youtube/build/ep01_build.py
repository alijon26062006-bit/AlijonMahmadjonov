"""Сборка таймингов и звуковой дорожки урока 1.

Берёт сценарий (ep01_script.py) и озвучку (ep01_voice.json — ссылки и длительности
реплик). Если файлы голоса скачаны в public/ep01/voice/NN.wav, длительности берутся
из них и голос попадает в дорожку; иначе дорожка собирается без голоса (для превью).

Пишет src/data/ep01.json и public/ep01/soundtrack.wav.
Скачать голос (там, где сервер Higgsfield доступен): python3 build/ep01_build.py --download
"""

import json
import os
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import audio_fx as A  # noqa: E402
from ep01_script import SCENES  # noqa: E402

SR = A.SR
LEAD, GAP, TAIL = 0.9, 0.6, 1.4
VOICE_DIR = os.path.join(ROOT, "public", "ep01", "voice")

# звук для события: имя -> (эффект, громкость)
SFX = {}
for k in ("click_browser", "click_address", "click_download", "click_file", "click_check", "click_install",
          "ext_click", "click_run", "click_dl", "menu_file", "menu_open", "next", "install", "accept",
          "start_open", "start_pick", "addr_click", "chk1", "chk2", "chk3", "chk4"):
    SFX[k] = ("key", 0.9)
for k in ("window", "card1", "card2", "card3", "u1", "u2", "u3", "u4", "r1", "r2", "r3", "r4", "e1", "e2", "e3",
          "lbl_files", "lbl_code", "lbl_term", "lbl_bar", "feat1", "feat2", "feat3", "way1", "way2", "way3",
          "mouse", "text", "uses", "hw", "lang", "flow", "ver", "notepad", "editor", "vscode", "site", "wizard",
          "tasks", "folder", "new_file", "run_open", "folder_open", "hl_path", "hl_cursor", "term_open", "why"):
    SFX[k] = ("pop_soft", 0.8)
for k in ("warn", "callout", "path_card", "err_card", "repl_card", "ext_card", "py_card", "print_card", "interp",
          "calm", "ver_new", "term_hint", "keys"):
    SFX[k] = ("pop", 0.7)
for k in ("success", "congrats", "ext_install", "done", "opened", "download_done"):
    SFX[k] = ("chime", 1.0)
for k in ("output", "demo_out", "sum_out", "hello_out", "term_out", "prompt", "exit_out"):
    SFX[k] = ("pop", 0.6)
for k in ("enter_url", "enter_cmd", "py_enter", "run_enter", "addr_enter", "save"):
    SFX[k] = ("enter", 0.9)
for k in ("zoom_in", "zoom_out"):
    SFX[k] = ("whoosh", 0.45)


def load_wav(path):
    with wave.open(path) as wf:
        sr, ch, sw = wf.getframerate(), wf.getnchannels(), wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())
    dt = {2: np.int16, 4: np.int32}[sw]
    data = np.frombuffer(raw, dtype=dt).astype(np.float32) / float(np.iinfo(dt).max)
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    n = int(len(data) * SR / sr)
    return np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data).astype(np.float32)


def download(manifest):
    os.makedirs(VOICE_DIR, exist_ok=True)
    for i, v in manifest["lines"].items():
        out = os.path.join(VOICE_DIR, f"{int(i):02d}.wav")
        if not os.path.exists(out):
            subprocess.run(["curl", "-sSfL", "-o", out, v["url"]], check=True)
    print("голос скачан:", len(manifest["lines"]))


def main():
    manifest = json.load(open(os.path.join(HERE, "ep01_voice.json")))
    if "--download" in sys.argv:
        download(manifest)
    t = 0.0
    li = 0
    voices, sfx, scenes = [], [], []
    have_voice = True
    for sc in SCENES:
        start = t
        cur = start + LEAD
        lines = []
        for text in sc["lines"]:
            path = os.path.join(VOICE_DIR, f"{li:02d}.wav")
            if os.path.exists(path):
                v = load_wav(path)
                v = v / (np.max(np.abs(v)) or 1) * 0.9
                dur = len(v) / SR
                voices.append((cur, v))
            else:
                have_voice = False
                dur = manifest["lines"][str(li)]["dur"]
            lines.append({"start": round(cur - start, 3), "dur": round(dur, 3), "text": text})
            cur += dur + GAP
            li += 1

        def at(line_i, anchor):
            ln = lines[line_i]
            if isinstance(anchor, (int, float)):
                return ln["start"] + anchor
            pos = ln["text"].find(anchor)
            if pos < 0:
                raise ValueError(f"{sc['id']}: якорь «{anchor}» не найден")
            return ln["start"] + ln["dur"] * pos / len(ln["text"])

        ev = {}
        last = 0.0
        for e in sc["ev"]:
            name = e[0]
            et = round(at(e[1], e[2]), 3)
            if name.startswith("type:"):
                text, cps = e[3], e[4]
                times = [round(et + (i + 1) / cps, 3) for i in range(len(text))]
                ev[name] = {"t": et, "text": text, "times": times}
                for tt, ch in zip(times, text):
                    sfx.append((start + tt, "space" if ch == " " else "key", 0.55))
                last = max(last, times[-1])
                continue
            ev[name] = et
            last = max(last, et)
            if name in SFX:
                snd, vol = SFX[name]
                sfx.append((start + et, snd, vol))
        dur = round(max(cur - GAP - start, last + 1.2) + TAIL, 3)
        scenes.append({"id": sc["id"], "start": round(start, 3), "dur": dur, "lines": lines, "ev": ev})
        sfx.append((start + 0.02, "whoosh", 0.3))
        t = start + dur
    total = round(t + 0.6, 3)

    os.makedirs(os.path.join(ROOT, "src", "data"), exist_ok=True)
    with open(os.path.join(ROOT, "src", "data", "ep01.json"), "w") as f:
        json.dump({"total": total, "scenes": scenes}, f, ensure_ascii=False, indent=1)

    n = int((total + 0.5) * SR)
    voice = np.zeros(n, dtype=np.float32)
    for t0, v in voices:
        i = int(t0 * SR)
        voice[i:i + len(v)] += v[: n - i]
    mix = voice.copy()
    rng = np.random.default_rng(1)
    for t0, kind, vol in sfx:
        s = A.sfx_sound(kind, rng).astype(np.float32) * vol * 0.8
        i = int(t0 * SR)
        if i < n:
            mix[i:i + len(s)] += s[: n - i]
    bed = A.music_bed(n)
    win = int(0.3 * SR)
    env = np.convolve(np.abs(voice), np.ones(win) / win, mode="same")
    mix += bed * 0.7 * (1 - 0.65 * np.clip(env / 0.04, 0, 1))
    mix = mix / (np.max(np.abs(mix)) or 1) * 0.89
    os.makedirs(os.path.join(ROOT, "public", "ep01"), exist_ok=True)
    with wave.open(os.path.join(ROOT, "public", "ep01", "soundtrack.wav"), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((mix * 32767).astype(np.int16).tobytes())

    print(f"{total:.1f} c ({total / 60:.1f} мин), сцен {len(scenes)}, голос: {'да' if have_voice else 'нет (превью)'}")
    for s in scenes:
        print(f"  {s['id']:10s} {s['start']:7.1f} +{s['dur']:.1f}")


if __name__ == "__main__":
    main()
