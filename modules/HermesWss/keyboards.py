"""内联键盘构建工具。

提供 QQ Bot 内联键盘的构建函数和交互解析器。
"""

from __future__ import annotations

import re
import logging
from typing import Optional

from .models import (
    InlineKeyboard,
    KeyboardContent,
    KeyboardRow,
    KeyboardButton,
    KeyboardButtonRenderData,
    KeyboardButtonAction,
    KeyboardButtonPermission,
    ApprovalRequest,
    InteractionEvent,
    PostMessageFn,
)

logger = logging.getLogger(__name__)

APPROVAL_BUTTON_PREFIX = "approve:"
UPDATE_PROMPT_PREFIX = "update_prompt:"
_APPROVAL_DATA_RE = re.compile(r"^approve:(.+):(allow-once|allow-always|deny)$")
_UPDATE_PROMPT_RE = re.compile(r"^update_prompt:(y|n)$")


# ── internal helpers ──────────────────────────────────────────────────


def _make_callback_button(
    btn_id: str,
    label: str,
    visited_label: str,
    data: str,
    style: int = 1,
    group_id: str = "default",
) -> KeyboardButton:
    """构建一个回调类型的内联键盘按钮。

    Args:
        btn_id: 按钮唯一标识符。
        label: 按钮显示的文本。
        visited_label: 点击后显示的文本。
        data: 回调数据 payload（点击时通过 INTERACTION_CREATE 返回）。
        style: 按钮样式，0=灰色，1=蓝色。默认为 1。
        group_id: 按钮所属组 ID。同组按钮互斥（点击一个会灰掉其他同组按钮）。
            默认为 ``"default"``。

    Returns:
        配置完成的 :class:`KeyboardButton` 实例。
    """
    return KeyboardButton(
        id=btn_id,
        render_data=KeyboardButtonRenderData(
            label=label,
            visited_label=visited_label,
            style=style,
        ),
        action=KeyboardButtonAction(
            type=1,
            data=data,
            permission=KeyboardButtonPermission(type=2),
            click_limit=1,
        ),
        group_id=group_id,
    )


# ── approval keyboard ────────────────────────────────────────────────


def build_approval_keyboard(session_key: str) -> InlineKeyboard:
    """构建命令审批内联键盘。

    生成一个包含三个按钮的单行键盘：
    ``✅ 允许一次`` / ``⭐ 始终允许`` / ``❌ 拒绝``。

    所有三个按钮共享 ``group_id="approval"``，因此点击其中一个后
    另外两个自动灰掉（互斥）。

    Args:
        session_key: 会话标识符，用于将按钮回调路由回对应的等待调用方。

    Returns:
        配置完成的 :class:`InlineKeyboard` 实例。
    """
    allow_once = _make_callback_button(
        btn_id="approve-allow-once",
        label="✅ 允许一次",
        visited_label="✅ 已允许",
        data=f"{APPROVAL_BUTTON_PREFIX}{session_key}:allow-once",
        style=1,
        group_id="approval",
    )
    allow_always = _make_callback_button(
        btn_id="approve-allow-always",
        label="⭐ 始终允许",
        visited_label="⭐ 已允许",
        data=f"{APPROVAL_BUTTON_PREFIX}{session_key}:allow-always",
        style=1,
        group_id="approval",
    )
    deny = _make_callback_button(
        btn_id="approve-deny",
        label="❌ 拒绝",
        visited_label="❌ 已拒绝",
        data=f"{APPROVAL_BUTTON_PREFIX}{session_key}:deny",
        style=0,
        group_id="approval",
    )

    return InlineKeyboard(
        content=KeyboardContent(
            rows=[
                KeyboardRow(
                    buttons=[allow_once, allow_always, deny],
                ),
            ],
        ),
    )


# ── update prompt keyboard ───────────────────────────────────────────


def build_update_prompt_keyboard() -> InlineKeyboard:
    """构建更新提示内联键盘。

    生成一个包含两个按钮的单行键盘：
    ``✓ 确认`` / ``✗ 取消``。

    用于确认是否使用 LLM 生成的更新内容覆盖当前消息。

    Returns:
        配置完成的 :class:`InlineKeyboard` 实例。
    """
    confirm = _make_callback_button(
        btn_id="update-confirm",
        label="✓ 确认",
        visited_label="✓ 已确认",
        data=f"{UPDATE_PROMPT_PREFIX}y",
        style=1,
        group_id="update_prompt",
    )
    cancel = _make_callback_button(
        btn_id="update-cancel",
        label="✗ 取消",
        visited_label="✗ 已取消",
        data=f"{UPDATE_PROMPT_PREFIX}n",
        style=0,
        group_id="update_prompt",
    )

    return InlineKeyboard(
        content=KeyboardContent(
            rows=[
                KeyboardRow(
                    buttons=[confirm, cancel],
                ),
            ],
        ),
    )


# ── data parsers ─────────────────────────────────────────────────────


def parse_approval_button_data(button_data: str) -> tuple[str, str] | None:
    """解析审批按钮的回调数据。

    数据格式: ``approve:<session_key>:<decision>``

    ``decision`` 的取值范围为 ``allow-once``、``allow-always``、``deny``。

    Args:
        button_data: 按钮携带的原始 data 字符串。

    Returns:
        ``(session_key, decision)`` 的二元组；如果 data 不是审批按钮数据
        则返回 ``None``。
    """
    match = _APPROVAL_DATA_RE.match(button_data)
    if match is None:
        return None
    session_key: str = match.group(1)
    decision: str = match.group(2)
    return (session_key, decision)


def parse_update_prompt_button_data(button_data: str) -> str | None:
    """解析更新提示按钮的回调数据。

    数据格式: ``update_prompt:<choice>``

    ``choice`` 为 ``y``（确认）或 ``n``（取消）。

    Args:
        button_data: 按钮携带的原始 data 字符串。

    Returns:
        字符串 ``"y"`` 或 ``"n"``；如果 data 不是更新提示按钮数据
        则返回 ``None``。
    """
    match = _UPDATE_PROMPT_RE.match(button_data)
    if match is None:
        return None
    return match.group(1)


# ── text builders ────────────────────────────────────────────────────


def build_approval_text(req: ApprovalRequest) -> str:
    """将审批请求渲染为 Markdown 文本消息。

    生成的文本包含审批标题、描述、待执行命令预览、工作目录、
    工具名称、严重级别以及超时信息。严重级别为 ``"critical"``
    时会在标题前附加 ``🚨`` 图标。

    Args:
        req: 待渲染的审批请求对象。

    Returns:
        Markdown 格式的文本字符串。
    """
    lines: list[str] = []

    # Title with severity indicator
    severity_icon = "🚨 " if req.severity == "critical" else ""
    lines.append(f"### {severity_icon}{req.title}")

    # Description
    if req.description:
        lines.append("")
        lines.append(req.description)

    # Tool name
    if req.tool_name:
        lines.append("")
        lines.append(f"**工具:** `{req.tool_name}`")

    # Working directory
    if req.cwd:
        lines.append("")
        lines.append(f"**工作目录:** `{req.cwd}`")

    # Command preview
    if req.command_preview:
        lines.append("")
        lines.append("**待执行命令:**")
        lines.append(f"```bash\n{req.command_preview}\n```")

    # Timeout
    lines.append("")
    lines.append(f"**超时:** {req.timeout_sec}s")

    return "\n".join(lines)


# ── event parsers ────────────────────────────────────────────────────


def parse_interaction_event(raw: dict[str, object]) -> InteractionEvent:
    """解析原始的 ``INTERACTION_CREATE`` dispatch payload。

    QQ Bot API 的 INTERACTION_CREATE 事件中，按钮相关的字段
    （``button_data``、``button_id``、``resolver_user_id``）
    位于嵌套的 ``data`` 对象内。本函数将其扁平化为
    :class:`InteractionEvent` 的顶层字段。

    同时根据 ``chat_type`` 推导出人类可读的 ``scene`` 值：
    ``0 -> guild``、``1 -> group``、``2 -> c2c``。

    Args:
        raw: 从 WebSocket Dispatch 收到的原始 payload dict。

    Returns:
        解析完成的 :class:`InteractionEvent` 实例。
    """
    # Extract nested data object if present
    nested_data: dict[str, object] = {}
    raw_data = raw.get("data")
    if isinstance(raw_data, dict):
        nested_data = raw_data

    # Determine scene from chat_type
    raw_chat_type = raw.get("chat_type", 0)
    chat_type: int
    if isinstance(raw_chat_type, int):
        chat_type = raw_chat_type
    else:
        chat_type = 0

    scene_map: dict[int, str] = {0: "guild", 1: "group", 2: "c2c"}
    scene: str = scene_map.get(chat_type, "unknown")

    # Extract fields that may live in nested data
    button_data: str
    raw_button_data = nested_data.get("button_data")
    if isinstance(raw_button_data, str):
        button_data = raw_button_data
    else:
        raw_top_button_data = raw.get("button_data")
        if isinstance(raw_top_button_data, str):
            button_data = raw_top_button_data
        else:
            button_data = ""

    button_id: str
    raw_button_id = nested_data.get("button_id")
    if isinstance(raw_button_id, str):
        button_id = raw_button_id
    else:
        raw_top_button_id = raw.get("button_id")
        if isinstance(raw_top_button_id, str):
            button_id = raw_top_button_id
        else:
            button_id = ""

    resolver_user_id: str
    raw_resolver = nested_data.get("resolver_user_id")
    if isinstance(raw_resolver, str):
        resolver_user_id = raw_resolver
    else:
        raw_top_resolver = raw.get("resolver_user_id")
        if isinstance(raw_top_resolver, str):
            resolver_user_id = raw_top_resolver
        else:
            resolver_user_id = ""

    # Top-level scalar fields
    event_id: str
    raw_id = raw.get("id")
    if isinstance(raw_id, str):
        event_id = raw_id
    else:
        event_id = ""

    raw_type_val = raw.get("type", 0)
    event_type: int
    if isinstance(raw_type_val, int):
        event_type = raw_type_val
    else:
        event_type = 0

    raw_group_openid = raw.get("group_openid")
    group_openid: str
    if isinstance(raw_group_openid, str):
        group_openid = raw_group_openid
    else:
        group_openid = ""

    raw_group_member = raw.get("group_member_openid")
    group_member_openid: str
    if isinstance(raw_group_member, str):
        group_member_openid = raw_group_member
    else:
        group_member_openid = ""

    raw_user_openid = raw.get("user_openid")
    user_openid: str
    if isinstance(raw_user_openid, str):
        user_openid = raw_user_openid
    else:
        user_openid = ""

    raw_channel_id = raw.get("channel_id")
    channel_id: str
    if isinstance(raw_channel_id, str):
        channel_id = raw_channel_id
    else:
        channel_id = ""

    raw_guild_id = raw.get("guild_id")
    guild_id: str
    if isinstance(raw_guild_id, str):
        guild_id = raw_guild_id
    else:
        guild_id = ""

    return InteractionEvent(
        id=event_id,
        type=event_type,
        chat_type=chat_type,
        scene=scene,
        group_openid=group_openid,
        group_member_openid=group_member_openid,
        user_openid=user_openid,
        channel_id=channel_id,
        guild_id=guild_id,
        button_data=button_data,
        button_id=button_id,
        resolver_user_id=resolver_user_id,
    )
