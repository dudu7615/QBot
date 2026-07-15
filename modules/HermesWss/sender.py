"""
HermesWss — QQ Bot REST API 消息发送器。

提供文字、图片、语音、视频、文件、键盘消息的发送能力。
所有方法均通过 TokenManager 自动管理 access token 的获取与刷新。

从 Hermes Agent 的 gateway/platforms/qqbot/adapter.py 移植。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

import httpx

from .constants import API_BASE, DEFAULT_API_TIMEOUT, MEDIA_TYPE_IMAGE, MEDIA_TYPE_VOICE, MEDIA_TYPE_VIDEO, MEDIA_TYPE_FILE, MSG_TYPE_TEXT, MSG_TYPE_MARKDOWN, MSG_TYPE_MEDIA, MSG_TYPE_INPUT_NOTIFY, MAX_MESSAGE_LENGTH
from .exceptions import QQApiError, QQTokenError
from .keyboards import build_approval_keyboard, build_approval_text, build_update_prompt_keyboard
from .models import (
    ApprovalRequest,
    InlineKeyboard,
    SendResult,
    AccessTokenData,
)
from .token_manager import TokenManager
from .utils import get_api_headers


logger = logging.getLogger(__name__)


class QQMessageSender:
    """QQ Bot 消息发送器。

    封装所有 REST API 调用，自动管理 access token。
    支持文字、富媒体、键盘消息的发送。

    Attributes:
        api_base: API 基础 URL。
        _token_manager: Token 管理器。
        _http_client: HTTP 客户端实例。
    """

    def __init__(
        self,
        app_id: str,
        client_secret: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """初始化消息发送器。

        Args:
            app_id: QQ Bot 的 app_id。
            client_secret: QQ Bot 的 client_secret。
            http_client: 可选的 httpx 客户端。未提供时内部创建。
        """
        self.api_base: str = API_BASE
        self._http_client: httpx.AsyncClient = http_client or httpx.AsyncClient(
            timeout=DEFAULT_API_TIMEOUT,
            follow_redirects=True,
        )
        self._token_manager: TokenManager = TokenManager(
            app_id, client_secret, self._http_client,
        )

    # ==================================================================
    # 内部 API 请求
    # ==================================================================

    async def _api_request(
        self,
        method: str,
        path: str,
        json_body: dict[str, object] | None = None,
        token: str | None = None,
    ) -> dict[str, object]:
        """发起 QQ Bot REST API 请求。

        Args:
            method: HTTP 方法（GET / POST / PUT / DELETE）。
            path: API 路径（如 /v2/users/{openid}/messages），相对于 api_base。
            json_body: 请求体 JSON 字典。
            token: 可选的 access token。未提供时自动获取。

        Returns:
            解析后的 JSON 响应字典。

        Raises:
            QQTokenError: Token 获取失败。
            QQApiError: API 返回非 2xx 状态码。
        """
        if token is None:
            token = await self._token_manager.get_token()

        url: str = f"{self.api_base}{path}"
        headers: dict[str, str] = {
            "Authorization": f"QQBot {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        response: httpx.Response
        try:
            response = await self._http_client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_body,
            )
        except httpx.RequestError as exc:
            raise QQApiError(0, str(exc)) from exc

        if not response.is_success:
            raise QQApiError(response.status_code, response.text)

        result: dict[str, object] = response.json()
        return result

    # ==================================================================
    # 文字消息
    # ==================================================================

    def _build_text_body(
        self,
        content: str,
        reply_to: str | None = None,
        keyboard: InlineKeyboard | None = None,
        event_id: str | None = None,
    ) -> dict[str, object]:
        """构建文字消息请求体。

        Args:
            content: 消息文本内容（纯文本，非 Markdown）。
            reply_to: 要回复的消息 ID（可选）。
            keyboard: 附加的内联键盘（可选）。
            event_id: 网关事件 ID（可选，用于被动回复）。

        Returns:
            可用于 API 请求的消息体字典。
        """
        # 生成消息序列号（防重放 + 回复链标识）
        import time as _time
        import uuid as _uuid
        time_part: int = int(_time.time()) % 100000000
        rand_part: int = int(_uuid.uuid4().hex[:4], 16)
        msg_seq: int = (time_part ^ rand_part) % 65536

        body: dict[str, object] = {
            "content": content,
            "msg_type": MSG_TYPE_TEXT,
            "msg_seq": msg_seq,
        }
        if reply_to is not None:
            body["msg_id"] = reply_to
            body["message_reference"] = {
                "message_id": reply_to,
                "ignore_get_message_error": True,
            }
        if event_id:
            body["event_id"] = event_id
        if keyboard is not None:
            body["keyboard"] = keyboard.to_dict()
        return body

    async def send_text_to_c2c(
        self,
        openid: str,
        content: str,
        reply_to: str | None = None,
        keyboard: InlineKeyboard | None = None,
        event_id: str | None = None,
    ) -> SendResult:
        """发送文字消息到 C2C 私聊。

        Args:
            openid: 用户的 openid。
            content: 消息文本（纯文本，不超过 4000 字符）。
            reply_to: 要回复的消息 ID（可选）。
            keyboard: 附加的内联键盘（可选）。

        Returns:
            发送结果（SendResult）。
        """
        body: dict[str, object] = self._build_text_body(content, reply_to, keyboard, event_id)
        return await self._send_with_retry("POST", f"/v2/users/{openid}/messages", body)

    async def send_text_to_group(
        self,
        group_openid: str,
        content: str,
        reply_to: str | None = None,
        keyboard: InlineKeyboard | None = None,
        event_id: str | None = None,
    ) -> SendResult:
        """发送文字消息到群聊。

        Args:
            group_openid: 群的 openid。
            content: 消息文本（纯文本，不超过 4000 字符）。
            reply_to: 要回复的消息 ID（可选）。
            keyboard: 附加的内联键盘（可选）。

        Returns:
            发送结果（SendResult）。
        """
        body: dict[str, object] = self._build_text_body(content, reply_to, keyboard, event_id)
        return await self._send_with_retry("POST", f"/v2/groups/{group_openid}/messages", body)

    async def send_long_text_to_c2c(
        self,
        openid: str,
        content: str,
        reply_to: str | None = None,
        event_id: str | None = None,
    ) -> list[SendResult]:
        """发送长文字到 C2C，超长时自动分片。

        Args:
            openid: 用户的 openid。
            content: 消息文本（自动按 4000 字符分片）。
            reply_to: 回复的消息 ID（仅第一片携带）。
            event_id: 网关事件 ID（仅第一片携带）。

        Returns:
            每片的发送结果列表。
        """
        return await self._send_chunked(
            openid,
            content,
            reply_to,
            is_group=False,
            event_id=event_id,
        )

    async def send_long_text_to_group(
        self,
        group_openid: str,
        content: str,
        reply_to: str | None = None,
        event_id: str | None = None,
    ) -> list[SendResult]:
        """发送长文字到群聊，超长时自动分片。

        Args:
            group_openid: 群的 openid。
            content: 消息文本（自动按 4000 字符分片）。
            reply_to: 回复的消息 ID（仅第一片携带）。
            event_id: 网关事件 ID（仅第一片携带）。

        Returns:
            每片的发送结果列表。
        """
        return await self._send_chunked(
            group_openid,
            content,
            reply_to,
            is_group=True,
            event_id=event_id,
        )

    async def _send_chunked(
        self,
        chat_id: str,
        content: str,
        reply_to: str | None = None,
        is_group: bool = False,
        event_id: str | None = None,
    ) -> list[SendResult]:
        """将长文本按 4000 字符分片发送。

        Args:
            chat_id: 聊天对象 ID。
            content: 消息文本。
            reply_to: 初始回复的消息 ID。
            is_group: 是否为群聊消息。
            event_id: 网关事件 ID（仅第一片携带）。

        Returns:
            每片的发送结果列表。
        """
        results: list[SendResult] = []

        async def _do_send(text: str, reply: str | None) -> SendResult:
            if is_group:
                return await self.send_text_to_group(chat_id, text, reply, event_id=event_id)
            return await self.send_text_to_c2c(chat_id, text, reply, event_id=event_id)

        if len(content) <= MAX_MESSAGE_LENGTH:
            result: SendResult = await _do_send(content, reply_to)
            results.append(result)
            return results

        chunk_start: int = 0
        is_first: bool = True
        while chunk_start < len(content):
            chunk: str = content[chunk_start:chunk_start + MAX_MESSAGE_LENGTH]
            result = await _do_send(chunk, reply_to if is_first else None)
            results.append(result)
            chunk_start += MAX_MESSAGE_LENGTH
            is_first = False

        return results

    # ==================================================================
    # 富媒体消息
    # ==================================================================

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        chat_type: str = "c2c",
        reply_to: str | None = None,
    ) -> SendResult:
        """发送图片消息。

        Args:
            chat_id: 用户的 openid 或群 openid。
            image_url: 图片的 URL。
            chat_type: 聊天类型（"c2c" 或 "group"）。
            reply_to: 回复的消息 ID（可选）。

        Returns:
            发送结果（SendResult）。
        """
        body: dict[str, object] = {
            "msg_type": MSG_TYPE_MEDIA,
            "media": {
                "url": image_url,
                "type": MEDIA_TYPE_IMAGE,
            },
        }
        if reply_to is not None:
            body["msg_id"] = reply_to

        endpoint: str = (
            f"/v2/users/{chat_id}/messages"
            if chat_type == "c2c"
            else f"/v2/groups/{chat_id}/messages"
        )
        return await self._send_with_retry("POST", endpoint, body)

    async def send_voice(
        self,
        chat_id: str,
        voice_url: str,
        chat_type: str = "c2c",
        reply_to: str | None = None,
    ) -> SendResult:
        """发送语音消息。

        Args:
            chat_id: 用户的 openid 或群 openid。
            voice_url: 语音文件的 URL（支持格式：silk / amr）。
            chat_type: 聊天类型（"c2c" 或 "group"）。
            reply_to: 回复的消息 ID（可选）。

        Returns:
            发送结果（SendResult）。
        """
        body: dict[str, object] = {
            "msg_type": MSG_TYPE_MEDIA,
            "media": {
                "url": voice_url,
                "type": MEDIA_TYPE_VOICE,
            },
        }
        if reply_to is not None:
            body["msg_id"] = reply_to

        endpoint: str = (
            f"/v2/users/{chat_id}/messages"
            if chat_type == "c2c"
            else f"/v2/groups/{chat_id}/messages"
        )
        return await self._send_with_retry("POST", endpoint, body)

    async def send_video(
        self,
        chat_id: str,
        video_url: str,
        chat_type: str = "c2c",
        reply_to: str | None = None,
    ) -> SendResult:
        """发送视频消息。

        Args:
            chat_id: 用户的 openid 或群 openid。
            video_url: 视频文件的 URL。
            chat_type: 聊天类型（"c2c" 或 "group"）。
            reply_to: 回复的消息 ID（可选）。

        Returns:
            发送结果（SendResult）。
        """
        body: dict[str, object] = {
            "msg_type": MSG_TYPE_MEDIA,
            "media": {
                "url": video_url,
                "type": MEDIA_TYPE_VIDEO,
            },
        }
        if reply_to is not None:
            body["msg_id"] = reply_to

        endpoint: str = (
            f"/v2/users/{chat_id}/messages"
            if chat_type == "c2c"
            else f"/v2/groups/{chat_id}/messages"
        )
        return await self._send_with_retry("POST", endpoint, body)

    async def send_file(
        self,
        chat_id: str,
        file_url: str,
        chat_type: str = "c2c",
        reply_to: str | None = None,
    ) -> SendResult:
        """发送文件消息。

        Args:
            chat_id: 用户的 openid 或群 openid。
            file_url: 文件的 URL。
            chat_type: 聊天类型（"c2c" 或 "group"）。
            reply_to: 回复的消息 ID（可选）。

        Returns:
            发送结果（SendResult）。
        """
        body: dict[str, object] = {
            "msg_type": MSG_TYPE_MEDIA,
            "media": {
                "url": file_url,
                "type": MEDIA_TYPE_FILE,
            },
        }
        if reply_to is not None:
            body["msg_id"] = reply_to

        endpoint: str = (
            f"/v2/users/{chat_id}/messages"
            if chat_type == "c2c"
            else f"/v2/groups/{chat_id}/messages"
        )
        return await self._send_with_retry("POST", endpoint, body)

    # ==================================================================
    # 键盘消息
    # ==================================================================

    async def send_approval_request(
        self,
        chat_type: str,
        chat_id: str,
        req: ApprovalRequest,
        reply_to: str | None = None,
    ) -> bool:
        """发送审批请求消息（带内联键盘）。

        Args:
            chat_type: 聊天类型（"c2c" 或 "group"）。
            chat_id: 用户 openid 或群 openid。
            req: 审批请求数据。
            reply_to: 回复的消息 ID（可选）。

        Returns:
            是否发送成功。
        """
        text: str = build_approval_text(req)
        keyboard: InlineKeyboard = build_approval_keyboard(req.session_key)

        try:
            if chat_type == "c2c":
                await self.send_text_to_c2c(chat_id, text, reply_to, keyboard)
            else:
                await self.send_text_to_group(chat_id, text, reply_to, keyboard)
            logger.info(
                "Approval request sent to %s:%s (session=%.20s...)",
                chat_type, chat_id, req.session_key,
            )
            return True
        except Exception as exc:
            logger.error(
                "Failed to send approval to %s:%s: %s",
                chat_type, chat_id, exc,
            )
            return False

    async def send_typing(self, chat_id: str, chat_type: str = "c2c") -> None:
        """发送正在输入状态指示器。

        Args:
            chat_id: 用户 openid 或群 openid。
            chat_type: 聊天类型（"c2c" 或 "group"）。
        """
        body: dict[str, object] = {
            "msg_type": MSG_TYPE_INPUT_NOTIFY,
            "content": "0",  # 0 = 正在输入
        }
        endpoint: str = (
            f"/v2/users/{chat_id}/messages"
            if chat_type == "c2c"
            else f"/v2/groups/{chat_id}/messages"
        )
        try:
            await self._api_request("POST", endpoint, body)
        except Exception:
            pass  # typing 指示器失败不影响主流程

    # ==================================================================
    # 通用发送（带重试）
    # ==================================================================

    async def _send_with_retry(
        self,
        method: str,
        path: str,
        body: dict[str, object],
        max_retries: int = 3,
    ) -> SendResult:
        """带重试的 API 调用。

        Args:
            method: HTTP 方法。
            path: API 路径。
            body: 请求体。
            max_retries: 最大重试次数（默认 3）。

        Returns:
            发送结果（SendResult）。
        """
        last_error: str = ""

        for attempt in range(max_retries):
            try:
                token: str = await self._token_manager.get_token()
                data: dict[str, object] = await self._api_request(method, path, body, token)
                msg_id: str = str(data.get("id", uuid.uuid4().hex[:12]))
                return SendResult(
                    success=True,
                    message_id=msg_id,
                    raw_response=data,
                )
            except (QQApiError, QQTokenError) as exc:
                error_str: str = str(exc).lower()
                last_error = str(exc)

                # 永久性错误不重试
                if any(k in error_str for k in ("invalid", "forbidden", "not found", "bad request")):
                    return SendResult(success=False, error=str(exc), retryable=False)

                if attempt < max_retries - 1:
                    delay: float = 1.0 * (2.0 ** attempt)
                    logger.warning(
                        "Send retry %d/%d after %.1fs: %s",
                        attempt + 1, max_retries, delay, exc,
                    )
                    await asyncio.sleep(delay)

        return SendResult(success=False, error=last_error, retryable=True)
