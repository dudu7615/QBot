"""
HermesWss — QQ Bot WebSocket 客户端模块。

基于 QQ Bot API v2 WebSocket Gateway 协议，替代官方回调方式。
提供长连接消息接收、自动重连、消息发送、富媒体、键盘按钮等完整功能。

从 Hermes Agent 的 gateway/platforms/qqbot/ 移植，所有数据类型已迁移为 Pydantic。

使用方式：
    from modules.HermesWss import QQWebSocketClient, QQMessageSender

    async def on_message(msg: QQMessage) -> None:
        print(f"收到消息: {msg.content}")

    client = QQWebSocketClient("app_id", "client_secret", on_message=on_message)
    await client.start()
"""

from __future__ import annotations

from .constants import (
    API_BASE,
    HERMESWSS_VERSION,
    MAX_MESSAGE_LENGTH,
    MEDIA_TYPE_FILE,
    MEDIA_TYPE_IMAGE,
    MEDIA_TYPE_VIDEO,
    MEDIA_TYPE_VOICE,
    MSG_TYPE_INPUT_NOTIFY,
    MSG_TYPE_MARKDOWN,
    MSG_TYPE_MEDIA,
    MSG_TYPE_TEXT,
    RECONNECT_BACKOFF,
    TOKEN_URL,
    WSOpCode,
    WSCloseCode,
)
from .crypto import decrypt_secret, generate_bind_key
from .exceptions import (
    HermesWssError,
    QQApiError,
    QQBindError,
    QQBindTaskError,
    QQCloseError,
    QQGatewayError,
    QQTokenError,
    UploadDailyLimitExceededError,
    UploadError,
    UploadFileTooLargeError,
)
from .keyboards import (
    build_approval_keyboard,
    build_approval_text,
    build_update_prompt_keyboard,
    parse_approval_button_data,
    parse_interaction_event,
    parse_update_prompt_button_data,
)
from .models import (
    AccessTokenData,
    ApprovalRequest,
    BindResult,
    BindStatusEnum,
    ChatTypeEnum,
    GatewayResponse,
    InlineKeyboard,
    InteractionEvent,
    KeyboardButton,
    KeyboardButtonAction,
    KeyboardButtonPermission,
    KeyboardButtonRenderData,
    KeyboardContent,
    KeyboardRow,
    OnMessageCallback,
    OnInteractionCallback,
    QQBotConfig,
    QQMessage,
    QQMessageAuthor,
    SendResult,
    TokenResponse,
    UploadCompleteResponse,
    UploadPartFinishResponse,
    UploadPrepareResponse,
    WSPayload,
)
from .onboard import build_connect_url, qr_register
from .sender import QQMessageSender
from .token_manager import TokenManager
from .utils import build_user_agent, coerce_list, get_api_headers
from .wss_client import QQWebSocketClient

__all__ = [
    # 版本
    "HERMESWSS_VERSION",
    # 主类
    "QQWebSocketClient",
    "QQMessageSender",
    "TokenManager",
    # 常量
    "API_BASE",
    "TOKEN_URL",
    "MAX_MESSAGE_LENGTH",
    "WSOpCode",
    "WSCloseCode",
    "MSG_TYPE_TEXT",
    "MSG_TYPE_MARKDOWN",
    "MSG_TYPE_MEDIA",
    "MSG_TYPE_INPUT_NOTIFY",
    "MEDIA_TYPE_IMAGE",
    "MEDIA_TYPE_VOICE",
    "MEDIA_TYPE_VIDEO",
    "MEDIA_TYPE_FILE",
    "RECONNECT_BACKOFF",
    # 模型
    "QQBotConfig",
    "QQMessage",
    "QQMessageAuthor",
    "SendResult",
    "AccessTokenData",
    "TokenResponse",
    "GatewayResponse",
    "WSPayload",
    "InlineKeyboard",
    "KeyboardButton",
    "KeyboardButtonAction",
    "KeyboardButtonPermission",
    "KeyboardButtonRenderData",
    "KeyboardContent",
    "KeyboardRow",
    "InteractionEvent",
    "ApprovalRequest",
    "ChatTypeEnum",
    "OnMessageCallback",
    "OnInteractionCallback",
    "UploadPrepareResponse",
    "UploadPartFinishResponse",
    "UploadCompleteResponse",
    "BindResult",
    "BindStatusEnum",
    # 键盘
    "build_approval_keyboard",
    "build_update_prompt_keyboard",
    "build_approval_text",
    "parse_approval_button_data",
    "parse_update_prompt_button_data",
    "parse_interaction_event",
    # 配网
    "qr_register",
    "build_connect_url",
    # 加密
    "decrypt_secret",
    "generate_bind_key",
    # 工具
    "build_user_agent",
    "get_api_headers",
    "coerce_list",
    # 异常
    "HermesWssError",
    "QQCloseError",
    "QQTokenError",
    "QQApiError",
    "QQGatewayError",
    "QQBindError",
    "QQBindTaskError",
    "UploadError",
    "UploadDailyLimitExceededError",
    "UploadFileTooLargeError",
]
