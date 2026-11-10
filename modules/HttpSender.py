"""HttpSender — 插件层统一的消息发送入口。

封装 HermesWss 的 QQMessageSender，插件只依赖这里的两个函数，
不关心底层分片、重试与 token 管理。
"""

from __future__ import annotations

from modules.Config import config
from modules.Logger import logger
from modules.Types import MessageData
from modules.HermesWss import QQMessageSender, SendResult


# 模块级单例 — 所有插件共用
_sender: QQMessageSender = QQMessageSender(
    app_id=config["appId"],
    client_secret=config["clientSecret"],
)


def _reply_context(message: MessageData) -> tuple[str, str | None]:
    """提取被动回复所需的 msg_id 与 event_id。

    Args:
        message: 接收到的原始消息。

    Returns:
        (msg_id, event_id)，event_id 缺失时为 None。
    """
    return message["d"]["id"], message.get("event_id") or None


def _log_result(
    results: list[SendResult],
    label: str,
    target: str,
) -> None:
    """记录发送结果。

    Args:
        results: 每片的发送结果。
        label: 场景描述，如「私聊」「群聊」。
        target: 目标 openid（日志中截断）。
    """
    success_count: int = sum(1 for item in results if item.success)
    if success_count == len(results):
        logger.info(f"{label}消息发送成功 ({len(results)}片) → {target[:12]}...")
        return

    logger.error(
        f"{label}消息部分失败 ({success_count}/{len(results)}片) → {target[:12]}..."
    )
    for item in results:
        if not item.success:
            logger.error(f"  ├ 失败原因: {item.error}")


async def send_text(
    text: str,
    received: MessageData,
    target: str,
    *,
    is_group: bool,
) -> None:
    """发送文字消息，超长自动分片。

    Args:
        text: 消息内容。
        received: 接收到的原始消息（用于被动回复）。
        target: 用户 openid 或群 openid。
        is_group: 是否发往群聊。
    """
    msg_id, event_id = _reply_context(received)
    label: str = "群聊" if is_group else "私聊"

    results: list[SendResult]
    if is_group:
        results = await _sender.send_long_text_to_group(
            group_openid=target,
            content=text,
            reply_to=msg_id,
            event_id=event_id,
        )
    else:
        results = await _sender.send_long_text_to_c2c(
            openid=target,
            content=text,
            reply_to=msg_id,
            event_id=event_id,
        )
    _log_result(results, label, target)


async def sendText2Person(
    message: str,
    recievedMessage: MessageData,
    to: str,
) -> None:
    """发送文字消息到 C2C 私聊（向后兼容的旧签名）。

    Args:
        message: 要发送的文本内容。
        recievedMessage: 接收到的原始消息。
        to: 目标用户 openid。
    """
    await send_text(message, recievedMessage, to, is_group=False)


async def sendText2Group(
    message: str,
    recievedMessage: MessageData,
    group_openid: str,
) -> None:
    """发送文字消息到群聊（向后兼容的旧签名）。

    Args:
        message: 要发送的文本内容。
        recievedMessage: 接收到的原始消息。
        group_openid: 目标群 openid。
    """
    await send_text(message, recievedMessage, group_openid, is_group=True)
