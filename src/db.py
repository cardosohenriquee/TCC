from __future__ import annotations

import contextlib
from typing import Generator, Optional

import mysql.connector
from mysql.connector.connection import MySQLConnection

from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


def get_connection() -> MySQLConnection:
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        charset="utf8mb4",
        autocommit=False,
    )


@contextlib.contextmanager
def connection() -> Generator[MySQLConnection, None, None]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def drop_and_recreate_tables() -> None:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("DROP TABLE IF EXISTS results_aggregated")
        cursor.execute("DROP TABLE IF EXISTS transcriptions")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        cursor.close()
    create_tables()


def create_tables() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS transcriptions (
        id              BIGINT AUTO_INCREMENT PRIMARY KEY,
        audio_sample_id BIGINT NOT NULL,
        model           ENUM('azure', 'google', 'whisper') NOT NULL,
        run_index       TINYINT NOT NULL,
        transcription   LONGTEXT,
        wer             FLOAT,
        cer             FLOAT,
        latency_ms      INT,
        cost_usd        DECIMAL(10,6),
        error_message   TEXT,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (audio_sample_id) REFERENCES audio_samples(id)
    );

    CREATE TABLE IF NOT EXISTS results_aggregated (
        id              BIGINT AUTO_INCREMENT PRIMARY KEY,
        audio_sample_id BIGINT NOT NULL,
        model           ENUM('azure', 'google', 'whisper') NOT NULL,
        wer_mean        FLOAT,
        wer_std         FLOAT,
        cer_mean        FLOAT,
        cer_std         FLOAT,
        latency_mean_ms FLOAT,
        latency_std_ms  FLOAT,
        total_cost_usd  DECIMAL(10,6),
        runs_completed  TINYINT DEFAULT 0,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_audio_model (audio_sample_id, model),
        FOREIGN KEY (audio_sample_id) REFERENCES audio_samples(id)
    );
    """
    with connection() as conn:
        cursor = conn.cursor()
        for statement in ddl.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                cursor.execute(stmt)
        cursor.close()


def fetch_audio_samples() -> list[dict]:
    sql = """
        SELECT id, filename, file_path, reference_text
        FROM audio_samples
        ORDER BY id
    """
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        rows = cursor.fetchall()
        cursor.close()
    return rows


def run_exists(audio_sample_id: int, model: str, run_index: int) -> bool:
    sql = """
        SELECT 1 FROM transcriptions
        WHERE audio_sample_id = %s AND model = %s AND run_index = %s
          AND error_message IS NULL
        LIMIT 1
    """
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (audio_sample_id, model, run_index))
        exists = cursor.fetchone() is not None
        cursor.close()
    return exists


def insert_transcription(
    audio_sample_id: int,
    model: str,
    run_index: int,
    transcription: Optional[str],
    wer: Optional[float],
    cer: Optional[float],
    latency_ms: Optional[int],
    cost_usd: Optional[float],
    error_message: Optional[str] = None,
) -> int:
    sql = """
        INSERT INTO transcriptions
            (audio_sample_id, model, run_index, transcription, wer, cer,
             latency_ms, cost_usd, error_message)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (
            audio_sample_id, model, run_index, transcription,
            wer, cer, latency_ms, cost_usd, error_message,
        ))
        row_id = cursor.lastrowid
        cursor.close()
    return row_id


def upsert_aggregated(
    audio_sample_id: int,
    model: str,
    wer_mean: float,
    wer_std: float,
    cer_mean: float,
    cer_std: float,
    latency_mean_ms: float,
    latency_std_ms: float,
    total_cost_usd: float,
    runs_completed: int,
) -> None:
    sql = """
        INSERT INTO results_aggregated
            (audio_sample_id, model, wer_mean, wer_std, cer_mean, cer_std,
             latency_mean_ms, latency_std_ms, total_cost_usd, runs_completed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            wer_mean        = VALUES(wer_mean),
            wer_std         = VALUES(wer_std),
            cer_mean        = VALUES(cer_mean),
            cer_std         = VALUES(cer_std),
            latency_mean_ms = VALUES(latency_mean_ms),
            latency_std_ms  = VALUES(latency_std_ms),
            total_cost_usd  = VALUES(total_cost_usd),
            runs_completed  = VALUES(runs_completed)
    """
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, (
            audio_sample_id, model,
            wer_mean, wer_std, cer_mean, cer_std,
            latency_mean_ms, latency_std_ms, total_cost_usd, runs_completed,
        ))
        cursor.close()


def fetch_transcriptions_for_audio_model(
    audio_sample_id: int, model: str
) -> list[dict]:
    sql = """
        SELECT run_index, wer, cer, latency_ms, cost_usd
        FROM transcriptions
        WHERE audio_sample_id = %s AND model = %s AND error_message IS NULL
        ORDER BY run_index
    """
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, (audio_sample_id, model))
        rows = cursor.fetchall()
        cursor.close()
    return rows


def fetch_all_aggregated() -> list[dict]:
    sql = """
        SELECT model, wer_mean, wer_std, cer_mean, cer_std,
               latency_mean_ms, latency_std_ms, total_cost_usd, runs_completed
        FROM results_aggregated
        ORDER BY model
    """
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql)
        rows = cursor.fetchall()
        cursor.close()
    return rows
