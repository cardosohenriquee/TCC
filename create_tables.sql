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
