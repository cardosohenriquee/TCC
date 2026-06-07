import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

AZURE_SPEECH_KEY = os.environ["AZURE_SPEECH_KEY"]
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "brazilsouth")

GOOGLE_APPLICATION_CREDENTIALS = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

AUDIO_BASE_DIR = Path(__file__).parent.parent / "data" / "audio"
RESULTS_DIR = Path(__file__).parent.parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

NUM_RUNS = 1

COST_PER_HOUR_USD = {
    "azure": 1.00,
    "google": 1.44,
}
WHISPER_COST_PER_MINUTE_USD = 0.006
