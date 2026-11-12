"""
QBot — QQ Bot 主入口。

基于 HermesWss WebSocket 客户端连接 QQ Bot Gateway，
替代传统的 FastAPI webhook 方式，无需公网暴露端口。

数据流：
  QQ Gateway (WebSocket)
    → QQWebSocketClient._read_events
      → _dispatch_payload → _on_message
        → on_message 回调 → MainServer.on_message
          → 转换为旧 MessageData 格式 → 插件分发
"""

from __future__ import annotations

import asyncio

from modules.Config import config
from modules.Logger import logger
from modules.Types import MessageAuthor, MessageContent, MessageData
from modules.HermesWss import QQWebSocketClient, QQMessage
from plugin import PluginMeta
from plugin.AiChat_d import RequApi
from plugin.Weather_d import GetWeather


class MainServer:
    """QQ Bot 主服务器。

    管理插件系统和 WebSocket 客户端生命周期。
    """

    plugins = PluginMeta.plugins

    def __init__(self) -> None:
        self.client: QQWebSocketClient | None = None
        logger.info(f"插件注册完成, 共 {len(self.plugins)} 个插件")

    # ==================================================================
    # 生命周期
    # ==================================================================

    async def start(self) -> None:
        """启动 HermesWss WebSocket 客户端。"""
        app_id: str = config.appId
        client_secret: str = config.clientSecret

        logger.info(f"正在启动 WebSocket 客户端 (app_id={app_id})...")

        self.client = QQWebSocketClient(
            app_id=app_id,
            client_secret=client_secret,
            on_message=self.on_message,
            on_interaction=self.on_interaction,
        )

        success: bool = await self.client.start()
        if not success:
            logger.error("WebSocket 客户端启动失败")
            raise RuntimeError("WebSocket 客户端启动失败")

        logger.info("WebSocket 客户端启动成功, 等待消息...")

    async def wait_closed(self) -> None:
        """等待客户端不可恢复地停止。

        客户端放弃重连时置位 stopped 事件，避免进程带着失效连接挂死。
        """
        if self.client is not None:
            await self.client.stopped.wait()

    async def stop(self) -> None:
        """停止 WebSocket 客户端并释放插件持有的 HTTP 连接。"""
        if self.client is not None:
            logger.info("正在停止 WebSocket 客户端...")
            await self.client.stop()
            self.client = None

        await RequApi.close()
        await GetWeather.close()
        logger.info("应用已停止")

    # ==================================================================
    # 消息转换 (QQMessage → 旧 MessageData 格式)
    # ==================================================================

    def _to_message_data(self, msg: QQMessage) -> MessageData:
        """将 HermesWss 的 QQMessage 转换为插件层的 MessageData。

        Args:
            msg: HermesWss 消息对象。

        Returns:
            插件层使用的 MessageData。
        """
        author_id: str = ""
        group_openid: str = msg.group_openid or ""
        if msg.event_type == "C2C_MESSAGE_CREATE":
            author_id = msg.user_openid or ""
        elif msg.event_type in {"GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"}:
            author_id = msg.group_member_openid or msg.group_openid or ""

        return MessageData(
            id=msg.id,
            d=MessageContent(
                id=msg.id,
                content=msg.content,
                timestamp=msg.timestamp,
                author=MessageAuthor(
                    id=author_id,
                    user_openid=msg.user_openid or "",
                    union_openid=(msg.author.union_openid if msg.author else "") or "",
                ),
                group_openid=group_openid,
            ),
            t=msg.event_type,
            event_id=msg.event_id,
        )

    # ==================================================================
    # HermesWss 回调
    # ==================================================================

    async def on_message(self, msg: QQMessage) -> None:
        """HermesWss WebSocket 消息回调。

        将 QQMessage 转为旧格式后复用现有插件分发逻辑。

        Args:
            msg: HermesWss 消息对象。
        """
        message: MessageData = self._to_message_data(msg)
        content: str = msg.content
        message_type: str = msg.event_type

        logger.info(f"收到消息 [{message_type}] content={message.d.content}")

        # 统一处理插件调用逻辑（与原 handleMessage 一致）
        await self._dispatch_to_plugins(message, content, message_type)

    async def on_interaction(self, event: object) -> None:
        """HermesWss 按钮交互事件回调。

        Args:
            event: InteractionEvent 对象。
        """
        # 暂不支持按钮交互事件，可后续扩展
        logger.debug(f"收到按钮交互事件 (暂不处理): {event}")

    # ==================================================================
    # 插件分发（与原 handleMessage 逻辑一致）
    # ==================================================================

    async def _dispatch_to_plugins(
        self,
        message: MessageData,
        content: str,
        message_type: str,
    ) -> None:
        """将消息分发给匹配的插件。

        Args:
            message: 转换后的旧格式消息数据。
            content: 消息文本内容。
            message_type: 事件类型字符串。
        """
        for plugin in self.plugins:
            # 检查事件类型匹配（支持单个或列表）
            types = plugin.messageType
            if isinstance(types, list):
                if not any(message_type == t.value for t in types):
                    continue
            else:
                if message_type != types.value:
                    continue

            if content.startswith("/"):
                # 命令型消息 — 匹配特定前缀
                command: str = content.split(" ")[0]
                if isinstance(plugin.messageStartWith, str):
                    if plugin.messageStartWith == command:
                        logger.info(f"调用命令插件: {plugin.pluginName}")
                        await plugin.run(message)
                        return
                elif isinstance(plugin.messageStartWith, list):
                    if command in plugin.messageStartWith:
                        logger.info(f"调用命令插件: {plugin.pluginName}")
                        await plugin.run(message)
                        return

            elif not content.startswith("/") and plugin.messageStartWith == "":
                # 普通消息 — 匹配空前缀的插件
                logger.info(f"调用插件: {plugin.pluginName}")
                await plugin.run(message)
                return


# ======================================================================
# 入口
# ======================================================================

server = MainServer()


async def main() -> None:
    """异步主入口。"""
    exit_code: int = 0
    try:
        await server.start()
        # 保持运行，直到客户端放弃重连或收到 Ctrl+C
        await server.wait_closed()
        logger.warning("WebSocket 客户端已停止，进程退出")
        exit_code = 1
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("收到中断信号")
    except Exception as exc:
        logger.error(f"启动失败: {exc}")
        exit_code = 1
    finally:
        await server.stop()

    if exit_code != 0:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    logger.info("=" * 40)
    logger.info("QBot 启动中...")
    logger.info("=" * 40)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("应用已退出")
