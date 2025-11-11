from plugin.GlmAi_d import Paths, Types
from plugin.GlmAi_d.Config import config
from plugin.GlmAi_d.Sql import sql


class PersonHistory:
    def __init__(self, openId: str):
        self.openId = openId

    async def _loadSystemPrompt(
        self,
    ) -> None:
        if not await sql("message/get", {"open_id": self.openId}):
            with open(
                Paths.PERSONALITY / f"{config['personality']}", "r", encoding="utf-8"
            ) as f:
                systemPrompt: Types.ApiJson_Messages = {
                    "role": "system",
                    "content": f.read(),
                }

                await sql(
                    "message/add",
                    {
                        "open_id": self.openId,
                        "role": systemPrompt["role"],
                        "content": systemPrompt["content"],
                    },
                )

    async def addHistory(self, message: Types.ApiJson_Messages) -> None:

        await sql(
            "message/add",
            {
                "open_id": self.openId,
                "role": message["role"],
                "content": message["content"],
            },
        )

    async def getHistory(self) -> list[Types.ApiJson_Messages]:

        await self._loadSystemPrompt()
        return [
            {"role": role, "content": content}
            for role, content in await sql("message/get", {"open_id": self.openId})
        ]

    async def clearHistory(self) -> None:

        await sql("message/clear", {"open_id": self.openId})
        await self._loadSystemPrompt()
