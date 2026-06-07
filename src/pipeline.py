from __future__ import annotations

import logging
import statistics
import sys
import time
from typing import Callable

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from tqdm import tqdm

import db
from config import NUM_RUNS
from cost import compute_cost, get_audio_duration_seconds
from metrics import compute_wer, compute_cer
from transcribe import azure_stt, google_stt, whisper_stt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

MODELS: dict[str, Callable[[str], tuple[str, int]]] = {
    "azure": azure_stt.transcribe,
    "google": google_stt.transcribe,
    "whisper": whisper_stt.transcribe,
}

_SLEEP_BETWEEN_RUNS: dict[str, float] = {
    "azure": 0.5,
    "google": 0.5,
    "whisper": 1.0,
}


def _make_retry_transcribe(fn: Callable, model: str):
    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _call(file_path: str) -> tuple[str, int]:
        return fn(file_path)

    return _call


def _aggregate_and_save(audio_sample_id: int, model: str) -> None:
    rows = db.fetch_transcriptions_for_audio_model(audio_sample_id, model)
    if not rows:
        return

    wer_vals = [r["wer"] for r in rows if r["wer"] is not None]
    cer_vals = [r["cer"] for r in rows if r["cer"] is not None]
    lat_vals = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    cost_vals = [float(r["cost_usd"]) for r in rows if r["cost_usd"] is not None]

    def _std(vals: list) -> float:
        return statistics.stdev(vals) if len(vals) > 1 else 0.0

    db.upsert_aggregated(
        audio_sample_id=audio_sample_id,
        model=model,
        wer_mean=statistics.mean(wer_vals) if wer_vals else 0.0,
        wer_std=_std(wer_vals),
        cer_mean=statistics.mean(cer_vals) if cer_vals else 0.0,
        cer_std=_std(cer_vals),
        latency_mean_ms=statistics.mean(lat_vals) if lat_vals else 0.0,
        latency_std_ms=_std(lat_vals),
        total_cost_usd=sum(cost_vals),
        runs_completed=len(rows),
    )


def run(
    models: list[str] | None = None,
    audio_ids: list[int] | None = None,
    num_runs: int = NUM_RUNS,
    full: bool = False,
) -> None:
    if full:
        log.warning("--full ativado: dropando e recriando tabelas...")
        db.drop_and_recreate_tables()
        log.info("Tabelas recriadas.")
    else:
        db.create_tables()

    selected_models = models or list(MODELS.keys())
    audio_samples = db.fetch_audio_samples()

    if audio_ids:
        audio_samples = [a for a in audio_samples if a["id"] in audio_ids]

    if not audio_samples:
        log.warning("Nenhum áudio encontrado. Verifique a tabela audio_samples.")
        return

    total = len(audio_samples) * len(selected_models) * num_runs
    log.info(
        "Iniciando pipeline: %d áudios × %d modelos × %d runs = %d transcrições",
        len(audio_samples),
        len(selected_models),
        num_runs,
        total,
    )

    with tqdm(total=total, unit="run") as pbar:
        for sample in audio_samples:
            audio_id: int = sample["id"]
            file_path: str = sample["file_path"]
            reference: str = sample["reference_text"] or ""

            try:
                duration_s = get_audio_duration_seconds(file_path)
            except Exception as exc:
                log.error("Falha ao ler duração de %s: %s", file_path, exc)
                duration_s = 0.0

            for model_name in selected_models:
                fn = _make_retry_transcribe(MODELS[model_name], model_name)
                sleep_s = _SLEEP_BETWEEN_RUNS[model_name]

                for run_idx in range(1, num_runs + 1):
                    pbar.set_description(
                        f"[{model_name}] {sample['filename']} run {run_idx}"
                    )

                    if db.run_exists(audio_id, model_name, run_idx):
                        log.debug(
                            "Já existe: audio=%d model=%s run=%d — pulando.",
                            audio_id, model_name, run_idx,
                        )
                        pbar.update(1)
                        continue

                    transcription = None
                    wer = cer = latency_ms = cost_usd = None
                    error_message = None

                    try:
                        transcription, latency_ms = fn(file_path)
                        wer = compute_wer(reference, transcription)
                        cer = compute_cer(reference, transcription)
                        cost_usd = compute_cost(model_name, duration_s)
                    except Exception as exc:
                        error_message = str(exc)
                        log.error(
                            "Erro [%s] audio=%d run=%d: %s",
                            model_name, audio_id, run_idx, exc,
                        )

                    db.insert_transcription(
                        audio_sample_id=audio_id,
                        model=model_name,
                        run_index=run_idx,
                        transcription=transcription,
                        wer=wer,
                        cer=cer,
                        latency_ms=latency_ms,
                        cost_usd=cost_usd,
                        error_message=error_message,
                    )

                    pbar.update(1)
                    time.sleep(sleep_s)

                _aggregate_and_save(audio_id, model_name)

    log.info("Pipeline concluído.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pipeline ASR TCC")
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(MODELS.keys()),
        default=None,
        help="Modelos a executar (padrão: todos)",
    )
    parser.add_argument(
        "--audio-ids",
        nargs="+",
        type=int,
        default=None,
        help="IDs de audio_samples a processar (padrão: todos)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=NUM_RUNS,
        help=f"Número de runs por áudio×modelo (padrão: {NUM_RUNS})",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="Dropa e recria as tabelas antes de executar (apaga todos os dados)",
    )
    args = parser.parse_args()
    run(models=args.models, audio_ids=args.audio_ids, num_runs=args.runs, full=args.full)
