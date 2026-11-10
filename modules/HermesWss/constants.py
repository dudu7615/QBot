"""
HermesWss — QQ Bot WebSocket 客户端常量定义。

本模块从 Hermes Agent 的 gateway/platforms/qqbot/constants.py 移植，
所有数据类型已迁移为 Pydantic / IntEnum 并通过 strict mypy 检查。
"""

from __future__ import annotations

import os
from enum import IntEnum

# ---------------------------------------------------------------------------
# 版本
# ---------------------------------------------------------------------------

HERMESWSS_VERSION: str = "1.0.0"

# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

# Portal 域名可通过环境变量覆盖（企业代理 / 测试环境）
PORTAL_HOST: str = os.getenv("QQ_PORTAL_HOST", "q.qq.com")

API_BASE: str = "https://api.sgroup.qq.com"
TOKEN_URL: str = "https://bots.qq.com/app/getAppAccessToken"
GATEWAY_URL_PATH: str = "/gateway"

# QR 扫码配网端点
ONBOARD_CREATE_PATH: str = "/lite/create_bind_task"
ONBOARD_POLL_PATH: str = "/lite/poll_bind_result"
QR_URL_TEMPLATE: str = (
    "https://q.qq.com/qqbot/openclaw/connect.html"
    "?task_id={task_id}&_wv=2&source=hermeswss"
)

# ---------------------------------------------------------------------------
# 超时 & 重试
# ---------------------------------------------------------------------------

DEFAULT_API_TIMEOUT: float = 30.0
FILE_UPLOAD_TIMEOUT: float = 120.0
CONNECT_TIMEOUT_SECONDS: float = 20.0

RECONNECT_BACKOFF: list[float] = [2.0, 5.0, 10.0, 30.0, 60.0]
MAX_RECONNECT_ATTEMPTS: int = 100
RATE_LIMIT_DELAY: float = 60.0
QUICK_DISCONNECT_THRESHOLD: float = 5.0
MAX_QUICK_DISCONNECT_COUNT: int = 3

ONBOARD_POLL_INTERVAL: float = 2.0
ONBOARD_API_TIMEOUT: float = 10.0

# ---------------------------------------------------------------------------
# 消息限制
# ---------------------------------------------------------------------------

MAX_MESSAGE_LENGTH: int = 4000
DEDUP_WINDOW_SECONDS: int = 300
DEDUP_MAX_SIZE: int = 1000

# ---------------------------------------------------------------------------
# QQ Bot 消息类型
# ---------------------------------------------------------------------------

MSG_TYPE_TEXT: int = 0
MSG_TYPE_MARKDOWN: int = 2
MSG_TYPE_MEDIA: int = 7
MSG_TYPE_INPUT_NOTIFY: int = 6

# ---------------------------------------------------------------------------
# QQ Bot 媒体文件类型
# ---------------------------------------------------------------------------

MEDIA_TYPE_IMAGE: int = 1
MEDIA_TYPE_VIDEO: int = 2
MEDIA_TYPE_VOICE: int = 3
MEDIA_TYPE_FILE: int = 4

# ---------------------------------------------------------------------------
# WebSocket OP Code
# ---------------------------------------------------------------------------


class WSOpCode(IntEnum):
    """QQ Bot WebSocket 操作码。"""

    DISPATCH = 0           # 服务端推送事件
    HEARTBEAT = 1          # 客户端心跳
    IDENTIFY = 2           # 客户端鉴权
    RESUME = 6             # 客户端恢复连接
    RECONNECT = 7          # 服务端要求重连
    INVALID_SESSION = 9    # Session 失效
    HELLO = 10             # 服务端 Hello（心跳间隔）
    HEARTBEAT_ACK = 11     # 心跳回包


# ---------------------------------------------------------------------------
# QQ Bot WebSocket 关闭码
# ---------------------------------------------------------------------------


class WSCloseCode(IntEnum):
    """QQ Bot WebSocket 关闭码枚举。"""

    UNKNOWN_ERROR = 4000
    UNKNOWN_OPCODE = 4001
    DECODE_ERROR = 4002
    NOT_AUTHENTICATED = 4003
    AUTHENTICATION_FAILED = 4004
    ALREADY_AUTHENTICATED = 4005
    SESSION_TIMEOUT_EXPIRED = 4006
    INVALID_SEQ = 4007
    RATE_LIMITED = 4008
    SESSION_TIMEOUT = 4009
    INVALID_SHARD = 4010
    SHARDING_REQUIRED = 4011
    INVALID_API_VERSION = 4012
    INVALID_INTENT = 4013
    INTENT_NOT_AUTHORIZED = 4014
    SESSION_INVALID = 4900
    SESSION_EXPIRED = 4901
    SESSION_NOT_FOUND = 4902
    SESSION_CONFLICT = 4903
    SESSION_CLOSED = 4904
    SESSION_RATE_LIMITED = 4905
    SESSION_BLOCKED = 4906
    SESSION_CREATE_FAILED = 4910
    SESSION_JOIN_FAILED = 4911
    SESSION_RESUME_FAILED = 4912
    SESSION_RESUME_INVALID = 4913
    SESSION_TIMED_OUT = 4907
    SESSION_CREATE_RATE_LIMITED = 4908
    BOT_OFFLINE = 4914
    BOT_BANNED = 4915

    @property
    def is_fatal(self) -> bool:
        """是否是不可恢复的致命关闭码。"""
        return self in {
            WSCloseCode.UNKNOWN_OPCODE,
            WSCloseCode.DECODE_ERROR,
            WSCloseCode.INVALID_SHARD,
            WSCloseCode.SHARDING_REQUIRED,
            WSCloseCode.INVALID_API_VERSION,
            WSCloseCode.INVALID_INTENT,
            WSCloseCode.INTENT_NOT_AUTHORIZED,
            WSCloseCode.BOT_OFFLINE,
            WSCloseCode.BOT_BANNED,
        }

    @property
    def is_session_invalid(self) -> bool:
        """是否需要清除 session 重新 identify。"""
        return self in {
            WSCloseCode.SESSION_TIMEOUT_EXPIRED,
            WSCloseCode.INVALID_SEQ,
            WSCloseCode.SESSION_INVALID,
            WSCloseCode.SESSION_EXPIRED,
            WSCloseCode.SESSION_NOT_FOUND,
            WSCloseCode.SESSION_CONFLICT,
            WSCloseCode.SESSION_CLOSED,
            WSCloseCode.SESSION_RATE_LIMITED,
            WSCloseCode.SESSION_BLOCKED,
            WSCloseCode.SESSION_TIMED_OUT,
            WSCloseCode.SESSION_CREATE_FAILED,
            WSCloseCode.SESSION_JOIN_FAILED,
            WSCloseCode.SESSION_RESUME_FAILED,
            WSCloseCode.SESSION_RESUME_INVALID,
        }

    @property
    def description(self) -> str:
        """人类可读的描述。"""
        descriptions: dict[WSCloseCode, str] = {
            WSCloseCode.UNKNOWN_ERROR: "未知错误",
            WSCloseCode.UNKNOWN_OPCODE: "未知 opcode",
            WSCloseCode.DECODE_ERROR: "非法 payload",
            WSCloseCode.NOT_AUTHENTICATED: "未鉴权",
            WSCloseCode.AUTHENTICATION_FAILED: "鉴权失败（token 无效）",
            WSCloseCode.ALREADY_AUTHENTICATED: "重复鉴权",
            WSCloseCode.SESSION_TIMEOUT_EXPIRED: "会话超时",
            WSCloseCode.INVALID_SEQ: "无效 seq",
            WSCloseCode.RATE_LIMITED: "被限流",
            WSCloseCode.SESSION_TIMEOUT: "连接超时",
            WSCloseCode.INVALID_SHARD: "无效的分片信息",
            WSCloseCode.SHARDING_REQUIRED: "需要分片",
            WSCloseCode.INVALID_API_VERSION: "无效 API 版本",
            WSCloseCode.INVALID_INTENT: "无效 intent",
            WSCloseCode.INTENT_NOT_AUTHORIZED: "intent 未授权",
            WSCloseCode.BOT_OFFLINE: "机器人离线/沙箱模式",
            WSCloseCode.BOT_BANNED: "机器人被封禁",
        }
        return descriptions.get(self, f"关闭码 {self.value}")
