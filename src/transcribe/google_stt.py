from __future__ import annotations

import logging
import time

import soundfile as sf
from google.cloud import speech

log = logging.getLogger(__name__)

_client: speech.SpeechClient | None = None


def _get_client() -> speech.SpeechClient:
    global _client
    if _client is None:
        _client = speech.SpeechClient()
    return _client


def _to_linear16(file_path: str) -> tuple[bytes, int]:
    data, sample_rate = sf.read(file_path, dtype="float64", always_2d=False)
    if data.ndim == 2:
        data = data.mean(axis=1)
    data_i16 = (data * 32767).clip(-32768, 32767).astype("int16")
    return data_i16.tobytes(), sample_rate


def transcribe(file_path: str) -> tuple[str, int]:
    audio_bytes, sample_rate = _to_linear16(file_path)

    audio = speech.RecognitionAudio(content=audio_bytes)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate,
        audio_channel_count=1,
        language_code="pt-BR",
        enable_automatic_punctuation=False,
    )

    client = _get_client()
    t0 = time.monotonic()
    response = client.recognize(config=config, audio=audio)
    latency_ms = int((time.monotonic() - t0) * 1000)

    if not response.results:
        log.warning("Google retornou resultado vazio para: %s", file_path)
        return "", latency_ms

    parts = [result.alternatives[0].transcript for result in response.results]
    return " ".join(parts), latency_ms
