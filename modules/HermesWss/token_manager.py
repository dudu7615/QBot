"""Access Token 管理器。

提供带有 singleflight 锁的 QQ Bot access token 获取与自动刷新功能。
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import httpx

from .constants import TOKEN_URL, DEFAULT_API_TIMEOUT
from .exceptions import QQTokenError
from .models import AccessTokenData, TokenResponse
from .utils import get_api_headers, build_user_agent


class TokenManager:
    """QQ Bot Access Token 管理器。

    管理 QQ Bot 机器人的 access token 获取与自动刷新。
    使用 singleflight 模式确保同一时刻只有一个协程发起 token 刷新请求，
    避免多个并发协程同时刷新 token。

    Attributes:
        _app_id: QQ Bot 机器人的 app_id。
        _client_secret: QQ Bot 机器人的 client_secret。
        _http_client: 复用的 httpx.AsyncClient 实例。
        _access_token: 缓存的 access token 字符串，None 表示尚未获取。
        _token_expires_at: 当前 token 的过期时间戳（UNIX 时间），0.0 表示未设置。
        _token_lock: 用于 singleflight 的 asyncio 锁。
    """

    def __init__(
        self,
        app_id: str,
        client_secret: str,
        http_client: httpx.AsyncClient,
    ) -> None:
        """初始化 TokenManager。

        Args:
            app_id: QQ Bot 机器人的 app_id。
            client_secret: QQ Bot 机器人的 client_secret。
            http_client: 复用的 httpx.AsyncClient 实例。
        """
        self._app_id: str = app_id
        self._client_secret: str = client_secret
        self._http_client: httpx.AsyncClient = http_client
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock: asyncio.Lock = asyncio.Lock()

    async def get_token(self) -> str:
        """获取当前有效的 access token。

        如果缓存的 token 仍在有效期内（预留 60 秒缓冲期），直接返回缓存值。
        否则使用 asyncio.Lock 实现 singleflight，确保只有一个协程发起
        实际的 token 刷新请求，其他并发协程等待锁释放后复用刷新结果。

        Returns:
            有效的 access token 字符串。

        Raises:
            QQTokenError: 当网络请求失败、HTTP 状态码异常、响应格式错误、
               或任何其他导致 token 刷新失败的情况时抛出。
        """
        # 快速路径：缓存仍在有效期内（预留 60 秒缓冲期）
        if time.time() < self._token_expires_at - 60:
            assert self._access_token is not None
            return self._access_token

        # 单飞路径：加锁，避免并发刷新
        async with self._token_lock:
            # 二次检查：等待锁期间可能已有其他协程完成了刷新
            if time.time() < self._token_expires_at - 60:
                assert self._access_token is not None
                return self._access_token

            # 执行 token 刷新
            try:
                response: httpx.Response = await self._http_client.post(
                    TOKEN_URL,
                    json={
                        "appId": self._app_id,
                        "clientSecret": self._client_secret,
                    },
                    headers=get_api_headers(),
                    timeout=DEFAULT_API_TIMEOUT,
                )
                response.raise_for_status()
                token_data: TokenResponse = TokenResponse.model_validate_json(
                    response.text,
                )
            except Exception as exc:
                raise QQTokenError(
                    f"Failed to refresh access token: {exc}",
                ) from exc

            self._access_token = token_data.access_token
            self._token_expires_at = time.time() + token_data.expires_in
            return self._access_token
