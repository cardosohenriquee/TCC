# TCC — Avaliação de Modelos ASR em Português Brasileiro

Pipeline experimental para comparar três serviços de Reconhecimento Automático de Fala (ASR) — **Azure Speech-to-Text**, **Google Speech-to-Text** e **OpenAI Whisper** — sobre o dataset **CORAA ASR**, calculando WER, CER, latência e custo estimado por modelo.

---

## 1. Pré-requisitos

- Python 3.12+
- MySQL Server (local ou acessível na rede) — 8.x recomendado
- Contas ativas e com créditos/billing habilitado em:
  - Microsoft Azure (Cognitive Services — Speech)
  - Google Cloud Platform (Speech-to-Text API)
  - OpenAI (API)

---

## 2. Instalação

```bash
git clone <url-do-repositorio>
cd TCC

python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

---

## 3. Credenciais de API

Todas as credenciais são lidas do arquivo `.env` na raiz do projeto (carregado por `src/config.py`). Esse arquivo **nunca deve ser commitado** (já está no `.gitignore`).

Crie o arquivo `.env` com o seguinte conteúdo:

```dotenv
# Banco de dados MySQL
DB_HOST=localhost
DB_PORT=3306
DB_NAME=tcc_asr
DB_USER=root
DB_PASSWORD=sua_senha

# Azure Speech-to-Text
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=brazilsouth

# Google Cloud Speech-to-Text
GOOGLE_APPLICATION_CREDENTIALS=/home/seu_usuario/TCC/google_credentials.json

# OpenAI Whisper API
OPENAI_API_KEY=
```

### 3.1 Azure Speech-to-Text

1. Acesse o [Portal Azure](https://portal.azure.com).
2. Crie um recurso do tipo **Speech** (Cognitive Services).
3. Escolha a região (ex.: `brazilsouth`) — deve corresponder a `AZURE_SPEECH_REGION`.
4. Em **Keys and Endpoint**, copie a **Key 1** → `AZURE_SPEECH_KEY`.

### 3.2 Google Cloud Speech-to-Text

1. Acesse o [Google Cloud Console](https://console.cloud.google.com).
2. Crie (ou selecione) um projeto e ative a **Cloud Speech-to-Text API**.
3. Vá em **IAM & Admin → Service Accounts**, crie uma service account com o papel `Cloud Speech Client` (ou `Editor`).
4. Gere uma chave em formato **JSON** e salve-a como `google_credentials.json` na raiz do projeto (também ignorado pelo git).
5. Aponte `GOOGLE_APPLICATION_CREDENTIALS` para o caminho absoluto desse arquivo.

### 3.3 OpenAI (Whisper API)

1. Acesse [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
2. Gere uma nova chave secreta → `OPENAI_API_KEY`.
3. Garanta que a conta tenha billing/créditos ativos (a API do Whisper é paga por minuto de áudio).

---

## 4. Banco de dados local

O projeto usa MySQL com 3 tabelas: `audio_samples` (deve existir previamente, com os metadados do dataset), `transcriptions` e `results_aggregated` (criadas automaticamente pelo pipeline).

### 4.1 Criar o banco

```sql
CREATE DATABASE tcc_asr CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Use o mesmo nome em `DB_NAME` no `.env`.

### 4.2 Criar a tabela `audio_samples`

Essa tabela precisa ser criada e populada manualmente com os metadados do dataset CORAA ASR (arquivo de áudio local + transcrição de referência):

```sql
CREATE TABLE audio_samples (
  id             BIGINT PRIMARY KEY,
  filename       VARCHAR(255),
  file_path      TEXT,           -- caminho local do áudio, ex: /home/usuario/TCC/data/audio/arquivo.wav
  original_path  TEXT,
  reference_text LONGTEXT,       -- transcrição de referência (ground truth)
  dataset_source VARCHAR(255),
  subcorpus      VARCHAR(100),
  dataset_split  VARCHAR(50),
  category       VARCHAR(100),
  notes          TEXT,
  created_at     DATETIME,
  updated_at     DATETIME
);
```

Popule essa tabela com os áudios selecionados do CORAA ASR, com `file_path` apontando para os arquivos em `data/audio/` (os áudios ficam no filesystem, o banco só guarda o caminho e os metadados).

### 4.3 Criar as tabelas `transcriptions` e `results_aggregated`

Não é obrigatório rodar manualmente: `pipeline.py` chama `db.create_tables()` automaticamente na primeira execução (`CREATE TABLE IF NOT EXISTS`). Caso prefira criar antes, execute o script pronto:

```bash
mysql -u root -p tcc_asr < create_tables.sql
```

### 4.4 Áudios locais

Coloque os arquivos de áudio do dataset em:

```
data/audio/
```

Esse diretório não é versionado (`.gitignore`). O `file_path` cadastrado em `audio_samples` deve apontar para os arquivos nesse diretório.

---

## 5. Executando o pipeline (`pipeline.py`)

O pipeline lê os áudios cadastrados em `audio_samples`, transcreve com cada modelo, calcula WER/CER/latência/custo e grava em `transcriptions`, agregando o resultado em `results_aggregated`. Ele é **idempotente**: se uma run já existe (e não teve erro), ela é pulada.

```bash
cd src
python pipeline.py [opções]
```

### Parâmetros

| Parâmetro | Descrição | Padrão |
|---|---|---|
| `--models` | Lista de modelos a executar (`azure`, `google`, `whisper`) | todos os três |
| `--audio-ids` | Lista de IDs de `audio_samples` a processar | todos os áudios |
| `--runs` | Número de execuções por combinação áudio×modelo | valor de `NUM_RUNS` em `config.py` (padrão `1`) |
| `--full` | **Apaga e recria** `transcriptions` e `results_aggregated` antes de rodar (perde todos os dados já coletados) | desativado |

### Exemplos

```bash
# Rodar tudo (todos os áudios, todos os modelos, NUM_RUNS execuções cada)
python pipeline.py

# Rodar só o Whisper, 5 runs por áudio
python pipeline.py --models whisper --runs 5

# Testar com um subconjunto pequeno (recomendado antes do experimento completo)
python pipeline.py --models azure google whisper --audio-ids 1 2 3 --runs 2

# Rodar apenas alguns modelos em áudios específicos
python pipeline.py --models azure google --audio-ids 10 11 12

# Zerar os dados coletados e recomeçar do zero
python pipeline.py --full
```

> Para o experimento desejado, ajuste `NUM_RUNS = 20` em `src/config.py` ou passe `--runs 20`.

---

## 6. Gerando o relatório final (`report.py`)

Lê os dados agregados de `transcriptions` no MySQL, monta a tabela final (WER médio, DP WER, CER médio, DP CER, custo total por modelo) e exporta CSVs.

```bash
cd src
python report.py
```

Não recebe parâmetros de linha de comando. Ao rodar, ele:

1. Imprime no terminal a tabela resumo por modelo.
2. Exporta dois arquivos para `results/`:
   - `results/per_audio.csv` — métricas por áudio × modelo
   - `results/summary.csv` — resumo agregado por modelo

Se ainda não houver dados em `transcriptions`, o script avisa `"Nenhum resultado disponível ainda."` e não gera CSVs — rode `pipeline.py` primeiro.

---

## 7. Estrutura do projeto

```
TCC/
├── data/audio/               # áudios locais do CORAA ASR (não versionado)
├── src/
│   ├── config.py              # carrega .env e define constantes/custos
│   ├── db.py                  # conexão MySQL e queries
│   ├── metrics.py             # cálculo de WER/CER
│   ├── cost.py                # cálculo de custo por modelo
│   ├── transcribe/
│   │   ├── azure_stt.py
│   │   ├── google_stt.py
│   │   └── whisper_stt.py
│   ├── pipeline.py            # orquestra o experimento
│   └── report.py              # gera a tabela final e os CSVs
├── results/                   # CSVs gerados por report.py
├── create_tables.sql          # DDL de transcriptions e results_aggregated
├── .env                       # credenciais (não versionado)
├── google_credentials.json    # service account do Google (não versionado)
└── requirements.txt
```
