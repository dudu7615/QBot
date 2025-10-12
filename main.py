from fastapi import FastAPI
from modules.Logger import logger
from modules.Types import MessageData
from plugin import PluginMeta


class MainServer:
    plugins = PluginMeta.plugins

    def __init__(self):
        self.app = FastAPI()

        self.app.post("/")(self.handleMessage)

    async def handleMessage(self, message: MessageData):
        logger.info(f"Received message - {message['d']['content']}")
        content = message["d"]["content"]
        message_type = message["t"]
        
        # 统一处理插件调用逻辑
        for plugin in self.plugins:
            if message_type == plugin.messageType.value:
                # 对于命令型消息（以/开头）匹配特定前缀
                if content.startswith("/") and content.startswith(plugin.messageStartWith) and plugin.messageStartWith != "":
                    logger.info(f"call special plugin: {plugin.pluginName}")
                    await plugin.run(message)
                    break
                # 对于普通消息，匹配空前缀的插件
                elif not content.startswith("/") and plugin.messageStartWith == "":
                    logger.info(f"call plugin: {plugin.pluginName}")
                    await plugin.run(message)
                    break


server = MainServer()


if __name__ == "__main__":
    logger.info("Starting application")
    logger.info("Application initialized successfully")
    import uvicorn

    uvicorn.run(
        "main:server.app",
        host="0.0.0.0",
        port=8000,
        workers=2,
    )
