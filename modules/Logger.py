"""全局日志：统一使用 loguru，并把标准库 logging 桥接到 loguru。"""

import logging
from datetime import datetime
from pathlib import Path

from loguru import logger

__all__ = ["logger"]

ROOT_DIR = Path(__file__).parent.parent
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger.add(
    LOG_DIR / f"{datetime.now().strftime('%y%m%d-%H%M%S')}.log",
    rotation="1 MB",
    compression="zip",
    enqueue=True,
)


class _InterceptHandler(logging.Handler):
    """把标准库 logging 的记录转发给 loguru。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logger.opt(depth=6, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _install_logging_bridge() -> None:
    """接管标准库根 logger，避免第三方库日志散落到 stderr。"""
    logging.basicConfig(handlers=[_InterceptHandler()], level=logging.INFO, force=True)
    for name in ("aiohttp", "httpx", "sqlalchemy"):
        library_logger: logging.Logger = logging.getLogger(name)
        library_logger.handlers = [_InterceptHandler()]
        library_logger.propagate = False


_install_logging_bridge()
