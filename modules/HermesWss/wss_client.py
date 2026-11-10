"""
HermesWss — QQ Bot WebSocket 客户端。

基于 QQ Bot API v2 的 WebSocket Gateway 协议。
替代官方回调（webhook）方式，通过 WebSocket 长连接实时接收消息。

流程：
  1. 获取 Access Token（自动刷新）
  2. 获取 Gateway URL（/gateway）
  3. 建立 WebSocket 连接
  4. 发送 Identify（op 2）鉴权
  5. 维持心跳（op 1）
  6. 接收 Dispatch（op 0）事件 → 分发到回调

从 Hermes Agent 的 gateway/platforms/qqbot/adapter.py 移植。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Callable

import aiohttp

from .constants import (
    API_BASE,
    CONNECT_TIMEOUT_SECONDS,
    DEFAULT_API_TIMEOUT,
    GATEWAY_URL_PATH,
    MAX_RECONNECT_ATTEMPTS,
    QUICK_DISCONNECT_THRESHOLD,
    MAX_CONCURRENT_HANDLERS,
    MAX_QUICK_DISCONNECT_COUNT,
    RATE_LIMIT_DELAY,
    SHUTDOWN_GRACE_SECONDS,
    RECONNECT_BACKOFF,
    TOKEN_URL,
    WSOpCode,
    WSCloseCode,
)
from .exceptions import QQCloseError, QQTokenError
from .models import (
    QQMessage,
    QQMessageAuthor,
    InteractionEvent,
    OnMessageCallback,
    OnInteractionCallback,
    WSPayload,
)
from .token_manager import TokenManager
from .utils import build_user_agent, get_api_headers


logger = logging.getLogger(__name__)


class QQWebSocketClient:
    """QQ Bot WebSocket 客户端。

    管理与 QQ Bot Gateway 的 WebSocket 长连接，
    自动处理鉴权、心跳、重连、消息去重。

    Attributes:
        app_id: 机器人的 app_id。
        client_secret: 机器人的 client_secret。
        on_message: 收到消息时的回调函数。
        on_interaction: 收到按钮交互事件时的回调函数。
        running: 客户端是否正在运行。
    """

    def __init__(
        self,
        app_id: str,
        client_secret: str,
        on_message: OnMessageCallback | None = None,
        on_interaction: OnInteractionCallback | None = None,
    ) -> None:
        """初始化 WebSocket 客户端。

        Args:
            app_id: QQ Bot 的 app_id。
            client_secret: QQ Bot 的 client_secret。
            on_message: 收到 C2C/GROUP_AT 消息时的异步回调。
                回调签名：async def callback(msg: QQMessage) -> None
            on_interaction: 收到按钮交互事件时的异步回调。
                回调签名：async def callback(event: InteractionEvent) -> None
        """
        self.app_id: str = app_id
        self.client_secret: str = client_secret
        self.on_message: OnMessageCallback | None = on_message
        self.on_interaction: OnInteractionCallback | None = on_interaction

        # 内部状态
        self.running: bool = False

        # HTTP 客户端（用于 token、gateway URL、REST API）
        self._http_client: aiohttp.ClientSession | None = None

        # WebSocket 状态
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_session: aiohttp.ClientSession | None = None
        self._session_id: str | None = None
        self._last_seq: int | None = None
        self._heartbeat_interval: float = 30.0

        # Token 管理
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock: asyncio.Lock = asyncio.Lock()

        # 异步任务
        self._listen_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None

        # 消息去重
        self._seen_msg_ids: set[str] = set()
        self._dedup_lock: asyncio.Lock = asyncio.Lock()

        # 不可恢复的断开时置位，供上层感知客户端已停止
        self.stopped: asyncio.Event = asyncio.Event()

        # 消息处理任务：回调放入独立任务执行，避免阻塞读循环
        self._dispatch_tasks: set[asyncio.Task[None]] = set()
        self._dispatch_semaphore: asyncio.Semaphore = asyncio.Semaphore(
            MAX_CONCURRENT_HANDLERS
        )

    # ==================================================================
    # 主生命周期
    # ==================================================================

    async def start(self) -> bool:
        """启动客户端，建立 WebSocket 连接。

        Returns:
            连接是否成功建立。
        """
        self.running = True

        # 创建 HTTP 客户端
        if self._http_client is None:
            self._http_client = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=DEFAULT_API_TIMEOUT),
            )

        try:
            # 1. 获取 access token
            token: str = await self._ensure_token()

            # 2. 获取 gateway URL
            gateway_url: str = await self._get_gateway_url()

            # 3. 打开 WebSocket
            await self._open_ws(gateway_url)

            # 4. 启动监听和心跳
            self._listen_task = asyncio.create_task(self._listen_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info("[QQBot] Connected to gateway: %s", gateway_url)
            return True

        except Exception as exc:
            logger.error("[QQBot] Startup failed: %s", exc, exc_info=True)
            await self._cleanup()
            self.running = False
            return False

    async def stop(self) -> None:
        """停止客户端，断开所有连接。"""
        self.running = False

        # 等待进行中的消息处理结束，超时后取消
        if self._dispatch_tasks:
            pending: set[asyncio.Task[None]] = set(self._dispatch_tasks)
            done, still_pending = await asyncio.wait(
                pending, timeout=SHUTDOWN_GRACE_SECONDS
            )
            for task in still_pending:
                task.cancel()
            if still_pending:
                await asyncio.gather(*still_pending, return_exceptions=True)
            logger.info(
                "[QQBot] Dispatch drained: %d done, %d cancelled",
                len(done),
                len(still_pending),
            )

        if self._listen_task is not None:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        await self._cleanup()
        logger.info("[QQBot] Stopped")

    # ==================================================================
    # Token 管理
    # ==================================================================

    async def _ensure_token(self) -> str:
        """获取有效的 access token，过期时自动刷新（带 singleflight 锁）。

        Returns:
            有效的 access token 字符串。

        Raises:
            QQTokenError: Token 获取失败。
        """
        if self._access_token is not None and time.time() < self._token_expires_at - 60:
            return self._access_token

        async with self._token_lock:
            if self._access_token is not None and time.time() < self._token_expires_at - 60:
                return self._access_token

            try:
                if self._http_client is None:
                    raise QQTokenError("HTTP client not initialized")

                headers: dict[str, str] = get_api_headers()
                body: dict[str, str] = {
                    "appId": self.app_id,
                    "clientSecret": self.client_secret,
                }
                async with self._http_client.post(
                    TOKEN_URL,
                    json=body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=DEFAULT_API_TIMEOUT),
                ) as response:
                    if response.status != 200:
                        text: str = await response.text()
                        raise QQTokenError(
                            f"Token API failed (status={response.status}): {text[:200]}"
                        )
                    data: dict[str, object] = await response.json()

                token_obj: object = data.get("access_token")
                if token_obj is None:
                    raise QQTokenError(f"Token response missing access_token: {data}")
                self._access_token = str(token_obj)

                expires_in_obj: object = data.get("expires_in", 7200)
                expires_in: int = int(expires_in_obj) if isinstance(expires_in_obj, (int, float)) else 7200
                self._token_expires_at = time.time() + expires_in

                logger.info("[QQBot] Access token refreshed, expires in %ds", expires_in)
                return self._access_token

            except QQTokenError:
                raise
            except Exception as exc:
                raise QQTokenError(f"Failed to get access token: {exc}") from exc

    async def _get_gateway_url(self) -> str:
        """获取 WebSocket Gateway URL（调用 /gateway 接口）。

        Returns:
            WebSocket 网关 URL。

        Raises:
            RuntimeError: 获取失败。
        """
        token: str = await self._ensure_token()
        if self._http_client is None:
            raise RuntimeError("HTTP client not initialized")

        headers: dict[str, str] = {
            "Authorization": f"QQBot {token}",
            "User-Agent": build_user_agent(),
        }
        url: str = f"{API_BASE}{GATEWAY_URL_PATH}"

        async with self._http_client.get(
            url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=DEFAULT_API_TIMEOUT),
        ) as response:
            if response.status != 200:
                text: str = await response.text()
                raise RuntimeError(
                    f"Gateway URL API failed (status={response.status}): {text[:200]}"
                )
            data: dict[str, object] = await response.json()

        url_obj: object = data.get("url")
        if not isinstance(url_obj, str) or not url_obj:
            raise RuntimeError(f"Gateway response missing url: {data}")
        return str(url_obj)

    # ==================================================================
    # WebSocket 连接
    # ==================================================================

    async def _open_ws(self, gateway_url: str) -> None:
        """打开 WebSocket 连接到 QQ Bot Gateway。

        Args:
            gateway_url: 从 /gateway 获取的 WSS URL。

        Raises:
            RuntimeError: 连接失败。
        """
        # 清理旧的 WebSocket 资源
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        if self._ws_session is not None and not self._ws_session.closed:
            await self._ws_session.close()
        self._ws_session = None

        # 创建新的 session 并连接
        self._ws_session = aiohttp.ClientSession(trust_env=True)
        headers: dict[str, str] = {
            "User-Agent": build_user_agent(),
        }

        if self._ws_session is None:
            raise RuntimeError("WebSocket session not initialized")

        try:
            self._ws = await self._ws_session.ws_connect(
                gateway_url,
                headers=headers,
                timeout=aiohttp.ClientWSTimeout(
                    ws_close=CONNECT_TIMEOUT_SECONDS,
                ),
            )
            logger.info("[QQBot] WebSocket connected to %s", gateway_url)
        except Exception as exc:
            self._ws = None
            raise RuntimeError(f"WebSocket connection failed: {exc}") from exc

    async def _cleanup(self) -> None:
        """清理所有连接资源。"""
        # 清理 WebSocket
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        self._ws = None

        # 清理 WebSocket session
        if self._ws_session is not None and not self._ws_session.closed:
            await self._ws_session.close()
        self._ws_session = None

        # 清理 HTTP client
        if self._http_client is not None and not self._http_client.closed:
            await self._http_client.close()
        self._http_client = None

    # ==================================================================
    # 监听循环
    # ==================================================================

    async def _listen_loop(self) -> None:
        """WebSocket 监听主循环。

        读取 WebSocket 事件，处理断开重连。
        关闭码处理逻辑：
          4004 → token 无效，刷新并重连
          4006/4007 → session 失效，清除后重新 identify
          4008 → 被限流，等待后重连
          4009 → 连接超时，可 resume
          4914/4915 → 致命错误，停止重连
        """
        backoff_idx: int = 0
        connect_time: float = 0.0
        quick_disconnect_count: int = 0

        while self.running:
            try:
                connect_time = time.monotonic()
                await self._read_events()
                # 正常退出循环（_read_events 返回）→ 重置退避
                backoff_idx = 0
                quick_disconnect_count = 0
            except asyncio.CancelledError:
                return
            except QQCloseError as exc:
                if not self.running:
                    return

                code: int | None = exc.code
                reason_str: str = exc.reason if exc.reason is not None else ""
                logger.warning(
                    "[QQBot] WebSocket closed: code=%s reason=%s",
                    code, reason_str,
                )

                # 快速断连检测（配置错误 / 权限问题）
                duration: float = time.monotonic() - connect_time
                if duration < QUICK_DISCONNECT_THRESHOLD and connect_time > 0:
                    quick_disconnect_count += 1
                    logger.info(
                        "[QQBot] Quick disconnect (%.1fs), count: %d",
                        duration, quick_disconnect_count,
                    )
                    if quick_disconnect_count >= MAX_QUICK_DISCONNECT_COUNT:
                        logger.error(
                            "[QQBot] Too many quick disconnects. "
                            "Check: 1) AppID/Secret 2) Bot permissions on QQ Open Platform"
                        )
                        self._mark_stopped()
                        return
                else:
                    quick_disconnect_count = 0

                # 致命关闭码 → 停止重连
                if code is not None:
                    try:
                        close_code: WSCloseCode = WSCloseCode(code)
                        if close_code.is_fatal:
                            logger.error(
                                "[QQBot] %s. Stop reconnecting.",
                                close_code.description,
                            )
                            self._mark_stopped()
                            return
                        if close_code == WSCloseCode.AUTHENTICATION_FAILED:
                            # 4004: token 无效，清除 token 缓存
                            self._access_token = None
                            self._token_expires_at = 0.0
                            logger.info("[QQBot] Token invalid (4004), will refresh")
                        elif close_code.is_session_invalid:
                            # session 失效，清除 session 重新 identify
                            self._session_id = None
                            self._last_seq = None
                            logger.info(
                                "[QQBot] Session error (%d), clearing session",
                                code,
                            )
                        elif close_code == WSCloseCode.RATE_LIMITED:
                            # 4008: 被限流
                            logger.info("[QQBot] Rate limited (4008), waiting %ds", RATE_LIMIT_DELAY)
                            await asyncio.sleep(RATE_LIMIT_DELAY)
                            if await self._reconnect(backoff_idx):
                                backoff_idx = 0
                                quick_disconnect_count = 0
                            else:
                                backoff_idx += 1
                            continue
                    except ValueError:
                        pass  # 未知关闭码，继续重连

                # 通用重连
                if await self._reconnect(backoff_idx):
                    backoff_idx = 0
                    quick_disconnect_count = 0
                else:
                    backoff_idx += 1
                    if backoff_idx >= MAX_RECONNECT_ATTEMPTS:
                        logger.error("[QQBot] Max reconnect attempts reached")
                        self._mark_stopped()
                        return

            except Exception as exc:
                if not self.running:
                    return
                logger.warning("[QQBot] WebSocket error: %s", exc)

                if backoff_idx >= MAX_RECONNECT_ATTEMPTS:
                    logger.error("[QQBot] Max reconnect attempts reached")
                    self._mark_stopped()
                    return

                if await self._reconnect(backoff_idx):
                    backoff_idx = 0
                    quick_disconnect_count = 0
                else:
                    backoff_idx += 1

    def _mark_stopped(self) -> None:
        """标记客户端已不可恢复地停止，并唤醒等待方。"""
        self.running = False
        self.stopped.set()

    async def _reconnect(self, backoff_idx: int) -> bool:
        """尝试重连 WebSocket。

        Args:
            backoff_idx: 当前退避索引。

        Returns:
            是否重连成功。
        """
        delay: float = RECONNECT_BACKOFF[
            min(backoff_idx, len(RECONNECT_BACKOFF) - 1)
        ]
        logger.info(
            "[QQBot] Reconnecting in %.1fs (attempt %d)...",
            delay, backoff_idx + 1,
        )
        await asyncio.sleep(delay)

        self._heartbeat_interval = 30.0
        try:
            await self._ensure_token()
            gateway_url: str = await self._get_gateway_url()
            await self._open_ws(gateway_url)
            logger.info("[QQBot] Reconnected")
            return True
        except Exception as exc:
            logger.warning("[QQBot] Reconnect failed: %s", exc)
            return False

    async def _read_events(self) -> None:
        """读取 WebSocket 帧直到连接关闭。

        Raises:
            RuntimeError: WebSocket 未连接。
            QQCloseError: 服务端主动关闭连接。
        """
        if self._ws is None:
            raise RuntimeError("WebSocket not connected")
        if self._ws.closed:
            raise RuntimeError("WebSocket closed")

        while self.running and self._ws is not None and not self._ws.closed:
            msg: aiohttp.WSMessage = await self._ws.receive()

            if msg.type == aiohttp.WSMsgType.TEXT:
                payload: WSPayload | None = self._parse_payload(msg.data)
                if payload is not None:
                    await self._dispatch_payload(payload)

            elif msg.type == aiohttp.WSMsgType.PING:
                # aiohttp 自动回复 PONG
                pass

            elif msg.type == aiohttp.WSMsgType.CLOSE:
                extra_str: str = msg.extra if isinstance(msg.extra, str) else ""
                raise QQCloseError(msg.data, extra_str)

            elif msg.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                raise RuntimeError("WebSocket closed")

    # ==================================================================
    # 心跳
    # ==================================================================

    async def _heartbeat_loop(self) -> None:
        """心跳循环。

        根据 Hello 事件返回的 interval 定时发送 op 1 心跳。
        """
        try:
            while self.running:
                await asyncio.sleep(self._heartbeat_interval)
                if self._ws is None or self._ws.closed:
                    continue
                try:
                    await self._ws.send_json({"op": WSOpCode.HEARTBEAT, "d": self._last_seq})
                except Exception as exc:
                    logger.debug("[QQBot] Heartbeat failed: %s", exc)
        except asyncio.CancelledError:
            pass

    # ==================================================================
    # 消息处理
    # ==================================================================

    async def send_text(
        self,
        text: str,
        channel_type: str = "c2c",
        chat_id: str = "",
    ) -> None:
        """发送文字消息到 QQ（通过 REST API）。

        注意：此方法使用 aiohttp 的 HTTP 客户端，
        调用前请确保 start() 已成功执行。

        Args:
            text: 消息文本。
            channel_type: 频道类型（"c2c" 或 "group"）。
            chat_id: 目标 ID（user_openid 或 group_openid）。
        """
        token: str = await self._ensure_token()
        if self._http_client is None:
            logger.error("[QQBot] Cannot send: HTTP client not initialized")
            return

        endpoint: str = (
            f"/v2/users/{chat_id}/messages"
            if channel_type == "c2c"
            else f"/v2/groups/{chat_id}/messages"
        )
        url: str = f"{API_BASE}{endpoint}"
        headers: dict[str, str] = {
            "Authorization": f"QQBot {token}",
            "Content-Type": "application/json",
        }
        body: dict[str, object] = {
            "content": text,
            "msg_type": 0,
        }

        async with self._http_client.post(url, json=body, headers=headers) as response:
            if response.status != 200:
                resp_text: str = await response.text()
                logger.warning("[QQBot] Send failed (status=%d): %s", response.status, resp_text[:200])

    # ==================================================================
    # 事件派发
    # ==================================================================

    async def _dispatch_payload(self, payload: WSPayload) -> None:
        """派发 WebSocket 事件。

        Args:
            payload: 解析后的 WebSocket 协议帧。
        """
        op: int = payload.op
        event_type: str | None = payload.t
        seq: int | None = payload.s
        data: object | None = payload.d

        # 更新序列号
        if seq is not None and (self._last_seq is None or seq > self._last_seq):
            self._last_seq = seq

        # op 10 = Hello（心跳间隔）
        if op == WSOpCode.HELLO and isinstance(data, dict):
            interval_ms_obj: object = data.get("heartbeat_interval", 30000)
            interval_ms: int = (
                int(interval_ms_obj)
                if isinstance(interval_ms_obj, (int, float))
                else 30000
            )
            self._heartbeat_interval = interval_ms / 1000.0 * 0.8
            logger.debug(
                "[QQBot] Hello received, heartbeat_interval=%dms",
                interval_ms,
            )

            # 鉴权：有 session 则 Resume，否则 Identify
            if self._session_id is not None and self._last_seq is not None:
                await self._send_resume()
            else:
                await self._send_identify()
            return

        # op 0 = Dispatch
        if op == WSOpCode.DISPATCH and event_type is not None:
            if event_type == "READY" and isinstance(data, dict):
                session_id_obj: object = data.get("session_id")
                if isinstance(session_id_obj, str):
                    self._session_id = session_id_obj
                logger.info("[QQBot] Ready, session_id=%s", self._session_id)

            elif event_type == "RESUMED":
                logger.info("[QQBot] Session resumed")

            elif event_type in {
                "C2C_MESSAGE_CREATE",
                "GROUP_AT_MESSAGE_CREATE",
                "GROUP_MESSAGE_CREATE",
                "DIRECT_MESSAGE_CREATE",
            } and isinstance(data, dict):
                await self._on_message(event_type, data, payload.id or "")

            elif event_type == "INTERACTION_CREATE" and isinstance(data, dict):
                await self._on_interaction(data)

            return

        # op 11 = Heartbeat ACK
        if op == WSOpCode.HEARTBEAT_ACK:
            return

        # op 7 = Server Reconnect
        if op == WSOpCode.RECONNECT:
            logger.info("[QQBot] Server requested reconnect (op 7)")
            if self._ws is not None and not self._ws.closed:
                await self._ws.close()
            return

        # op 9 = Invalid Session
        if op == WSOpCode.INVALID_SESSION:
            resumable: bool = bool(data) if data is not None else False
            if not resumable:
                logger.info("[QQBot] Invalid session (op 9), clearing")
                self._session_id = None
                self._last_seq = None
            else:
                logger.info("[QQBot] Invalid session (op 9, resumable)")
            if self._ws is not None and not self._ws.closed:
                await self._ws.close()
            return

    async def _send_identify(self) -> None:
        """发送 op 2 Identify 鉴权。

        在收到 op 10 Hello 后调用。
        """
        token: str = await self._ensure_token()
        payload: dict[str, object] = {
            "op": WSOpCode.IDENTIFY,
            "d": {
                "token": f"QQBot {token}",
                "intents": (1 << 25) | (1 << 30) | (1 << 12) | (1 << 26),
                "shard": [0, 1],
                "properties": {
                    "$os": "linux",
                    "$browser": "hermeswss",
                    "$device": "hermeswss",
                },
            },
        }

        if self._ws is not None and not self._ws.closed:
            await self._ws.send_json(payload)
            logger.info("[QQBot] Identify sent")
        else:
            logger.warning("[QQBot] Cannot identify: WebSocket not connected")

    async def _send_resume(self) -> None:
        """发送 op 6 Resume 恢复连接。

        在重连后发送，恢复之前的 session。
        """
        token: str = await self._ensure_token()
        payload: dict[str, object] = {
            "op": WSOpCode.RESUME,
            "d": {
                "token": f"QQBot {token}",
                "session_id": self._session_id,
                "seq": self._last_seq,
            },
        }

        if self._ws is not None and not self._ws.closed:
            await self._ws.send_json(payload)
            logger.info(
                "[QQBot] Resume sent (session_id=%s, seq=%s)",
                self._session_id, self._last_seq,
            )
        else:
            logger.warning("[QQBot] Cannot resume: WebSocket not connected")

    # ==================================================================
    # 消息处理
    # ==================================================================

    async def _on_message(
        self,
        event_type: str,
        data: dict[str, object],
        event_id: str = "",
    ) -> None:
        """处理收到的消息事件。

        Args:
            event_type: 事件类型（C2C_MESSAGE_CREATE / GROUP_AT_MESSAGE_CREATE 等）。
            data: 消息数据字典。
        """
        # 提取消息 ID
        msg_id_obj: object = data.get("id", "")
        msg_id: str = str(msg_id_obj) if msg_id_obj is not None else ""
        if not msg_id:
            return

        # 消息去重
        async with self._dedup_lock:
            if msg_id in self._seen_msg_ids:
                logger.debug("[QQBot] Duplicate message: %s", msg_id)
                return
            self._seen_msg_ids.add(msg_id)
            # 限制去重集合大小
            if len(self._seen_msg_ids) > 1000:
                self._seen_msg_ids = set(list(self._seen_msg_ids)[-500:])

        # 解析消息内容
        content_obj: object = data.get("content", "")
        content: str = str(content_obj).strip() if content_obj is not None else ""

        timestamp_obj: object = data.get("timestamp", "")
        timestamp: str = str(timestamp_obj) if timestamp_obj is not None else ""

        # 解析作者
        author_data: object = data.get("author")
        author: QQMessageAuthor = QQMessageAuthor()
        if isinstance(author_data, dict):
            author = QQMessageAuthor(
                id=str(author_data.get("id", "") or ""),
                user_openid=str(author_data.get("user_openid", "") or ""),
                union_openid=str(author_data.get("union_openid", "") or ""),
                member_openid=str(author_data.get("member_openid", "") or ""),
            )

        # 构造 QQMessage
        msg: QQMessage = QQMessage(
            id=msg_id,
            content=content,
            timestamp=timestamp,
            author=author,
            event_type=event_type,
            event_id=event_id,
            raw=data,
        )

        # 提取场景相关的 openid
        if event_type == "C2C_MESSAGE_CREATE":
            author_raw: object = data.get("author", {})
            if isinstance(author_raw, dict):
                uoid: object = author_raw.get("user_openid")
                if isinstance(uoid, str):
                    msg.user_openid = uoid

        elif event_type in {"GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"}:
            group_openid_raw: object = data.get("group_openid")
            if isinstance(group_openid_raw, str):
                msg.group_openid = group_openid_raw

            # 群成员 openid 在事件顶层或 author.member_openid 中都可能出现，
            # 顶层缺失时回退到 author，避免发送者身份被误判成群 openid
            member_openid_raw: object = data.get("group_member_openid")
            member_openid: str = (
                member_openid_raw
                if isinstance(member_openid_raw, str) and member_openid_raw
                else (msg.author.member_openid if msg.author is not None else "") or ""
            )
            if member_openid:
                msg.group_member_openid = member_openid
                if msg.author is not None:
                    msg.author.member_openid = member_openid

        # 触发回调：放入独立任务，避免慢插件阻塞读循环与心跳
        if self.on_message is not None:
            task: asyncio.Task[None] = asyncio.create_task(
                self._dispatch_message(msg)
            )
            self._dispatch_tasks.add(task)
            task.add_done_callback(self._dispatch_tasks.discard)

    async def _dispatch_message(self, msg: QQMessage) -> None:
        """处理一条消息，异常只记录不向外抛。

        Args:
            msg: 收到的消息。
        """
        assert self.on_message is not None
        async with self._dispatch_semaphore:
            try:
                await self.on_message(msg)
            except Exception as exc:
                logger.error(
                    "[QQBot] Message callback error: %s", exc, exc_info=True
                )

    async def _on_interaction(self, data: dict[str, object]) -> None:
        """处理按钮交互事件（INTERACTION_CREATE）。

        Args:
            data: 交互事件数据字典。
        """
        data_raw: object = data.get("data", {})
        resolved: object = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
        if isinstance(data_raw, dict):
            resolved = data_raw.get("resolved", {}) if isinstance(data_raw.get("resolved"), dict) else {}

        scene_code: int = 0
        scene_code_obj: object = data.get("chat_type", 0)
        if isinstance(scene_code_obj, int):
            scene_code = scene_code_obj

        scene_map: dict[int, str] = {0: "guild", 1: "group", 2: "c2c"}
        scene: str = scene_map.get(scene_code, "")

        button_data_obj: object = resolved.get("button_data", "") if isinstance(resolved, dict) else ""
        if isinstance(resolved, dict):
            bd: object = resolved.get("button_data", "")
            button_data_str: str = str(bd) if bd is not None else ""
        else:
            button_data_str = ""

        button_id_obj: object = resolved.get("button_id", "") if isinstance(resolved, dict) else ""
        if isinstance(resolved, dict):
            bid: object = resolved.get("button_id", "")
            button_id_str: str = str(bid) if bid is not None else ""
        else:
            button_id_str = ""

        type_value: int = 0
        type_raw: object = data.get("type", 0)
        if isinstance(type_raw, (int, float)):
            type_value = int(type_raw)
        event: InteractionEvent = InteractionEvent(
            id=str(data.get("id", "") or ""),
            type=type_value,
            chat_type=scene_code,
            scene=scene,
            group_openid=str(data.get("group_openid", "") or ""),
            group_member_openid=str(data.get("group_member_openid", "") or ""),
            user_openid=str(data.get("user_openid", "") or ""),
            button_data=button_data_str,
            button_id=button_id_str,
        )

        if self.on_interaction is not None:
            try:
                await self.on_interaction(event)
            except Exception as exc:
                logger.error("[QQBot] Interaction callback error: %s", exc, exc_info=True)

    # ==================================================================
    # 工具方法
    # ==================================================================

    @staticmethod
    def _parse_payload(raw_data: str) -> WSPayload | None:
        """解析 JSON 字符串为 WSPayload。

        Args:
            raw_data: 原始 JSON 字符串。

        Returns:
            解析后的 WSPayload，解析失败返回 None。
        """
        try:
            data: dict[str, object] = json.loads(raw_data)
        except json.JSONDecodeError as exc:
            logger.warning("[QQBot] Failed to parse JSON: %s", exc)
            return None

        op_obj: object = data.get("op", 0)
        op: int = int(op_obj) if isinstance(op_obj, (int, float)) else 0

        seq: int | None = None
        seq_obj: object = data.get("s")
        if isinstance(seq_obj, int):
            seq = seq_obj

        t: str | None = None
        t_obj: object = data.get("t")
        if isinstance(t_obj, str):
            t = t_obj

        event_id: str | None = None
        id_obj: object = data.get("id")
        if isinstance(id_obj, str):
            event_id = id_obj

        return WSPayload(
            op=op,
            d=data.get("d"),
            s=seq,
            t=t,
            id=event_id,
        )
