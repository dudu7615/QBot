from modules.Logger import logger
from modules.Types import MessageData, MessageType
from modules import HttpSender
from plugin.PluginBase import PluginBase
from plugin.AiChat_d import RequApi
from plugin.AiChat_d.History import PersonHistory


class AiChat(PluginBase):
    usable = True

    @property
    def messageType(
        self,
    ) -> list[MessageType.Group | MessageType.Person]:
        return [
            MessageType.Person.C2C_MESSAGE_CREATE,
            MessageType.Group.GROUP_AT_MESSAGE_CREATE,
            MessageType.Group.GROUP_MESSAGE_CREATE,
        ]

    @property
    def pluginName(self) -> str:
        return "AiChat"

    @staticmethod
    def _reply_target(message: MessageData) -> tuple[str, str]:
        """根据消息类型返回 (发送方式, 目标 ID)。

        Returns:
            ("person", author_id) 或 ("group", group_openid)
        """
        if message["t"] in {"GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"}:
            return ("group", message["d"]["group_openid"])
        return ("person", message["d"]["author"]["id"])

    async def run(self, message: MessageData):
        content = message["d"]["content"]
        author = message["d"]["author"]
        union_id = author["union_openid"] or author["id"]
        if content.startswith("!") or content.startswith("！"):
            command = content.split(" ")[0][1:]
            match command:
                case "clear":
                    PersonHistory(union_id).clearHistory()

                    send_type, target = self._reply_target(message)
                    if send_type == "group":
                        await HttpSender.sendText2Group(
                            "已清空历史记录", message, target
                        )
                    else:
                        await HttpSender.sendText2Person(
                            "已清空历史记录", message, target
                        )
                case _:
                    logger.warning(f"未知命令: {command}")
                    send_type, target = self._reply_target(message)
                    if send_type == "group":
                        await HttpSender.sendText2Group(
                            "使用 “!clear” 清空历史记录", message, target
                        )
                    else:
                        await HttpSender.sendText2Person(
                            "使用 “!clear” 清空历史记录", message, target
                        )

        else:
            reply = await RequApi.RequApi(content, union_id)
            send_type, target = self._reply_target(message)
            if send_type == "group":
                await HttpSender.sendText2Group(reply, message, target)
            else:
                await HttpSender.sendText2Person(reply, message, target)
