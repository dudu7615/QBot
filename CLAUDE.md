# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                    # Install/update dependencies
uv run python main.py      # Start the bot (WebSocket client)
uv run mypy main.py        # Type-check (use --explicit-package-bases for module resolution)
uv run python -c "..."     # Run one-off Python snippets
```

This project uses `uv` as the package manager — always use `uv` instead of `pip`.

## Rules

1. ALWAYS use `uv` to manage packages and run spirit.
2. DO NOT use `pip` or `uv pip` to install packages.
3. use `loguru` for logging output, do not use `print` or `logging`.
4. EVERY code MUST pass examination of `mypy --strict`， DO NOT use `Any` if not necessary.
5. data types MUST define by `pydantic`.

## Project Architecture

**QBot** is a QQ Bot that connects to the QQ Bot API v2 via WebSocket (HermesWss) to receive messages in real-time, then dispatches them through a plugin system for automated replies.

### Message Flow

```
QQ Gateway (WebSocket)
  └─► HermesWss/QQWebSocketClient  (wss_client.py)
        └─► on_message(msg: QQMessage)
              └─► main.py → _to_old_message_data()  (convert QQMessage → MessageData)
                    └─► _dispatch_to_plugins()  (match by event type + command prefix)
                          ├─► plugin/AiChat.py     — AI chat via local newapi (OpenAI-compatible)
                          ├─► plugin/Weather.py   — Weather queries (心知天气 API)
                          └─► plugin/Holiday.py   — Holiday queries (timor.tech API)
                                └─► HttpSender.sendText2Person()  →  HermesWss/QQMessageSender
```

### Key Directories

| Directory | Purpose |
|-----------|---------|
| `modules/HermesWss/` | **WebSocket 客户端** — 连接 QQ Bot Gateway，接收消息、发送消息、心跳保活、断线重连 |
| `modules/` | 核心模块：`Config` (YAML配置)、`HttpSender` (消息发送封装)、`Types` (MessageData TypedDict)、`Logger` (loguru) |
| `plugin/` | **插件系统** — `PluginBase` 抽象基类 + 元类自动注册；每个插件实现 `run(message)` |
| `plugin/*_d/` | 各插件的依赖模块（如 Sqlite 缓存、API 调用） |

### Plugins

| Plugin | Command | Type |
|--------|---------|------|
| AiChat | `!clear` (私聊) | C2C_MESSAGE_CREATE |
| Weather | `/今日天气`, `/天气预报`, `/常住地` (私聊) | C2C_MESSAGE_CREATE |
| Holiday | `/最近假期` (私聊) | C2C_MESSAGE_CREATE |

### Plugin Registration

Plugins inherit `PluginBase` with `usable = True`. The `PluginMeta` metaclass auto-registers each plugin instance into `PluginMeta.plugins` at import time. All plugins are imported in `plugin/__init__.py`.

### Data Types

- **Incoming:** `QQMessage` (Pydantic v2, from HermesWss) → converted to `MessageData` (TypedDict, for backward compat with plugins)
- **Sending:** `HttpSender.sendText2Person(reply_text, received_message, user_openid)` — backward-compatible wrapper around `QQMessageSender`

### Config

`config.yaml` at project root holds `appId` and `clientSecret` for QQ Bot authentication. Loaded by `modules/Config.py` as a TypedDict.

### Key Dependencies

- `aiohttp` — WebSocket client (HermesWss)
- `httpx` — REST API calls (sending messages, weather/holiday/glm APIs)
- `pydantic` — Data models (HermesWss)
- `loguru` — Logging
- `pyyaml` — Configuration loading