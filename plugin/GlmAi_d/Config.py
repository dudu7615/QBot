from typing import TypedDict
import yaml
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent

class Config(TypedDict):
    apiKey: str

config: Config = yaml.load(
    open(PLUGIN_ROOT / "config.yaml", "r", encoding="utf8"),
    Loader=yaml.FullLoader,
)