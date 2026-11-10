"""AiChat 插件配置。"""

from pydantic import BaseModel, ValidationError
import yaml  # type: ignore[import-untyped]

from modules.Logger import logger
from plugin.AiChat_d import Paths


class Config(BaseModel):
    """AiChat 插件配置。

    Attributes:
        apiKey: LLM 接口密钥。
        url: OpenAI 兼容接口地址。
        model: 模型名。
        personality: 人设文件名（位于 data/personality 下）。
        max_context_length: 超过该消息数时触发上下文截断。
        keep_recent: 截断后保留的最新消息数（含 system prompt）。
    """

    apiKey: str
    url: str
    model: str
    personality: str
    max_context_length: int
    keep_recent: int


def _load_config() -> Config:
    """读取并校验插件配置。

    Returns:
        校验后的配置对象。

    Raises:
        SystemExit: 文件缺失或内容不合法。
    """
    try:
        with open(Paths.CONFIG_FILE, "r", encoding="utf-8") as file:
            raw: object = yaml.safe_load(file)
    except FileNotFoundError:
        logger.error(f"配置文件不存在: {Paths.CONFIG_FILE}")
        raise SystemExit(1)

    try:
        return Config.model_validate(raw)
    except ValidationError as exc:
        logger.error(f"AiChat 配置不合法: {Paths.CONFIG_FILE}\n{exc}")
        raise SystemExit(1)


config: Config = _load_config()
