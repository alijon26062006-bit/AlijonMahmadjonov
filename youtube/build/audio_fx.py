"""Звуковые эффекты и фоновая музыка (синтез на numpy).

Скопировано из reels/engine.py, чтобы сборка звука не тянула Pillow и шрифты.
"""

import math

import numpy as np

SR = 44100


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
