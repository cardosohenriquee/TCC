from __future__ import annotations

import soundfile as sf

from config import COST_PER_HOUR_USD, WHISPER_COST_PER_MINUTE_USD


def get_audio_duration_seconds(file_path: str) -> float:
    info = sf.info(file_path)
    return info.duration


def compute_cost(model: str, duration_seconds: float) -> float:
    if model == "whisper":
        minutes = duration_seconds / 60.0
        return minutes * WHISPER_COST_PER_MINUTE_USD
    hours = duration_seconds / 3600.0
    return hours * COST_PER_HOUR_USD[model]
