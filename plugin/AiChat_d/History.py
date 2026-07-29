from plugin.AiChat_d import Paths, Types
from plugin.AiChat_d.Config import config
from plugin.AiChat_d.Sql import *


class PersonHistory:
    def __init__(self, openId: str):
        self.openId = openId
        self._addUserIfNotExist()

    def _addUserIfNotExist(self) -> None:
        if not User.getByOpenId(self.openId):
            User.addOrUpdate(self.openId, "unknown")

    def _loadSystemPrompt(
        self,
    ) -> None:
        if User.getmessageCount(self.openId) == 0:
            with open(
                Paths.PERSONALITY / f"{config['personality']}", "r", encoding="utf-8"
            ) as f:
                Message.addMessage(self.openId, f.read(), MessageRole.system)

    def addHistory(self, message: Types.ApiJson_Messages) -> None:
        Message.addMessage(
            self.openId, message["content"], MessageRole(message["role"])
        )

    def getHistory(self) -> list[Types.ApiJson_Messages]:
        self._loadSystemPrompt()

        messages: list[Message] = Message.getByOpenId(self.openId)

        # 上下文截断：超过 max_context_length 时保留 system prompt + 最近 keep_recent 条
        if len(messages) > config["max_context_length"]:
            system_prompt: Message = messages[0]
            recent: list[Message] = messages[-(config["keep_recent"] - 1):]
            messages = [system_prompt] + recent
            Message.truncateTo(self.openId, config["keep_recent"])

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

    def clearHistory(self) -> None:
        Message.clearByOpenId(self.openId)
        self._loadSystemPrompt()
