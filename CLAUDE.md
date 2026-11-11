# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                    # Install/update dependencies
uv run python main.py      # Start the bot (WebSocket client)
uv run mypy . --explicit-package-bases   # Type-check (strict, 0 errors expected)
uv run python -c "..."     # Run one-off Python snippets
```

This project uses `uv` as the package manager — always use `uv` instead of `pip`.

## Rules

1. ALWAYS use `uv` to manage packages and run spirit.
2. DO NOT use `pip` or `uv pip` to install packages.
3. use `loguru` for logging output, do not use `print` or `logging`.
4. EVERY code MUST pass `uv run mypy . --explicit-package-bases`（strict），非必要不要用 `Any`。
5. 数据类型统一用 `pydantic`（配置、消息、请求/响应模型），不要用 TypedDict。

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
| AiChat | `!clear`；其余消息走 LLM | C2C / GROUP_AT / GROUP（群普通消息有 30s 冷却） |
| Weather | `/今日天气`, `/天气预报`, `/常住地` | C2C / GROUP_AT / GROUP |
| Holiday | `/最近假期` | C2C / GROUP_AT / GROUP |

### Plugin Registration

Plugins inherit `PluginBase` with `usable = True`. The `PluginMeta` metaclass auto-registers each plugin instance into `PluginMeta.plugins` at import time. All plugins are imported in `plugin/__init__.py`.

新增插件必须显式声明 `usable = True`，并设置 `messageStartWith`；
未声明 `usable` 的类按不可用处理（不会注册）。`messageStartWith == ""`
表示兜底处理所有非 `/` 开头的消息，同一时刻只应有一个这样的插件。

### Data Types

- **Incoming:** `QQMessage` (Pydantic v2, from HermesWss) → converted to `MessageData` (Pydantic, for plugins)
- **Sending:** `HttpSender.sendText2Person(reply_text, received_message, user_openid)` — backward-compatible wrapper around `QQMessageSender`

### Config

`config.yaml` at project root holds `appId` and `clientSecret` for QQ Bot authentication.
Loaded by `modules/Config.py` into a Pydantic `Config` model（缺字段会明确报错并退出）。
插件各自的 `config.yaml` 同样用 Pydantic 模型加载。

### Key Dependencies

- `aiohttp` — WebSocket client (HermesWss)
- `httpx` — REST API calls (sending messages, weather/holiday/glm APIs)
- `pydantic` — 所有数据模型（HermesWss、配置、消息、AI 请求/响应）
- `loguru` — Logging
- `pyyaml` — Configuration loading