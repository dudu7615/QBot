"""调用 OpenAI 兼容接口获取回复。"""

import asyncio

import httpx
from pydantic import ValidationError

from modules.Logger import logger
from plugin.AiChat_d.Config import config
from plugin.AiChat_d.History import PersonHistory
from plugin.AiChat_d.Sql import Message
from plugin.AiChat_d.Types import ChatMessage, ChatRequest, ChatResponse

_FALLBACK_REPLY = "抱歉，AI 接口请求失败，请稍后再试。"
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.0

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """返回模块级复用的 AsyncClient。"""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=60.0)
    return _client


async def close() -> None:
    """关闭共享的 HTTP 客户端（进程退出时调用）。"""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _extract_reply(payload: bytes) -> str:
    """从 OpenAI 兼容响应中取出回复文本。

    Args:
        payload: 响应体原始字节。

    Returns:
        回复文本；结构不符合预期时返回空字符串。
    """
    try:
        response = ChatResponse.model_validate_json(payload)
    except ValidationError as exc:
        logger.warning(f"AI 响应结构异常: {exc}")
        return ""

    if not response.choices:
        logger.warning("AI 响应缺少 choices")
        return ""
    return response.choices[0].message.content


async def request_reply(message: str, open_id: str) -> str:
    """向 LLM 请求一次回复，并把成功的一轮写入历史。

    只有请求成功时才落库用户消息与助手回复，避免失败时留下孤立轮次。

    Args:
        message: 用户输入。
        open_id: 会话标识。

    Returns:
        AI 回复文本；失败时返回固定提示。
    """
    history = PersonHistory(open_id)
    request = ChatRequest(
        model=config.model,
        messages=[
            ChatMessage(**item) for item in history.getHistory()
        ]
        + [ChatMessage(role="user", content=message)],
    )
    headers: dict[str, str] = {"Authorization": f"Bearer {config.apiKey}"}

    logger.info(f"请求 AI openid={open_id}, 内容={message}")

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        reply: str = ""
        try:
            response: httpx.Response = await _get_client().post(
                config.url,
                headers=headers,
                json=request.model_dump(),
            )
            if response.is_success:
                reply = _extract_reply(response.content)
            else:
                logger.warning(
                    f"AI 接口返回 {response.status_code}: {response.text[:200]}"
                )
        except Exception as exc:
            logger.warning(f"AI 接口请求异常（第 {attempt} 次）: {exc}")

        if reply:
            # 一问一答在同一事务内写入，失败不会留下半轮对话
            Message.addTurn(open_id, message, reply)
            logger.info(f"AI 回复 openid={open_id}, 内容={reply}")
            return reply

        if attempt < _MAX_ATTEMPTS:
            await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)

    logger.error(f"AI 接口请求失败 openid={open_id}")
    return _FALLBACK_REPLY
