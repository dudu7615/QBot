"""AiChat 插件配置。"""

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator
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

    # 校验失败时不要把整份配置（含 apiKey）写进异常信息
    model_config = ConfigDict(hide_input_in_errors=True)

    apiKey: str
    url: str
    model: str
    personality: str
    max_context_length: int
    keep_recent: int

    @model_validator(mode="after")
    def _check_window(self) -> "Config":
        """校验上下文窗口配置合理。

        Returns:
            校验通过的自身。

        Raises:
            ValueError: keep_recent 必须 >= 1 且不超过 max_context_length。
        """
        if self.keep_recent < 1 or self.keep_recent > self.max_context_length:
            raise ValueError(
                "keep_recent 必须满足 1 <= keep_recent <= max_context_length"
            )
        return self


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
