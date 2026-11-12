"""
HermesWss — 全部 Pydantic 数据模型。

从 Hermes Agent 的 gateway/platforms/qqbot/ 移植的所有数据类型，
统一为 Pydantic v2 BaseModel，通过 strict mypy 检查。

包含：WebSocket 消息、配置、发送结果、键盘按钮、审批交互、上传状态等。
"""

from __future__ import annotations

from enum import IntEnum
from typing import Callable, Coroutine

import asyncio
from pydantic import BaseModel, Field

# ======================================================================
# 配置
# ======================================================================


class QQBotConfig(BaseModel):
    """QQ Bot 机器人配置。

    Attributes:
        app_id: 机器人的 app_id（QQ 开放平台获取）。
        client_secret: 机器人的 client_secret（QQ 开放平台获取）。
        markdown_support: 是否启用 Markdown 消息格式。
        dm_policy: 私信策略（open / allowlist / disabled / pairing）。
        group_policy: 群聊策略（open / allowlist / disabled / pairing）。
    """

    app_id: str
    client_secret: str
    markdown_support: bool = False
    dm_policy: str = "open"
    group_policy: str = "open"


# ======================================================================
# Token 相关
# ======================================================================


class TokenResponse(BaseModel):
    """调用 /app/getAppAccessToken 返回的响应体。

    Attributes:
        access_token: Bearer token。
        expires_in: 过期时间（秒，从收到时算起）。
    """

    access_token: str
    expires_in: int


# ======================================================================
# WebSocket 协议
# ======================================================================


class WSPayload(BaseModel):
    """QQ Bot WebSocket 协议帧。

    参考：https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/

    Attributes:
        op: 操作码（见 WSOpCode）。
        d: 事件数据（payload body）。
        s: 序列号（仅 op 0 Dispatch 时存在）。
        t: 事件类型（仅 op 0 Dispatch 时存在，如 C2C_MESSAGE_CREATE）。
        id: 事件 ID（仅 op 0 Dispatch 时存在，用于被动回复）。
    """

    op: int
    d: object | None = None
    s: int | None = None
    t: str | None = None
    id: str | None = None


class GatewayResponse(BaseModel):
    """调用 /gateway 获取的 WebSocket 网关地址。

    Attributes:
        url: WebSocket 网关 URL。
    """

    url: str


# ======================================================================
# 消息相关（接收）
# ======================================================================


class QQMessageAuthor(BaseModel):
    """QQ Bot 消息作者信息。

    Attributes:
        id: 用户 ID。
        user_openid: 用户的 openid（C2C 场景）。
        union_openid: 用户的 union_openid。
        member_openid: 群成员的 openid（群聊场景）。
    """

    id: str | None = None
    user_openid: str | None = None
    union_openid: str | None = None
    member_openid: str | None = None


class QQMessage(BaseModel):
    """QQ Bot 收到的消息统一模型。

    同时支持 C2C 私聊和 GROUP_AT 群 @ 两种场景。
    字段名与 QQ Bot API v2 官方 payload 保持一致。

    Attributes:
        id: 消息 ID（用于去重和回复）。
        content: 消息文本内容。
        timestamp: 消息时间戳字符串。
        author: 发送者信息。
        user_openid: C2C 场景的用户 openid。
        group_openid: 群聊场景的群 openid。
        group_member_openid: 群聊场景的发送者 openid。
        event_type: 事件类型（如 C2C_MESSAGE_CREATE）。
        raw: 原始 payload dict，供高级使用。
    """

    id: str
    content: str = ""
    timestamp: str = ""
    author: QQMessageAuthor | None = None
    user_openid: str | None = None
    group_openid: str | None = None
    group_member_openid: str | None = None
    event_type: str = ""
    event_id: str = ""  # 网关事件 ID，用于被动回复
    raw: dict[str, object] = Field(default_factory=dict)


# ======================================================================
# 发送结果
# ======================================================================


class SendResult(BaseModel):
    """消息发送结果。

    Attributes:
        success: 是否发送成功。
        message_id: 发送成功后的消息 ID。
        error: 错误信息（失败时）。
        retryable: 是否可重试。
        raw_response: API 原始响应。
    """

    success: bool
    message_id: str = ""
    error: str = ""
    retryable: bool = False
    raw_response: dict[str, object] | None = None


# ======================================================================
# 键盘按钮模型
# ======================================================================


class KeyboardButtonPermission(BaseModel):
    """按钮权限元数据。

    Attributes:
        type: 权限类型。2 表示所有用户可点击。
    """

    type: int = 2

    def to_dict(self) -> dict[str, object]:
        """序列化为 API 请求可用的字典。"""
        return {"type": self.type}


class KeyboardButtonAction(BaseModel):
    """按钮点击行为定义。

    Attributes:
        type: 行为类型。1 = Callback（触发 INTERACTION_CREATE），2 = 打开链接。
        data: 点击时携带的数据 payload。
        permission: 点击权限。
        click_limit: 每个用户可点击次数（1 = 单次使用）。
    """

    type: int
    data: str
    permission: KeyboardButtonPermission = Field(default_factory=KeyboardButtonPermission)
    click_limit: int = 1

    def to_dict(self) -> dict[str, object]:
        """序列化为 API 请求可用的字典。"""
        return {
            "type": self.type,
            "data": self.data,
            "permission": self.permission.to_dict(),
            "click_limit": self.click_limit,
        }


class KeyboardButtonRenderData(BaseModel):
    """按钮视觉渲染定义。

    Attributes:
        label: 点击前显示的文本。
        visited_label: 点击后显示的文本。
        style: 0 = 灰色，1 = 蓝色。
    """

    label: str
    visited_label: str
    style: int = 1

    def to_dict(self) -> dict[str, object]:
        """序列化为 API 请求可用的字典。"""
        return {
            "label": self.label,
            "visited_label": self.visited_label,
            "style": self.style,
        }


class KeyboardButton(BaseModel):
    """一个按钮。

    Attributes:
        id: 按钮唯一 ID。
        render_data: 渲染数据。
        action: 点击行为。
        group_id: 按钮组 ID。同组按钮互斥（点击一个会灰掉其他的）。
    """

    id: str
    render_data: KeyboardButtonRenderData
    action: KeyboardButtonAction
    group_id: str = "default"

    def to_dict(self) -> dict[str, object]:
        """序列化为 API 请求可用的字典。"""
        return {
            "id": self.id,
            "render_data": self.render_data.to_dict(),
            "action": self.action.to_dict(),
            "group_id": self.group_id,
        }


class KeyboardRow(BaseModel):
    """一行按钮（横向排列）。

    Attributes:
        buttons: 该行的按钮列表。
    """

    buttons: list[KeyboardButton] = Field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """序列化为 API 请求可用的字典。"""
        return {"buttons": [b.to_dict() for b in self.buttons]}


class KeyboardContent(BaseModel):
    """键盘内容（多行）。

    Attributes:
        rows: 所有行的按钮列表。
    """

    rows: list[KeyboardRow] = Field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """序列化为 API 请求可用的字典。"""
        return self.model_dump()


class InlineKeyboard(BaseModel):
    """内联键盘顶层结构。

    嵌入到消息的 ``keyboard`` 字段中发送。

    Attributes:
        content: 键盘内容。
    """

    content: KeyboardContent = Field(default_factory=KeyboardContent)

    def to_dict(self) -> dict[str, object]:
        """序列化为 API 请求可用的字典。"""
        return self.model_dump()


# ======================================================================
# 交互事件（按钮点击）
# ======================================================================


class ChatTypeEnum(IntEnum):
    """聊天类型枚举。"""

    GUILD = 0
    GROUP = 1
    C2C = 2


class InteractionEvent(BaseModel):
    """``INTERACTION_CREATE`` 事件解析结果。

    当用户点击内联键盘按钮时，QQ Bot API 推送此事件。

    Attributes:
        id: 交互事件 ID（用于 ACK）。
        type: 事件类型码（11 = 消息按钮）。
        chat_type: 聊天类型编码。
        scene: 人类可读的场景名（guild / group / c2c）。
        group_openid: 群 openid。
        group_member_openid: 群成员 openid。
        user_openid: 用户 openid。
        channel_id: 频道 ID。
        guild_id: 服务器 ID。
        button_data: 按钮携带的数据（如 approve:key:decision）。
        button_id: 点击的按钮 ID。
        resolver_user_id: 处理者用户 ID。
    """

    id: str = ""
    type: int = 0
    chat_type: int = 0
    scene: str = ""
    group_openid: str = ""
    group_member_openid: str = ""
    user_openid: str = ""
    channel_id: str = ""
    guild_id: str = ""
    button_data: str = ""
    button_id: str = ""
    resolver_user_id: str = ""

    @property
    def operator_openid(self) -> str:
        """获取操作者的 openid（按优先级：群成员 > 用户 > 处理者）。"""
        return (
            self.group_member_openid
            or self.user_openid
            or self.resolver_user_id
        )


# ======================================================================
# 审批相关
# ======================================================================


class ApprovalRequest(BaseModel):
    """审批请求的展示数据。

    Attributes:
        session_key: 用于将决策路由回等待的调用方。
        title: 审批标题。
        description: 详细描述。
        command_preview: 待执行的命令文本。
        cwd: 工作目录。
        tool_name: 工具名称。
        severity: 严重级别（critical / info / ''）。
        timeout_sec: 超时秒数。
    """

    session_key: str
    title: str
    description: str = ""
    command_preview: str = ""
    cwd: str = ""
    tool_name: str = ""
    severity: str = ""
    timeout_sec: int = 120


# ======================================================================
# 审批回调类型
# ======================================================================

# POST 消息的函数签名（适配器注入用）


# ======================================================================
# 分片上传
# ======================================================================


class UploadPrepareResponse(BaseModel):
    """调用 upload_prepare 后的响应。

    Attributes:
        upload_id: 上传任务 ID。
        block_size: 每个分片的大小（字节）。
        upload_urls: 预签名的 COS 上传 URL 列表。
    """

    upload_id: str
    block_size: int
    upload_urls: list[str]


class UploadPartFinishResponse(BaseModel):
    """调用 upload_part_finish 后的响应。

    Attributes:
        part_number: 已完成的分片序号。
        etag: 分片的 ETag。
    """

    part_number: int
    etag: str


class UploadCompleteResponse(BaseModel):
    """上传完成后返回的文件信息。

    Attributes:
        file_info: 用于 RichMedia 消息的 file_info token。
    """

    file_info: str


# ======================================================================
# 扫码配网
# ======================================================================


class BindStatusEnum(IntEnum):
    """扫码配网状态枚举。"""

    NONE = 0
    PENDING = 1
    COMPLETED = 2
    EXPIRED = 3


class BindResult(BaseModel):
    """扫码配网结果。

    Attributes:
        app_id: 机器人 app_id。
        client_secret: 解密后的 client_secret。
        user_openid: 扫码用户的 openid。
    """

    app_id: str
    client_secret: str
    user_openid: str


# ======================================================================
# 事件分发回调类型
# ======================================================================

# 收到消息后的回调签名
OnMessageCallback = Callable[
    [QQMessage],
    Coroutine["asyncio.AbstractEventLoop", object, None],
]

# 按钮交互事件的回调签名
OnInteractionCallback = Callable[
    [InteractionEvent],
    Coroutine["asyncio.AbstractEventLoop", object, None],
]
