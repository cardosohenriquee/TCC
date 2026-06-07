from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

import db
from config import RESULTS_DIR

MODELS = ["azure", "google", "whisper"]


def _build_per_audio_df() -> pd.DataFrame:
    rows = []
    for sample in db.fetch_audio_samples():
        audio_id = sample["id"]
        filename = sample["filename"]
        for model in MODELS:
            data = db.fetch_transcriptions_for_audio_model(audio_id, model)
            if not data:
                continue
            wer_vals = [r["wer"] for r in data if r["wer"] is not None]
            cer_vals = [r["cer"] for r in data if r["cer"] is not None]
            lat_vals = [r["latency_ms"] for r in data if r["latency_ms"] is not None]
            cost_vals = [float(r["cost_usd"]) for r in data if r["cost_usd"] is not None]

            import statistics

            def _mean(v):
                return statistics.mean(v) if v else None

            def _std(v):
                return statistics.stdev(v) if len(v) > 1 else 0.0

            rows.append({
                "filename": filename,
                "audio_sample_id": audio_id,
                "model": model,
                "runs": len(data),
                "wer_mean": _mean(wer_vals),
                "wer_std": _std(wer_vals),
                "cer_mean": _mean(cer_vals),
                "cer_std": _std(cer_vals),
                "latency_mean_ms": _mean(lat_vals),
                "latency_std_ms": _std(lat_vals),
                "total_cost_usd": sum(cost_vals),
            })
    return pd.DataFrame(rows)


def _build_summary_df() -> pd.DataFrame:
    per_audio = _build_per_audio_df()
    if per_audio.empty:
        return pd.DataFrame()

    rows = []
    for model in MODELS:
        subset = per_audio[per_audio["model"] == model]
        if subset.empty:
            continue
        rows.append({
            "Modelo": model.capitalize(),
            "WER Médio": subset["wer_mean"].mean(),
            "DP WER": subset["wer_mean"].std(),
            "CER Médio": subset["cer_mean"].mean(),
            "DP CER": subset["cer_mean"].std(),
            "Custo Total (USD)": subset["total_cost_usd"].sum(),
        })
    return pd.DataFrame(rows)


def generate(export_csv: bool = True) -> pd.DataFrame:
    summary = _build_summary_df()
    if summary.empty:
        print("Nenhum resultado disponível ainda.", file=sys.stderr)
        return summary

    print("\n=== Tabela Final de Resultados ===\n")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    if export_csv:
        per_audio = _build_per_audio_df()
        per_audio_path = RESULTS_DIR / "per_audio.csv"
        summary_path = RESULTS_DIR / "summary.csv"
        per_audio.to_csv(per_audio_path, index=False)
        summary.to_csv(summary_path, index=False)
        print(f"\nCSVs exportados para {RESULTS_DIR}/")

    return summary


if __name__ == "__main__":
    generate()
