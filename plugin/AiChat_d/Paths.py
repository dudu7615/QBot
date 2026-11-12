from pathlib import Path

ROOT = Path(__file__).parent
CONFIG_FILE = ROOT / "config.yaml"
DATA = ROOT / "data"
PERSONALITY = DATA / "personality"
PERSONALITY.mkdir(parents=True, exist_ok=True)
