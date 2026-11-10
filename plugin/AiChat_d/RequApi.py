import asyncio
from typing import Any

import httpx

from modules.Logger import logger
from plugin.AiChat_d.Config import config
from plugin.AiChat_d.History import PersonHistory
from plugin.AiChat_d.Types import ApiJson, ApiJson_Messages

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


def _extract_reply(payload: dict[str, Any]) -> str:
    """从 OpenAI 兼容响应中取出回复文本。

    Args:
        payload: 响应 JSON。

    Returns:
        回复文本。

    Raises:
        ValueError: 响应结构不符合预期。
    """
    try:
        content: Any = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"响应结构异常: {payload}") from exc
    if not isinstance(content, str):
        raise ValueError(f"回复内容不是字符串: {content!r}")
    return content


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
    payload: ApiJson = {
        "model": config.model,
        "messages": history.getHistory() + [{"role": "user", "content": message}],
        "stream": False,
        "temperature": 0.7,
        "top_p": 0.7,
        "max_tokens": 2048,
        "do_sample": True,
        "thinking": {"type": "disabled"},
    }
    headers: dict[str, str] = {"Authorization": f"Bearer {config.apiKey}"}

    logger.info(f"请求 AI openid={open_id}, 内容={message}")

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response: httpx.Response = await _get_client().post(
                config.url, headers=headers, json=payload
            )
            if response.is_success:
                reply: str = _extract_reply(response.json())
            else:
                logger.warning(
                    f"AI 接口返回 {response.status_code}: {response.text[:200]}"
                )
                reply = ""
        except Exception as exc:
            logger.warning(f"AI 接口请求异常（第 {attempt} 次）: {exc}")
            reply = ""

        if reply:
            history.addHistory(ApiJson_Messages(role="user", content=message))
            history.addHistory(ApiJson_Messages(role="assistant", content=reply))
            logger.info(f"AI 回复 openid={open_id}, 内容={reply}")
            return reply

        if attempt < _MAX_ATTEMPTS:
            await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)

    logger.error(f"AI 接口请求失败 openid={open_id}")
    return _FALLBACK_REPLY
