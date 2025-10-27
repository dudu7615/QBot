from pathlib import Path

ROOT = Path(__file__).parent
CONFIG_FILE = ROOT / "config.yaml"
DATA = ROOT / "data"
HISTORY = DATA / "history"
PERSONALITY = DATA / "personality"
HISTORY.mkdir(parents=True, exist_ok=True)
PERSONALITY.mkdir(parents=True, exist_ok=True)
