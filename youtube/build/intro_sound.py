"""Звук 5-секундной заставки: вжух, удар, звон, мягкий хвост."""
import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audio_fx as A  # noqa: E402

SR = A.SR
n = int(5.0 * SR)
mix = np.zeros(n, dtype=np.float32)
rng = np.random.default_rng(7)


def put(t, s, vol):
    i = int(t * SR)
    mix[i:i + len(s)] += (s[: n - i] * vol).astype(np.float32)


# удар: низкий «бум» с понижением тона + шумовая атака
L = int(1.6 * SR)
t = np.arange(L) / SR
f = 40 + 90 * np.exp(-t * 9)
boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
hit = A._onepole_lowpass(rng.standard_normal(L), np.full(L, 2500.0)) * np.exp(-t * 30)
# пэд-аккорд, который тянется до конца
P = int(3.6 * SR)
tp = np.arange(P) / SR
pad = sum(np.sin(2 * np.pi * fr * tp) + 0.5 * np.sin(2 * np.pi * fr * 2.003 * tp) for fr in (220.0, 277.18, 329.63, 440.0))
pad *= np.minimum(1, tp / 0.15) * np.exp(-tp * 1.1) * 0.05

put(0.05, A.sfx_sound("whoosh", rng), 0.9)
put(0.55, A.sfx_sound("whoosh", rng), 0.6)
put(1.15, boom, 0.9)
put(1.15, hit, 0.5)
put(1.18, A.sfx_sound("chime", rng), 2.2)
put(1.2, pad, 1.0)
put(1.6, A.sfx_sound("sparkle", rng), 1.6)
put(3.9, A.sfx_sound("whoosh", rng), 0.4)
fade = int(0.4 * SR)
mix[-fade:] *= np.linspace(1, 0, fade)
mix = mix / np.max(np.abs(mix)) * 0.9
with wave.open(os.path.join(os.path.dirname(__file__), "..", "public", "intro", "intro.wav"), "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes((mix * 32767).astype(np.int16).tobytes())
print("ok")
