from pathlib import Path
from typing import TypedDict
import yaml


class Config(TypedDict):
    appId: str
    clientSecret: str


config: Config = yaml.load(
    open(Path(__file__).parent.parent / "config.yaml", "r", encoding="utf8"),
    Loader=yaml.FullLoader,
)
