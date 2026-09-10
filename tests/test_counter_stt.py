"""Звук и распознавание: тут проверяем всё, что можно без самой модели."""

from __future__ import annotations

import io
import json
import math

import pytest

from counter.numbers import VOCABULARY
from counter.stt import SAMPLE_RATE, Recognizer, VoiceError, decode_to_pcm


def make_ogg(seconds: float = 1.0, rate: int = 48000) -> bytes:
    """Настоящий OGG/Opus — такой же формат, в каком Телеграм шлёт голосовые."""
    av = pytest.importorskip("av")
    np = pytest.importorskip("numpy")

    buffer = io.BytesIO()
    with av.open(buffer, "w", format="ogg") as out:
        stream = out.add_stream("libopus", rate=rate)
        stream.layout = "mono"
        samples = np.arange(int(rate * seconds), dtype=np.float32)
        tone = (0.3 * np.sin(2 * math.pi * 440 * samples / rate) * 32767).astype(np.int16)
        frame = av.AudioFrame.from_ndarray(tone.reshape(1, -1), format="s16", layout="mono")
        frame.rate = rate
        for packet in stream.encode(frame):
            out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)
    return buffer.getvalue()


def test_decode_gives_mono_16k(monkeypatch):
    pcm = decode_to_pcm(make_ogg(1.0))
    assert len(pcm) % 2 == 0
    seconds = len(pcm) / 2 / SAMPLE_RATE
    assert 0.9 <= seconds <= 2.0        # длительность сохранилась


def test_empty_audio_is_explained():
    with pytest.raises(VoiceError):
        decode_to_pcm(b"")


def test_broken_audio_is_explained():
    with pytest.raises(VoiceError):
        decode_to_pcm("это не звук, а просто байты".encode() * 100)


def test_missing_model_gives_human_advice(tmp_path):
    recognizer = Recognizer(tmp_path / "нет-такой-папки")
    recognizer.load()
    assert not recognizer.ready
    assert "модел" in (recognizer.problem or "").lower()


def test_vocabulary_covers_spoken_numbers():
    """Словарь для Vosk — только числительные, никаких лишних слов."""
    for word in ("семь", "шестьсот", "тысяч", "пять", "yetti", "ming", "yuz"):
        assert word in VOCABULARY
    assert "обувь" not in VOCABULARY
    json.dumps(list(VOCABULARY))        # словарь должен быть сериализуем для Vosk
