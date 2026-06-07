from __future__ import annotations

import time

import azure.cognitiveservices.speech as speechsdk

from config import AZURE_SPEECH_KEY, AZURE_SPEECH_REGION


def transcribe(file_path: str) -> tuple[str, int]:
    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_SPEECH_KEY,
        region=AZURE_SPEECH_REGION,
    )
    speech_config.speech_recognition_language = "pt-BR"

    audio_config = speechsdk.audio.AudioConfig(filename=file_path)
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    t0 = time.monotonic()
    result = recognizer.recognize_once()
    latency_ms = int((time.monotonic() - t0) * 1000)

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text, latency_ms

    if result.reason == speechsdk.ResultReason.NoMatch:
        raise RuntimeError(f"Azure NoMatch: {result.no_match_details}")

    if result.reason == speechsdk.ResultReason.Canceled:
        details = result.cancellation_details
        raise RuntimeError(
            f"Azure Canceled: {details.reason} — {details.error_details}"
        )

    raise RuntimeError(f"Azure resultado inesperado: {result.reason}")
