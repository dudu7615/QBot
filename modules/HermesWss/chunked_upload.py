"""
HermesWss — QQ Bot 大文件分片上传器。

QQ v2 API 对 inline base64 上传（file_data / url）限制约 10 MB。
10 MB ~ 100 MB 的文件需使用三步分片上传流程：
  1. POST /v2/{users|groups}/{id}/upload_prepare → upload_id + 签名 URL
  2. PUT 分片到签名 COS URL → 标记完成
  3. POST /v2/{users|groups}/{id}/files 获取 file_info token

从 Hermes Agent 的 gateway/platforms/qqbot/chunked_upload.py 移植。
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Callable

import httpx

from .constants import API_BASE, FILE_UPLOAD_TIMEOUT, DEFAULT_API_TIMEOUT
from .exceptions import UploadDailyLimitExceededError, UploadFileTooLargeError, UploadError
from .models import UploadPrepareResponse, UploadPartFinishResponse, UploadCompleteResponse
from .token_manager import TokenManager
from .utils import get_api_headers

from modules.Logger import logger


# ── 业务错误码 ──────────────────────────────────────────────────────
_BIZ_CODE_DAILY_LIMIT: int = 40093002
_BIZ_CODE_PART_RETRYABLE: int = 40093001

# ── 分片上传参数 ────────────────────────────────────────────────────
_DEFAULT_CONCURRENT_PARTS: int = 1
_MAX_CONCURRENT_PARTS: int = 10

_PART_UPLOAD_TIMEOUT: float = 300.0
_PART_UPLOAD_MAX_RETRIES: int = 2
_PART_FINISH_RETRY_INTERVAL: float = 1.0
_PART_FINISH_DEFAULT_TIMEOUT: float = 120.0
_PART_FINISH_MAX_TIMEOUT: float = 600.0

_COMPLETE_UPLOAD_MAX_RETRIES: int = 2
_COMPLETE_UPLOAD_BASE_DELAY: float = 2.0

# 分片上传的大小上限（QQ API 规范：10 MB ~ 100 MB）
_MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024

# 前 10,002,432 字节用于 md5_10m 哈希（QQ API 规范）
_MD5_10M_SIZE: int = 10_002_432


class ChunkedUploader:
    """QQ Bot 大文件分片上传器。

    处理 10 MB ~ 100 MB 文件的三步分片上传流程。
    自动处理 token 刷新、断点续传（分片级重试）、配额检测。

    Attributes:
        api_base: API 基础 URL。
        http_client: HTTP 客户端。
        token_manager: Token 管理器。
    """

    def __init__(
        self,
        app_id: str,
        client_secret: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """初始化分片上传器。

        Args:
            app_id: QQ Bot 的 app_id。
            client_secret: QQ Bot 的 client_secret。
            http_client: 可选的 httpx 客户端。未提供时内部创建。
        """
        self.api_base: str = API_BASE
        self.http_client: httpx.AsyncClient = http_client or httpx.AsyncClient(
            timeout=FILE_UPLOAD_TIMEOUT,
            follow_redirects=True,
        )
        self.token_manager: TokenManager = TokenManager(
            app_id, client_secret, self.http_client,
        )

    async def _get_auth_headers(self) -> dict[str, str]:
        """获取含 Authorization 的 HTTP 头。

        Returns:
            含 token 的请求头字典。
        """
        token: str = await self.token_manager.get_token()
        headers: dict[str, str] = get_api_headers()
        headers["Authorization"] = f"QQBot {token}"
        return headers

    async def upload_file(
        self,
        chat_id: str,
        file_path: str,
        chat_type: str = "c2c",
        concurrent_parts: int = _DEFAULT_CONCURRENT_PARTS,
    ) -> UploadCompleteResponse:
        """上传文件（完整三步流程）。

        Args:
            chat_id: 用户 openid 或群 openid。
            file_path: 本地文件路径。
            chat_type: 聊天类型（"c2c" 或 "group"）。
            concurrent_parts: 并发上传分片数（默认 1，最大 10）。

        Returns:
            上传完成响应（含 file_info token）。

        Raises:
            UploadDailyLimitExceededError: 日配额超限。
            UploadFileTooLargeError: 文件超过大小上限。
            UploadError: 上传过程出错。
        """
        file_path_obj: Path = Path(file_path)
        if not file_path_obj.exists():
            raise UploadError(f"File not found: {file_path}")

        file_size: int = file_path_obj.stat().st_size
        file_name: str = file_path_obj.name

        if file_size > _MAX_UPLOAD_BYTES:
            raise UploadFileTooLargeError(
                file_name, file_size, _MAX_UPLOAD_BYTES,
            )

        # 计算 md5_10m（QQ API 要求）
        md5_10m: str = self._compute_md5_10m(file_path_obj)

        # Step 1: upload_prepare
        prepare: UploadPrepareResponse = await self._upload_prepare(
            chat_id, chat_type, file_name, file_size, md5_10m,
        )

        block_size: int = prepare.block_size
        upload_urls: list[str] = prepare.upload_urls

        if block_size <= 0:
            raise UploadError(
                f"upload_prepare 返回了非法的 block_size: {block_size}"
            )

        expected_parts: int = (file_size + block_size - 1) // block_size
        if expected_parts != len(upload_urls):
            raise UploadError(
                f"Part count mismatch: {expected_parts} parts vs "
                f"{len(upload_urls)} upload URLs"
            )

        # Step 2: 逐片读取文件并上传，避免把整个大文件读入内存
        concurrent: int = min(concurrent_parts, _MAX_CONCURRENT_PARTS)
        if concurrent > 1:
            await self._upload_parts_concurrent(
                file_path_obj, block_size, upload_urls, concurrent,
            )
        else:
            await self._upload_parts_sequential(
                file_path_obj, block_size, upload_urls,
            )

        # Step 3: complete upload
        result: UploadCompleteResponse = await self._complete_upload(
            chat_id, chat_type, prepare.upload_id,
        )
        # file_info 是可复用的富媒体 token，不写入持久化日志
        logger.info(
            f"Upload complete: {file_name} ({file_size} bytes) → file_info 已获取"
        )
        return result

    async def _upload_prepare(
        self,
        chat_id: str,
        chat_type: str,
        file_name: str,
        file_size: int,
        md5_10m: str,
    ) -> UploadPrepareResponse:
        """Step 1: 调用 upload_prepare 获取上传凭证。

        Args:
            chat_id: 用户 openid 或群 openid。
            chat_type: 聊天类型。
            file_name: 文件名。
            file_size: 文件大小（字节）。
            md5_10m: 文件前 10MB 的 md5。

        Returns:
            UploadPrepareResponse。

        Raises:
            UploadDailyLimitExceededError: 日配额超限。
            UploadError: 其他错误。
        """
        headers: dict[str, str] = await self._get_auth_headers()
        endpoint: str = (
            f"/v2/users/{chat_id}/upload_prepare"
            if chat_type == "c2c"
            else f"/v2/groups/{chat_id}/upload_prepare"
        )
        url: str = f"{self.api_base}{endpoint}"

        body: dict[str, object] = {
            "file_name": file_name,
            "file_size": file_size,
            "md5_10m": md5_10m,
            "sdk_version": "1.0.0",
        }

        response: httpx.Response = await self.http_client.post(
            url, json=body, headers=headers,
        )

        if response.status_code != 200:
            err_body: str = response.text
            # 检查日配额超限（biz_code 在响应体 JSON 中）
            try:
                err_json: dict[str, object] = response.json()
                biz_code: object = err_json.get("biz_code", 0)
                if biz_code == _BIZ_CODE_DAILY_LIMIT:
                    raise UploadDailyLimitExceededError(file_name, file_size)
            except Exception:
                pass
            raise UploadError(
                f"upload_prepare failed (status={response.status_code}): {err_body[:200]}"
            )

        data: dict[str, object] = response.json()
        upload_id_obj: object = data.get("upload_id", "")
        block_size_obj: object = data.get("block_size", 0)
        upload_urls_obj: object = data.get("upload_urls", [])

        upload_id_str: str = str(upload_id_obj) if upload_id_obj is not None else ""
        block_size_int: int = 0
        if isinstance(block_size_obj, (int, float)):
            block_size_int = int(block_size_obj)
        upload_urls_list: list[str] = (
            [str(u) for u in upload_urls_obj]
            if isinstance(upload_urls_obj, (list, tuple))
            else []
        )

        return UploadPrepareResponse(
            upload_id=upload_id_str,
            block_size=block_size_int,
            upload_urls=upload_urls_list,
        )

    async def _upload_parts_sequential(
        self,
        file_path: Path,
        block_size: int,
        upload_urls: list[str],
    ) -> None:
        """Step 2a: 顺序上传分片。

        Args:
            file_path: 待上传文件。
            block_size: 每片大小（字节）。
            upload_urls: 预签名的 COS URL 列表。

        Raises:
            UploadError: 上传失败。
        """
        with open(file_path, "rb") as file:
            for idx, cos_url in enumerate(upload_urls):
                part_data: bytes = file.read(block_size)
                if not part_data:
                    raise UploadError(f"文件在分片 {idx + 1} 处提前结束")
                await self._upload_single_part(part_data, cos_url, idx + 1)

    async def _upload_parts_concurrent(
        self,
        file_path: Path,
        block_size: int,
        upload_urls: list[str],
        concurrent: int,
    ) -> None:
        """Step 2b: 并发上传分片。

        Args:
            file_path: 待上传文件。
            block_size: 每片大小（字节）。
            upload_urls: 预签名的 COS URL 列表。
            concurrent: 同时上传的分片数。

        Raises:
            UploadError: 任一上传失败。
        """
        semaphore: asyncio.Semaphore = asyncio.Semaphore(concurrent)
        parts: list[bytes] = []
        with open(file_path, "rb") as file:
            while True:
                chunk: bytes = file.read(block_size)
                if not chunk:
                    break
                parts.append(chunk)

        if len(parts) != len(upload_urls):
            raise UploadError(
                f"Part count mismatch: {len(parts)} parts vs "
                f"{len(upload_urls)} upload URLs"
            )

        async def _send(part_data: bytes, cos_url: str, index: int) -> None:
            async with semaphore:
                await self._upload_single_part(part_data, cos_url, index)

        tasks: list[asyncio.Task[None]] = [
            asyncio.create_task(_send(part_data, cos_url, idx + 1))
            for idx, (part_data, cos_url) in enumerate(zip(parts, upload_urls))
        ]

        results: list[None | BaseException] = await asyncio.gather(
            *tasks, return_exceptions=True,
        )

        for result in results:
            if isinstance(result, BaseException):
                raise UploadError(f"Concurrent upload failed: {result}") from result

    async def _upload_single_part(
        self,
        part_data: bytes,
        cos_url: str,
        part_number: int,
    ) -> None:
        """上传单个分片到 COS。

        Args:
            part_data: 分片字节数据。
            cos_url: 预签名的 COS 上传 URL。
            part_number: 分片序号。

        Raises:
            UploadError: 上传失败。
        """
        last_error: str = ""
        for attempt in range(_PART_UPLOAD_MAX_RETRIES + 1):
            try:
                response: httpx.Response = await self.http_client.put(
                    cos_url,
                    content=part_data,
                    timeout=_PART_UPLOAD_TIMEOUT,
                )
                if response.is_success:
                    logger.debug(f"Part {part_number} uploaded successfully")
                    return

                last_error = (
                    f"Part {part_number} PUT failed "
                    f"(status={response.status_code}): {response.text[:100]}"
                )
            except httpx.RequestError as exc:
                last_error = f"Part {part_number} request error: {exc}"

            if attempt < _PART_UPLOAD_MAX_RETRIES:
                await asyncio.sleep(1.0 * (2.0 ** attempt))

        raise UploadError(last_error)

    async def _complete_upload(
        self,
        chat_id: str,
        chat_type: str,
        upload_id: str,
    ) -> UploadCompleteResponse:
        """Step 3: 完成上传，获取 file_info。

        Args:
            chat_id: 用户或群 openid。
            chat_type: 聊天类型。
            upload_id: 上传任务 ID。

        Returns:
            UploadCompleteResponse（含 file_info token）。

        Raises:
            UploadError: 完成上传失败。
        """
        headers: dict[str, str] = await self._get_auth_headers()
        endpoint: str = (
            f"/v2/users/{chat_id}/files"
            if chat_type == "c2c"
            else f"/v2/groups/{chat_id}/files"
        )
        url: str = f"{self.api_base}{endpoint}"
        body: dict[str, object] = {"upload_id": upload_id}

        last_error: str = ""
        for attempt in range(_COMPLETE_UPLOAD_MAX_RETRIES):
            try:
                response: httpx.Response = await self.http_client.post(
                    url, json=body, headers=headers,
                )
                if response.is_success:
                    data: dict[str, object] = response.json()
                    file_info_obj: object = data.get("file_info", "")
                    return UploadCompleteResponse(
                        file_info=str(file_info_obj) if file_info_obj is not None else "",
                    )

                last_error = (
                    f"Complete upload failed "
                    f"(status={response.status_code}): {response.text[:200]}"
                )
            except httpx.RequestError as exc:
                last_error = f"Complete upload request error: {exc}"

            if attempt < _COMPLETE_UPLOAD_MAX_RETRIES - 1:
                delay: float = _COMPLETE_UPLOAD_BASE_DELAY * (2.0 ** attempt)
                await asyncio.sleep(delay)

        raise UploadError(last_error)

    # ==================================================================
    # 工具方法
    # ==================================================================

    @staticmethod
    def _compute_md5_10m(file_path: Path) -> str:
        """计算文件前 10MB 的 md5 值（QQ API 要求）。

        Args:
            file_path: 文件路径。

        Returns:
            十六进制 md5 字符串。
        """
        hasher: hashlib._Hash = hashlib.md5()
        with file_path.open("rb") as f:
            chunk: bytes = f.read(_MD5_10M_SIZE)
            hasher.update(chunk)
        return hasher.hexdigest()
