"""Распознавание голоса без интернета и без платных ключей.

Движок — Vosk: модель лежит файлом на диске, всё считается на месте.
Словарь заранее сужен до числительных (см. numbers.VOCABULARY): бот
слушает только числа, поэтому реже ошибается и не выдумывает слова.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import wave
from io import BytesIO
from pathlib import Path

from .numbers import VOCABULARY

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
_GRAMMAR = json.dumps(list(VOCABULARY) + ["[unk]"], ensure_ascii=False)


class VoiceError(RuntimeError):
    """Не смогли распознать — с готовым текстом для пользователя."""


# ── Звук → сырой PCM ───────────────────────────────────────────────────────
def _decode_with_av(data: bytes) -> bytes:
    import av  # колёса PyAV несут ffmpeg внутри, ставить ничего не надо

    import av.audio.resampler

    buffer = BytesIO(data)
    with av.open(buffer) as container:
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise VoiceError("В файле нет звука.")
        resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        chunks: list[bytes] = []
        for frame in container.decode(stream):
            for resampled in resampler.resample(frame):
                chunks.append(bytes(resampled.planes[0]))
        for resampled in resampler.resample(None):
            chunks.append(bytes(resampled.planes[0]))
    return b"".join(chunks)


def _decode_with_ffmpeg(data: bytes) -> bytes:
    binary = shutil.which("ffmpeg")
    if not binary:
        raise VoiceError(
            "Не получилось раскодировать голосовое.\n"
            "Если так с каждым — переустанови: bash setup-counter.sh"
        )
    process = subprocess.run(
        [binary, "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
         "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "pipe:1"],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    if process.returncode != 0 or not process.stdout:
        raise VoiceError("Не получилось раскодировать голосовое. Запиши ещё раз.")
    return process.stdout


def decode_to_pcm(data: bytes) -> bytes:
    """OGG/Opus (и почти что угодно ещё) → PCM 16 бит, моно, 16 кГц."""
    if not data:
        raise VoiceError("Пустое голосовое.")
    try:
        return _decode_with_av(data)
    except VoiceError:
        raise
    except ImportError:
        pass
    except Exception as exc:  # битый файл — пробуем вторым способом
        log.warning("PyAV не справился (%s), пробую ffmpeg", exc)
    return _decode_with_ffmpeg(data)


def _wav_bytes(pcm: bytes) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm)
    return buffer.getvalue()


# ── Распознавание ──────────────────────────────────────────────────────────
class Recognizer:
    """Ленивая обёртка над Vosk: модель грузится один раз и живёт в памяти."""

    def __init__(self, model_path: str | Path, restrict_to_numbers: bool = True) -> None:
        self.model_path = Path(model_path)
        self.restrict_to_numbers = restrict_to_numbers
        self._model = None
        self._problem: str | None = None
        self._lock = asyncio.Lock()

    # -- состояние ---------------------------------------------------------
    @property
    def ready(self) -> bool:
        return self._model is not None

    @property
    def problem(self) -> str | None:
        return self._problem

    def load(self) -> None:
        """Загрузить модель. Блокирует поток на несколько секунд."""
        if self._model is not None:
            return
        try:
            import vosk
        except ImportError:
            self._problem = (
                "Не установлена библиотека vosk.\n"
                "Поставь её командой:  pip install vosk"
            )
            return
        if not self.model_path.is_dir():
            self._problem = (
                f"Нет голосовой модели в папке {self.model_path}.\n"
                "Скачать её один раз: bash setup-counter.sh"
            )
            return
        try:
            vosk.SetLogLevel(-1)
            self._model = vosk.Model(str(self.model_path))
            self._problem = None
            log.info("Голосовая модель загружена: %s", self.model_path)
        except Exception as exc:  # noqa: BLE001 — покажем причину человеку
            self._problem = f"Не удалось загрузить голосовую модель: {exc}"
            log.exception("Модель не загрузилась")

    async def prepare(self) -> None:
        async with self._lock:
            if self._model is None and self._problem is None:
                await asyncio.to_thread(self.load)

    # -- работа ------------------------------------------------------------
    def _make_kaldi(self):
        import vosk

        if self.restrict_to_numbers:
            try:
                return vosk.KaldiRecognizer(self._model, SAMPLE_RATE, _GRAMMAR)
            except Exception as exc:  # noqa: BLE001
                log.warning("Словарь только из чисел не подошёл модели (%s), слушаю всё", exc)
        return vosk.KaldiRecognizer(self._model, SAMPLE_RATE)

    def recognize_pcm(self, pcm: bytes) -> str:
        if self._model is None:
            self.load()
        if self._model is None:
            raise VoiceError(self._problem or "Голосовой движок не готов.")

        kaldi = self._make_kaldi()
        pieces: list[str] = []
        step = 8000
        for start in range(0, len(pcm), step):
            chunk = pcm[start : start + step]
            if kaldi.AcceptWaveform(chunk):
                pieces.append(json.loads(kaldi.Result()).get("text", ""))
        pieces.append(json.loads(kaldi.FinalResult()).get("text", ""))
        return " ".join(piece for piece in pieces if piece).strip()

    def recognize(self, audio: bytes) -> str:
        return self.recognize_pcm(decode_to_pcm(audio))

    async def recognize_async(self, audio: bytes) -> str:
        await self.prepare()
        return await asyncio.to_thread(self.recognize, audio)


__all__ = ["Recognizer", "VoiceError", "decode_to_pcm", "SAMPLE_RATE", "_wav_bytes"]
