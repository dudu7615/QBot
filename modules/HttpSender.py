"""
HttpSender — QQ Bot 消息发送器（向后兼容封装）。

基于 HermesWss 的 QQMessageSender 实现，保留原有的函数签名，
使现有插件无需修改即可继续使用。

新增功能（相对于旧版 HttpSender）：
  - 自动管理 Access Token（TokenManager singleflight）
  - 支持超长文本自动分片
  - 支持富媒体、键盘消息
  - 带重试机制
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


async def sendText2Person(
    message: str,
    recievedMessage: MessageData,
    to: str,
) -> None:
    """发送文字消息到 C2C 私聊（向后兼容）。

    Args:
        message: 要发送的文本内容。
        recievedMessage: 接收到的原始消息（用于提取 msg_id 做回复引用）。
        to: 目标用户 openid。
    """
    msg_id: str = recievedMessage["d"]["id"]
    event_id: str | None = recievedMessage.get("event_id") or None

    result: SendResult = await _sender.send_text_to_c2c(
        openid=to,
        content=message,
        reply_to=msg_id,
        event_id=event_id,
    )

    if result.success:
        logger.info(
            f"私聊消息发送成功 msg_id={result.message_id[:12]}... → {to[:12]}..."
        )
    else:
        logger.error(
            f"私聊消息发送失败 → {to[:12]}...: {result.error}"
        )


async def sendLongText2Person(
    message: str,
    recievedMessage: MessageData,
    to: str,
) -> None:
    """发送长文本到 C2C 私聊，超长时自动分片。

    Args:
        message: 要发送的文本内容（超过 4000 字符自动分片）。
        recievedMessage: 接收到的原始消息。
        to: 目标用户 openid。
    """
    msg_id: str = recievedMessage["d"]["id"]
    event_id: str | None = recievedMessage.get("event_id") or None

    results: list[SendResult] = await _sender.send_long_text_to_c2c(
        openid=to,
        content=message,
        reply_to=msg_id,
        event_id=event_id,
    )

    success_count: int = sum(1 for r in results if r.success)
    if success_count == len(results):
        logger.info(
            f"长文本发送成功 ({len(results)}片) → {to[:12]}..."
        )
    else:
        failed: int = len(results) - success_count
        logger.error(
            f"长文本发送部分失败 ({success_count}/{len(results)}片) → {to[:12]}..."
        )


async def sendText2Group(
    message: str,
    recievedMessage: MessageData,
    group_openid: str,
) -> None:
    """发送文字消息到群聊。

    Args:
        message: 要发送的文本内容。
        recievedMessage: 接收到的原始消息（用于提取 msg_id 做回复引用）。
        group_openid: 目标群 openid。
    """
    msg_id: str = recievedMessage["d"]["id"]
    event_id: str | None = recievedMessage.get("event_id") or None

    result: SendResult = await _sender.send_text_to_group(
        group_openid=group_openid,
        content=message,
        reply_to=msg_id,
        event_id=event_id,
    )

    if result.success:
        logger.info(
            f"群聊消息发送成功 msg_id={result.message_id[:12]}... "
            f"→ group={group_openid[:12]}..."
        )
    else:
        logger.error(
            f"群聊消息发送失败 → group={group_openid[:12]}...: {result.error}"
        )


async def sendLongText2Group(
    message: str,
    recievedMessage: MessageData,
    group_openid: str,
) -> None:
    """发送长文本到群聊，超长时自动分片。

    Args:
        message: 要发送的文本内容（超过 4000 字符自动分片）。
        recievedMessage: 接收到的原始消息。
        group_openid: 目标群 openid。
    """
    msg_id: str = recievedMessage["d"]["id"]
    event_id: str | None = recievedMessage.get("event_id") or None

    results: list[SendResult] = await _sender.send_long_text_to_group(
        group_openid=group_openid,
        content=message,
        reply_to=msg_id,
        event_id=event_id,
    )

    success_count: int = sum(1 for r in results if r.success)
    if success_count == len(results):
        logger.info(
            f"群聊长文本发送成功 ({len(results)}片) → group={group_openid[:12]}..."
        )
    else:
        failed: int = len(results) - success_count
        logger.error(
            f"群聊长文本发送部分失败 ({success_count}/{len(results)}片) "
            f"→ group={group_openid[:12]}..."
        )
