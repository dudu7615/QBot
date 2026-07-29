from typing import TypedDict
import yaml
from plugin.AiChat_d import Paths


class Config(TypedDict):
    apiKey: str
    url: str
    model: str
    personality: str
    max_context_length: int  # 超过此消息数时触发上下文截断
    keep_recent: int  # 截断后保留的最新消息数（含 system prompt）


config: Config = yaml.load(
    open(Paths.CONFIG_FILE, "r", encoding="utf8"),
    Loader=yaml.FullLoader,
)
