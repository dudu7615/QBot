from modules.Logger import logger
from modules.Types import MessageData, MessageType
from modules import HttpSender
from plugin.PluginBase import PluginBase
from plugin.GlmAi_d import RequApi
from plugin.GlmAi_d.History import PersonHistory


class GlmAi(PluginBase):
    usable = True

    @property
    def messageType(self) -> MessageType.Group | MessageType.Person:
        return MessageType.Person.C2C_MESSAGE_CREATE

    @property
    def pluginName(self) -> str:
        return "GlmAi"

    async def run(self, message: MessageData):
        content = message["d"]["content"]
        author = message["d"]["author"]
        if content.startswith("!") or content.startswith("！"):
            command = content.split(" ")[0][1:]
            match command:
                case "clear":
                    PersonHistory(author["id"]).clearHistory()

                    await HttpSender.sendText2Person(
                        "已清空历史记录", message, author["id"]
                    )
                case _:
                    logger.warning(f"未知命令: {command}")
                    await HttpSender.sendText2Person(
                        "使用 “!clear” 清空历史记录", message, author["id"]
                    )

        else:
            reply = await RequApi.RequApi(content, author["id"])
            await HttpSender.sendText2Person(reply, message, author["id"])
