"""
HermesWss — AES-256-GCM 加解密工具。

从 Hermes Agent 的 gateway/platforms/qqbot/crypto.py 移植。

用于 QR 扫码配网流程中解密 QQ 返回的 client_secret。
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_bind_key() -> str:
    """生成 256 位随机 AES 密钥，返回 base64 字符串。"""
    return base64.b64encode(os.urandom(32)).decode("ascii")


def decrypt_secret(encrypted_base64: str, key_base64: str) -> str:
    """解密 base64 编码的 AES-256-GCM 密文。

    密文布局（base64 解码后）：
        IV (12 bytes) ‖ ciphertext (N bytes) ‖ AuthTag (16 bytes)

    Args:
        encrypted_base64: ``poll_bind_result`` 返回的 ``bot_encrypt_secret``。
        key_base64: :func:`generate_bind_key` 生成的 base64 AES 密钥。

    Returns:
        解密后的 ``client_secret`` UTF-8 字符串。
    """
    key: bytes = base64.b64decode(key_base64)
    raw: bytes = base64.b64decode(encrypted_base64)

    iv: bytes = raw[:12]
    ciphertext_with_tag: bytes = raw[12:]

    aesgcm = AESGCM(key)
    plaintext: bytes = aesgcm.decrypt(iv, ciphertext_with_tag, None)
    return plaintext.decode("utf-8")
