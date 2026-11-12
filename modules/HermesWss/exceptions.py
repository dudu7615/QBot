"""
HermesWss — QQ Bot WebSocket 客户端异常定义。

本模块从 Hermes Agent 的 gateway/platforms/qqbot/ 移植，
所有异常均已通过 strict mypy 检查。

与上游差异：
  - 拆分为独立模块
  - 所有异常类添加 type-safe 的字段
  - 移除 Hermes 特有的 _set_fatal_error 耦合
"""

from __future__ import annotations

from typing import Optional


class HermesWssError(Exception):
    """所有 HermesWss 异常的基类。"""


class QQCloseError(HermesWssError):
    """QQ WebSocket 因指定关闭码断开连接。

    Attributes:
        code: 关闭码。
        reason: 关闭原因。
    """

    def __init__(self, code: int | None, reason: str = "") -> None:
        self.code: int | None = int(code) if code is not None else None
        self.reason: str = reason if reason else ""
        super().__init__(f"WebSocket closed (code={self.code}, reason={self.reason})")


class QQBindError(HermesWssError):
    """扫码配网相关错误。"""


class QQTokenError(HermesWssError):
    """Access Token 相关错误。"""


class QQApiError(HermesWssError):
    """QQ Bot REST API 调用错误。

    Attributes:
        status_code: HTTP 状态码。
        body: 响应体文本。
    """

    def __init__(self, status_code: int, body: str, message: str = "") -> None:
        self.status_code: int = status_code
        self.body: str = body
        msg: str = message or f"API error (status={status_code}): {body[:200]}"
        super().__init__(msg)


class QQGatewayError(HermesWssError):
    """获取 Gateway URL 失败。"""


class UploadError(HermesWssError):
    """大文件上传通用错误。"""


class UploadDailyLimitExceededError(UploadError):
    """日上传配额超限（biz_code 40093002）。"""

    def __init__(
        self,
        file_name: str,
        file_size: int,
        message: str = "",
    ) -> None:
        self.file_name: str = file_name
        self.file_size: int = file_size
        msg: str = message or f"Daily upload limit exceeded for {file_name}"
        super().__init__(msg)


class UploadFileTooLargeError(UploadError):
    """文件超过单文件大小上限。

    Attributes:
        file_name: 文件名。
        size: 实际大小（字节）。
        limit: 允许的上限（字节）。
    """

    def __init__(self, file_name: str, size: int, limit: int) -> None:
        self.file_name: str = file_name
        self.size: int = size
        self.limit: int = limit
        super().__init__(
            f"{file_name} 大小 {size} 字节超过上限 {limit} 字节"
        )


class QQBindTaskError(HermesWssError):
    """扫码配网任务相关错误。"""
