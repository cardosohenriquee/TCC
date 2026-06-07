from __future__ import annotations

import time

from openai import OpenAI

from config import OPENAI_API_KEY

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def transcribe(file_path: str) -> tuple[str, int]:
    client = _get_client()
    t0 = time.monotonic()
    with open(file_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="pt",
            response_format="text",
        )
    latency_ms = int((time.monotonic() - t0) * 1000)
    return str(response).strip(), latency_ms
