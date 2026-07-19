# HermesWss — QQ Bot WebSocket 客户端模块

基于 QQ Bot API v2 **WebSocket Gateway 协议**的客户端模块，替代官方回调（webhook）方式。

从 Hermes Agent（Nous Research）的 `gateway/platforms/qqbot/` 移植，
所有数据类型已迁移为 **Pydantic v2**，全部通过 **mypy --strict** 类型检查。

## 核心特性

| 功能 | 说明 |
|------|------|
| **WebSocket 长连接** | 替代回调，无需公网暴露端口、配 SSL、验证回调 URL |
| **自动重连** | 带退避策略，覆盖 QQ 所有关闭码（4004/4006/4008/4009/4914/4915） |
| **心跳保活** | 根据 Hello 事件动态调整心跳间隔 |
| **会话恢复** | Identify / Resume 双模式，重连不丢 session |
| **消息去重** | 基于 msg_id 的去重机制 |
| **文字发送** | C2C 私聊 / 群聊，超长自动分片 |
| **富媒体发送** | 图片、语音、视频、文件（URL 方式） |
| **内联键盘** | ✅允许一次 / ⭐始终允许 / ❌拒绝 审批键盘，✓确认/✗取消 确认键盘 |
| **按钮交互** | INTERACTION_CREATE 事件解析与路由 |
| **大文件上传** | 三步分片上传（10MB~100MB），并发支持 |
| **扫码配网** | QR 码扫码自动配置 app_id 和 client_secret |
| **Token 管理** | 自动获取/刷新，singleflight 防并发 |
| **Proxy 支持** | 通过 WSS_PROXY / HTTPS_PROXY 环境变量 |

## 文件结构

```
modules/HermesWss/
├── __init__.py           # 导出入口
├── constants.py          # API 端点、超时、WS 关闭码枚举
├── models.py             # 全部 Pydantic 数据模型（含 to_dict）
├── exceptions.py         # 自定义异常
├── token_manager.py      # Access Token 管理（singleflight）
├── utils.py              # User-Agent、HTTP 头、配置辅助
├── crypto.py             # AES-256-GCM 加解密
├── keyboards.py          # 内联键盘构建器 + 审批文本
├── sender.py             # REST API 消息发送器（文字/富媒体/键盘）
├── wss_client.py         # WebSocket 客户端（连接/心跳/消息接收）
├── chunked_upload.py     # 大文件分片上传器
└── onboard.py            # QR 扫码配网
```

## 快速开始

```python
import asyncio
from modules.HermesWss import QQWebSocketClient, QQMessage, QQMessageSender

async def on_message(msg: QQMessage) -> None:
    """收到消息时的回调。"""
    print(f"[{msg.event_type}] {msg.content}")

    # 自动回复
    sender = QQMessageSender("app_id", "client_secret")
    if msg.user_openid:
        await sender.send_text_to_c2c(
            msg.user_openid, f"你说: {msg.content}", reply_to=msg.id,
        )
    elif msg.group_openid:
        await sender.send_text_to_group(
            msg.group_openid, f"@{msg.author.member_openid} 你说: {msg.content}",
            reply_to=msg.id,
        )

async def main():
    client = QQWebSocketClient(
        app_id="你的app_id",
        client_secret="你的client_secret",
        on_message=on_message,
    )
    await client.start()

    # 保持运行
    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        await client.stop()

asyncio.run(main())
```

## 与原有 QBot 集成

在 `main.py` 中替换 FastAPI 回调：

```python
# 替换前
from fastapi import FastAPI
app = FastAPI()
@app.post("/")
async def handle_webhook(data: dict):
    # 处理回调...

# 替换后
from modules.HermesWss import QQWebSocketClient, QQMessage

async def handle_message(msg: QQMessage) -> None:
    # msg 直接转为老格式
    old_data = {
        "id": msg.id,
        "d": {
            "id": msg.id,
            "content": msg.content,
            "timestamp": msg.timestamp,
            "author": {
                "id": msg.author.id if msg.author else "",
                "user_openid": msg.user_openid or msg.group_member_openid or "",
            },
            "message_type": 0,
        },
        "t": msg.event_type,
    }
    # 调用现有插件系统
    for plugin in MainServer.plugins:
        ...

client = QQWebSocketClient(
    app_id=config["appId"],
    client_secret=config["clientSecret"],
    on_message=handle_message,
)
await client.start()
```

## 依赖

- Python >= 3.13
- pydantic >= 2.0
- aiohttp >= 3.11（WebSocket + HTTP 客户端）
- httpx >= 0.28（compat，MessageSender 使用）
- cryptography >= 46.0（AES-256-GCM 解密）
- qrcode（可选，扫码配网终端显示）

## 与 Hermes 原版的差异

| 项目 | Hermes 原版 | HermesWss |
|------|-------------|-----------|
| 数据模型 | 分散 TypedDict + dataclass | **集中 Pydantic v2** |
| 类型检查 | 部分类型标注 | **mypy --strict 全部通过** |
| 去耦合 | 强耦合 Hermes core（BasePlatformAdapter） | **零外部依赖** |
| 导入限制 | 需在 Hermes 项目内使用 | 独立模块，pip install 即可 |
| 配置 | YAML + env 混用 | 纯构造参数注入 |
| 文档 | 英文 + SDK 风格 | 中文文档 |

## 许可

从 Hermes Agent（Apache 2.0）移植。
