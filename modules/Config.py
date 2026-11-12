"""全局配置：读取项目根目录的 config.yaml。"""

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError

from modules.Logger import logger

CONFIG_FILE: Path = Path(__file__).parent.parent / "config.yaml"


class Config(BaseModel):
    """项目配置。

    Attributes:
        appId: QQ Bot 的 app_id。
        clientSecret: QQ Bot 的 client_secret。
    """

    appId: str
    clientSecret: str


def _load_config(path: Path) -> Config:
    """读取并校验配置文件。

    Args:
        path: 配置文件路径。

    Returns:
        校验后的配置对象。

    Raises:
        SystemExit: 文件缺失或内容不合法。
    """
    try:
        with open(path, "r", encoding="utf-8") as file:
            raw: object = yaml.safe_load(file)
    except FileNotFoundError:
        logger.error(f"配置文件不存在: {path}")
        raise SystemExit(1)

    try:
        return Config.model_validate(raw)
    except ValidationError as exc:
        logger.error(f"配置文件缺少必要字段或类型错误: {path}\n{exc}")
        raise SystemExit(1)


config: Config = _load_config(CONFIG_FILE)
