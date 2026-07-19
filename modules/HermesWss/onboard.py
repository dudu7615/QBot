"""
HermesWss — QQ Bot 扫码配网（onboarding）。

允许用户扫描终端打印的 QR 码，自动填写 app_id 和 client_secret。

流程：
    1. 生成 AES-256 绑定密钥
    2. 调用 ``/lite/create_bind_task`` 创建扫码任务
    3. 在终端渲染 QR 码并打印连接 URL
    4. 轮询 ``/lite/poll_bind_result`` 等待用户扫码
    5. 解密返回的 ``bot_encrypt_secret`` 得到 ``client_secret``
    6. 返回 :class:`BindResult`

从 Hermes Agent 的 ``gateway/platforms/qqbot/onboard.py`` 移植。
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from .constants import (
    ONBOARD_API_TIMEOUT,
    ONBOARD_CREATE_PATH,
    ONBOARD_POLL_INTERVAL,
    ONBOARD_POLL_PATH,
    PORTAL_HOST,
    QR_URL_TEMPLATE,
)
from .crypto import decrypt_secret, generate_bind_key
from .exceptions import QQBindError, QQBindTaskError
from .models import BindResult, BindStatusEnum
from .utils import get_api_headers

logger = logging.getLogger(__name__)


def build_connect_url(task_id: str) -> str:
    """根据 ``task_id`` 构建扫码配网 URL。

    URL 指向 QQ Bot 的 H5 配网页面，用户使用手机 QQ
    扫描该页面上的二维码即可完成绑定。

    Args:
        task_id: 通过 :func:`_create_bind_task` 获取的任务 ID。

    Returns:
        完整的配网页面 URL（可在浏览器打开，手机 QQ 扫码）。
    """
    return QR_URL_TEMPLATE.format(task_id=task_id)


def _render_qr(url: str) -> bool:
    """尝试在终端渲染 QR 码。

    依赖可选的 ``qrcode`` 包。如果未安装，仅输出提示信息，
    不会中断流程。

    Args:
        url: 需要编码为 QR 码的 URL。

    Returns:
        ``True`` 表示 QR 码渲染成功，``False`` 表示
        ``qrcode`` 包未安装或渲染过程出错。
    """
    try:
        import qrcode  # type: ignore[import-untyped]

        qr = qrcode.QRCode(box_size=2, border=1)
        qr.add_data(url)
        qr.print_ascii(invert=True)
        return True
    except ImportError:
        logger.info("qrcode 包未安装，跳过 QR 码终端渲染。")
        return False
    except Exception:
        logger.exception("QR 码渲染异常。")
        return False


def _create_bind_task(timeout: float) -> tuple[str, str]:
    """创建扫码配网任务。

    向 QQ Bot Portal 发送 ``create_bind_task`` 请求。
    请求体中携带一个由 :func:`generate_bind_key` 生成的 AES-256 密钥，
    服务器会用该密钥加密返回的 ``client_secret``。

    Args:
        timeout: HTTP 请求超时秒数。

    Returns:
        ``(task_id, aes_key_base64)`` 元组。

    Raises:
        QQBindTaskError: 任务创建失败（网络错误或非 2xx 响应）。
    """
    aes_key: str = generate_bind_key()
    url: str = f"https://{PORTAL_HOST}{ONBOARD_CREATE_PATH}"

    try:
        with httpx.Client(timeout=timeout) as client:
            resp: httpx.Response = client.post(
                url,
                json={"bind_key": aes_key},
                headers=get_api_headers(),
            )
    except httpx.HTTPError as exc:
        raise QQBindTaskError(
            f"创建绑定任务失败（网络错误）: {exc}"
        ) from exc

    if resp.status_code != 200:
        raise QQBindTaskError(
            f"创建绑定任务失败（HTTP {resp.status_code}）: {resp.text[:200]}"
        )

    data: object = resp.json()
    if not isinstance(data, dict):
        raise QQBindTaskError(
            f"创建绑定任务返回格式异常: {type(data).__name__}"
        )

    task_id: object = data.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise QQBindTaskError(
            f"响应中缺少 task_id: {data}"
        )

    return (task_id, aes_key)


def _poll_bind_result(
    task_id: str, timeout: float
) -> tuple[BindStatusEnum, str, str, str]:
    """轮询扫码配网结果。

    以 ``ONBOARD_POLL_INTERVAL`` 为间隔向 Portal 发送
    ``poll_bind_result`` 请求，直到任务完成、过期或超时。

    Args:
        task_id: 要轮询的任务 ID。
        timeout: 总超时秒数（从调用时开始计算）。

    Returns:
        ``(status, app_id, encrypted_secret, user_openid)`` 元组。
        - ``status``: :class:`BindStatusEnum` 状态码。
        - ``app_id``: 机器人的 app_id（仅 ``COMPLETED`` 时有值）。
        - ``encrypted_secret``: AES-GCM 加密的 ``client_secret``
          （仅 ``COMPLETED`` 时有值）。
        - ``user_openid``: 扫码用户的 openid（仅 ``COMPLETED`` 时有值）。

    Raises:
        QQBindError: 轮询过程中发生网络异常或响应格式错误。
    """
    url: str = f"https://{PORTAL_HOST}{ONBOARD_POLL_PATH}"
    deadline: float = time.monotonic() + timeout

    while True:
        remaining: float = deadline - time.monotonic()
        if remaining <= 0:
            return (BindStatusEnum.EXPIRED, "", "", "")

        try:
            with httpx.Client(timeout=ONBOARD_API_TIMEOUT) as client:
                resp: httpx.Response = client.post(
                    url,
                    json={"task_id": task_id},
                    headers=get_api_headers(),
                )
        except httpx.HTTPError as exc:
            raise QQBindError(
                f"轮询绑定结果失败（网络错误）: {exc}"
            ) from exc

        if resp.status_code != 200:
            raise QQBindError(
                f"轮询绑定结果失败（HTTP {resp.status_code}）: {resp.text[:200]}"
            )

        data: object = resp.json()
        if not isinstance(data, dict):
            raise QQBindError(
                f"轮询绑定结果返回格式异常: {type(data).__name__}"
            )

        raw_status: object = data.get("task_status")
        if not isinstance(raw_status, int):
            raise QQBindError(
                f"响应中缺少 task_status 或类型错误: {data}"
            )

        try:
            status: BindStatusEnum = BindStatusEnum(raw_status)
        except ValueError:
            raise QQBindError(
                f"未知的绑定状态码: {raw_status}"
            ) from None

        if status == BindStatusEnum.COMPLETED:
            app_id: object = data.get("app_id", "")
            encrypted_secret: object = data.get("bot_encrypt_secret", "")
            user_openid: object = data.get("user_openid", "")

            if not isinstance(app_id, str):
                app_id = str(app_id) if app_id is not None else ""
            if not isinstance(encrypted_secret, str):
                encrypted_secret = (
                    str(encrypted_secret)
                    if encrypted_secret is not None
                    else ""
                )
            if not isinstance(user_openid, str):
                user_openid = (
                    str(user_openid) if user_openid is not None else ""
                )

            return (status, app_id, encrypted_secret, user_openid)

        if status == BindStatusEnum.EXPIRED:
            return (status, "", "", "")

        if status == BindStatusEnum.NONE:
            logger.debug("绑定任务尚未激活，继续轮询…")
        elif status == BindStatusEnum.PENDING:
            logger.debug("等待用户扫码…")

        time.sleep(ONBOARD_POLL_INTERVAL)


def qr_register(timeout_seconds: int = 600) -> BindResult | None:
    """QQ Bot 扫码配网主入口。

    完整的工作流：

    1. 调用 ``create_bind_task`` 创建绑定任务，获取 ``task_id``。
    2. 基于 ``task_id`` 构建配网页面 URL。
    3. 尝试在终端渲染 QR 码（依赖 ``qrcode`` 包）。
    4. 打印配网 URL 供用户手动扫码。
    5. 以 ``ONBOARD_POLL_INTERVAL`` 间隔轮询 ``poll_bind_result``。
    6. 扫码完成后用 AES-GCM 密钥解密 ``client_secret``。
    7. 返回 :class:`BindResult`。

    Args:
        timeout_seconds: 整体超时秒数（默认 600 秒）。
            从创建任务开始计算，包括用户扫码等待时间。
            建议至少 120 秒以确保用户有足够的扫码时间。

    Returns:
        - 绑定成功时返回 :class:`BindResult`（包含 app_id、client_secret、
          user_openid）。
        - ``None`` 表示超时或用户未在时限内完成扫码。

    Raises:
        QQBindTaskError: 创建绑定任务阶段失败（网络/服务端错误）。
        QQBindError: 轮询阶段发生不可恢复的错误。
    """
    timeout_float: float = float(timeout_seconds)
    deadline: float = time.monotonic() + timeout_float

    # Step 1: 创建绑定任务
    task_id: str
    aes_key: str
    task_id, aes_key = _create_bind_task(ONBOARD_API_TIMEOUT)

    logger.info(
        "绑定任务已创建: task_id=%s, 请在 %d 秒内完成扫码",
        task_id,
        timeout_seconds,
    )

    # Step 2: 构建配网 URL & 渲染 QR 码
    connect_url: str = build_connect_url(task_id)
    _render_qr(connect_url)

    print(f"\n{'=' * 60}")
    print("  QQ Bot 扫码配网")
    print(f"{'=' * 60}")
    print(f"  请在浏览器中打开以下链接或扫描上方 QR 码：")
    print(f"  {connect_url}")
    print(f"{'=' * 60}\n")

    # Step 3: 轮询绑定结果
    poll_deadline: float = deadline - time.monotonic()
    if poll_deadline <= 0:
        logger.warning("绑定超时（创建任务阶段已耗时超额）")
        return None

    status: BindStatusEnum
    app_id: str
    encrypted_secret: str
    user_openid: str

    status, app_id, encrypted_secret, user_openid = _poll_bind_result(
        task_id, poll_deadline
    )

    # Step 4: 处理结果
    if status == BindStatusEnum.EXPIRED:
        logger.warning("绑定任务已过期（task_id=%s）", task_id)
        return None

    if status != BindStatusEnum.COMPLETED:
        logger.warning(
            "绑定任务未完成（status=%s, task_id=%s）",
            status,
            task_id,
        )
        return None

    if not app_id or not encrypted_secret:
        logger.error(
            "绑定返回数据不完整: app_id=%s, encrypted_secret=%s",
            app_id,
            "***" if encrypted_secret else "(空)",
        )
        return None

    # Step 5: 解密 client_secret
    try:
        client_secret: str = decrypt_secret(encrypted_secret, aes_key)
    except Exception as exc:
        raise QQBindError(
            f"解密 client_secret 失败: {exc}"
        ) from exc

    if not client_secret:
        raise QQBindError("解密后的 client_secret 为空")

    logger.info(
        "扫码配网成功: app_id=%s, user_openid=%s",
        app_id,
        user_openid,
    )

    return BindResult(
        app_id=app_id,
        client_secret=client_secret,
        user_openid=user_openid,
    )
