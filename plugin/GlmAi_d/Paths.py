from pathlib import Path

ROOT = Path(__file__).parent
CONFIG_FILE = ROOT / "config.yaml"
DATA = ROOT / "data"
HISTORY = DATA / "history"
HISTORY.mkdir(parents=True, exist_ok=True)
