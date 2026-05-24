from pathlib import Path
import os

APP_NAME = "NickWhispr"
APP_VERSION = "0.2.0"
APP_SUBTITLE = "talk, it types."

DATA_DIR = Path(os.environ.get("APPDATA", "~")) / "WhisprNick"
DB_PATH = DATA_DIR / "whisprnick.db"

MAX_RECORDING_SECONDS = 60
SILENCE_CUTOFF_SECONDS = 3
DEFAULT_HOTKEY = "Ctrl+Shift+Space"

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5:3b"

WHISPER_MODEL = "small"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 760
SIDEBAR_WIDTH = 220
TITLEBAR_HEIGHT = 36
