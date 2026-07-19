from typing import TypedDict
import yaml
from plugin.GlmAi_d import Paths


class Config(TypedDict):
    apiKey: str
    personality: str


config: Config = yaml.load(
    open(Paths.CONFIG_FILE, "r", encoding="utf8"),
    Loader=yaml.FullLoader,
)
