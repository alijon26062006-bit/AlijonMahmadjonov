"""Сборка таймингов и звуковой дорожки урока по сценарию build/<ep>_script.py.

  python3 build/lesson_build.py ep02 --voice piper    черновой голос (бесплатный Piper, локально)
  python3 build/lesson_build.py ep02 --voice openai   живой голос OpenAI (нужен OPENAI_API_KEY и доступ к api.openai.com)
  python3 build/lesson_build.py ep02 --download       живой голос по ссылкам из build/<ep>_voice.json
  python3 build/lesson_build.py ep02                  собрать из уже лежащих public/<ep>/voice/NN.wav

Пишет src/data/<ep>.json и public/<ep>/soundtrack.wav.
"""

import importlib
import json
import os
import re
import subprocess
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import audio_fx as A  # noqa: E402

SR = A.SR
LEAD, GAP, TAIL = 0.9, 0.6, 1.4

# Как читать английские слова черновым русским голосом (живой голос читает их сам).
PIPER_SAY = [("VS Code", "ви-эс код"), ("SyntaxError", "синтакс эррор"), ("NameError", "нейм эррор"),
             ("separator", "сепарэйтор"), ("Print", "Принт"), ("print", "принт"), ("sep", "сэп"),
             ("end", "энд"), ("main", "мэйн"), ("py", "пай"), ("Python", "Пайтон"), ("Enter", "энтер")]


OPENAI_MODEL = "gpt-4o-mini-tts"
OPENAI_VOICE = os.environ.get("OPENAI_TTS_VOICE", "onyx")  # мужские: onyx, ash, echo
OPENAI_STYLE = ("Ты дружелюбный преподаватель программирования на YouTube. Говори по-русски спокойно, "
                "чётко и с живой интонацией, в умеренном темпе. Английские слова и код произноси по-английски.")


def openai_tts(text, out_path):
    """Озвучка одной реплики через OpenAI. Ключ берётся из переменной окружения OPENAI_API_KEY."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("Нет OPENAI_API_KEY в переменных окружения")
    body = json.dumps({"model": OPENAI_MODEL, "voice": OPENAI_VOICE, "input": text,
                       "instructions": OPENAI_STYLE, "response_format": "pcm"})
    pcm = subprocess.run(["curl", "-sSf", "https://api.openai.com/v1/audio/speech",
                          "-H", f"Authorization: Bearer {key}", "-H", "Content-Type: application/json",
                          "--data-binary", "@-"], input=body.encode(), check=True, capture_output=True).stdout
    with wave.open(out_path, "wb") as wf:  # pcm: 24 кГц, 16 бит, моно
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm)


TRIM_AF = ("silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:"
           "stop_duration=0.55:stop_threshold=-42dB:stop_silence=0.45")


def sfx_for(name):
    if name.startswith("run"):
        return [("key", 0.9, 0.0), ("enter", 0.8, 0.05)]
    if re.fullmatch(r"o\d+", name):
        return [("pop_soft", 0.6, 0.0)]
    if re.fullmatch(r"[xe]\d+", name):
        return [("pop", 0.6, 0.0)]
    if re.fullmatch(r"f\d+", name):
        return [("chime", 0.7, 0.0)]
    if re.fullmatch(r"[chrs]\d+", name) or name in ("hw", "next", "sub"):
        return [("pop_soft", 0.7, 0.0)]
    return []


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


def write_wav(path, data):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((np.clip(data, -1, 1) * 32767).astype(np.int16).tobytes())


def main():
    ep = sys.argv[1]
    script = importlib.import_module(f"{ep}_script")
    voice_dir = os.path.join(ROOT, "public", ep, "voice")
    os.makedirs(voice_dir, exist_ok=True)
    lines_all = [t for sc in script.SCENES for t in sc["lines"]]

    if "--voice" in sys.argv and sys.argv[sys.argv.index("--voice") + 1] == "piper":
        sys.path.insert(0, os.path.join(ROOT, "..", "reels"))
        import engine as E  # черновой голос Piper
        for i, text in enumerate(lines_all):
            say = text
            for en, ru in PIPER_SAY:
                say = re.sub(rf"\b{re.escape(en)}\b", ru, say)
            write_wav(os.path.join(voice_dir, f"{i:02d}.wav"), E.tts(say))
    if "--voice" in sys.argv and sys.argv[sys.argv.index("--voice") + 1] == "openai":
        for i, text in enumerate(lines_all):
            openai_tts(text, os.path.join(voice_dir, f"{i:02d}.wav"))
            print(f"  озвучено {i + 1}/{len(lines_all)}", flush=True)
    if "--download" in sys.argv:
        manifest = json.load(open(os.path.join(HERE, f"{ep}_voice.json")))
        for i, v in manifest["lines"].items():
            out = os.path.join(voice_dir, f"{int(i):02d}.wav")
            subprocess.run(["curl", "-sSfL", "-o", out, v["url"]], check=True)
            if manifest.get("trim_pauses"):
                # длинные паузы внутри фразы сокращаем до ~0.5 с, чтобы речь шла живо
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-af", TRIM_AF, "-ar", "44100", "-ac", "1", out + ".t.wav"], check=True)
                os.replace(out + ".t.wav", out)

    mpath = os.path.join(HERE, f"{ep}_voice.json")
    manifest_dur = {k: v["dur"] for k, v in json.load(open(mpath))["lines"].items()} if os.path.exists(mpath) else {}
    t, li = 0.0, 0
    voices, sfx, scenes = [], [], []
    for sc in script.SCENES:
        start = t
        cur = start + LEAD
        lines = []
        for text in sc["lines"]:
            path = os.path.join(voice_dir, f"{li:02d}.wav")
            if os.path.exists(path) and "--manifest-durations" not in sys.argv:
                v = load_wav(path)
                v = v / (np.max(np.abs(v)) or 1) * 0.9
                dur = len(v) / SR
                voices.append((cur, v))
            else:  # голоса нет — длительность из списка озвучки (для превью без звука)
                dur = manifest_dur[str(li)]
            lines.append({"start": round(cur - start, 3), "dur": round(dur, 3), "text": text})
            cur += dur + GAP
            li += 1

        def at(i, anchor):
            ln = lines[i]
            if isinstance(anchor, (int, float)):
                return ln["start"] + anchor
            pos = ln["text"].find(anchor)
            if pos < 0:
                raise ValueError(f"{sc['id']}: якорь «{anchor}» не найден")
            return ln["start"] + ln["dur"] * pos / len(ln["text"])

        ev, last = {}, 0.0
        for e in sc["ev"]:
            name, et = e[0], round(at(e[1], e[2]), 3)
            if name.startswith("type:"):
                text, cps = e[3], e[4]
                times = [round(et + (k + 1) / cps, 3) for k in range(len(text))]
                ev[name] = {"t": et, "text": text, "times": times}
                sfx += [(start + tt, "space" if ch == " " else "key", 0.5) for tt, ch in zip(times, text)]
                last = max(last, times[-1])
                continue
            ev[name] = et
            last = max(last, et)
            sfx += [(start + et + dt, snd, vol) for snd, vol, dt in sfx_for(name)]
        dur = round(max(cur - GAP - start, last + 1.5) + TAIL, 3)
        scenes.append({"id": sc["id"], "kind": sc["kind"], "params": sc.get("params", {}), "start": round(start, 3),
                       "dur": dur, "lines": lines, "ev": ev})
        sfx.append((start + 0.02, "whoosh", 0.3))
        t = start + dur
    total = round(t + 0.6, 3)

    with open(os.path.join(ROOT, "src", "data", f"{ep}.json"), "w") as f:
        json.dump({"episode": script.EPISODE, "total": total, "scenes": scenes}, f, ensure_ascii=False, indent=1)

    n = int((total + 0.5) * SR)
    voice = np.zeros(n, dtype=np.float32)
    for t0, v in voices:
        i = int(t0 * SR)
        voice[i:i + len(v)] += v[: n - i]
    mix = voice.copy()
    rng = np.random.default_rng(2)
    for t0, kind, vol in sfx:
        s = A.sfx_sound(kind, rng).astype(np.float32) * vol * 0.8
        i = int(t0 * SR)
        if i < n:
            mix[i:i + len(s)] += s[: n - i]
    win = int(0.3 * SR)
    env = np.convolve(np.abs(voice), np.ones(win) / win, mode="same")
    mix += A.music_bed(n) * 0.7 * (1 - 0.65 * np.clip(env / 0.04, 0, 1))
    write_wav(os.path.join(ROOT, "public", ep, "soundtrack.wav"), mix / (np.max(np.abs(mix)) or 1) * 0.89)

    print(f"{ep}: {total:.1f} c ({total / 60:.1f} мин), сцен {len(scenes)}")
    for s in scenes:
        print(f"  {s['id']:10s} {s['kind']:7s} {s['start']:7.1f} +{s['dur']:.1f}")


if __name__ == "__main__":
    main()
