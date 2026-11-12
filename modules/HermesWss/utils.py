"""
HermesWss — 工具函数（User-Agent、HTTP 头、配置辅助）。

从 Hermes Agent 的 gateway/platforms/qqbot/utils.py 移植。
"""

from __future__ import annotations

import platform
import sys

from .constants import HERMESWSS_VERSION


def _get_package_version() -> str:
    """尝试从包元数据获取版本号，失败返回 'dev'。"""
    try:
        from importlib.metadata import version
        return version("QBot")
    except Exception:
        return "dev"


def build_user_agent() -> str:
    """构建 User-Agent 字符串。

    格式::

        HermesWss/<qqbot_version> (Python/<py_version>; <os>; QBot/<qbot_version>)
    """
    py_version: str = (
        f"{sys.version_info.major}.{sys.version_info.minor}"
        f".{sys.version_info.micro}"
    )
    os_name: str = platform.system().lower()
    qbot_version: str = _get_package_version()
    return (
        f"HermesWss/{HERMESWSS_VERSION}"
        f" (Python/{py_version}; {os_name}; QBot/{qbot_version})"
    )


def get_api_headers() -> dict[str, str]:
    """返回 QQ Bot API 请求的标准 HTTP 头。

    包含 Content-Type、Accept 和 User-Agent。
    ``q.qq.com`` 要求 ``Accept: application/json``，否则返回 JS 反爬页面。
    """
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": build_user_agent(),
    }
