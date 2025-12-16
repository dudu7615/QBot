from plugin.GlmAi_d import Paths, Types
from plugin.GlmAi_d.Config import config
from plugin.GlmAi_d.Sql import *


class PersonHistory:
    def __init__(self, openId: str):
        self.openId = openId

    async def _loadSystemPrompt(
        self,
    ) -> None:
        if User.getmessageCount(self.openId) == 0:
            with open(
                Paths.PERSONALITY / f"{config['personality']}", "r", encoding="utf-8"
            ) as f:
                Message.addMessage(self.openId, f.read(), MessageRole.system)

    async def addHistory(self, message: Types.ApiJson_Messages) -> None:
        Message.addMessage(self.openId, message["content"], MessageRole.user if message["role"] == "user" else MessageRole.assistant)


    async def getHistory(self) -> list[Types.ApiJson_Messages]:

        await self._loadSystemPrompt()

        return [
            {"role": role, "content": content}
            for role, content in Message.getByOpenId(self.openId)
        ]

    async def clearHistory(self) -> None:

        Message.clearByOpenId(self.openId)
        await self._loadSystemPrompt()
