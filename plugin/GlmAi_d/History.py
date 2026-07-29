from plugin.GlmAi_d import Paths, Types
from plugin.GlmAi_d.Config import config
from plugin.GlmAi_d.Sql import *


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

        return [
            {"role": msg.role, "content": msg.content}
            for msg in Message.getByOpenId(self.openId)
        ]

    def clearHistory(self) -> None:

        Message.clearByOpenId(self.openId)
        self._loadSystemPrompt()
